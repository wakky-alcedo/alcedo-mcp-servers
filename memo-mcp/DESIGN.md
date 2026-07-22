# DESIGN.md: memo-mcp サーバー

SPEC.md（`memo-mcp/SPEC.md`）に基づく技術設計。既存の `task-mcp` を参照実装とし、
「1サブディレクトリ=1 MCPサーバー」規約に沿って `memo-mcp/` 配下に閉じた形で構築する。

---

## 1. アーキテクチャ概要

memo-mcp は、alcedo-personal-app の pc-server が公開するメモ用REST API
（`/api/v1/memos` 系）を、MCPツールとして薄くラップするステートレスなアダプタである。
自身は永続状態を持たず、リクエストのたびに pc-server へHTTPで問い合わせる。

```
┌──────────────────────────┐        MCP (stdio / streamable-http)
│  MCPクライアント          │
│  - Claude Code (ローカル)  │◀──── stdio ────┐
│  - claude.ai カスタム      │                │
│    コネクタ (スマホ等)      │◀─ streamable-http (via Cloudflare Tunnel)
└──────────────────────────┘                │
                                            ▼
                          ┌─────────────────────────────────┐
                          │  memo-mcp (FastMCP)              │
                          │  memo-mcp/server.py              │
                          │  - list_memos / add_memo /       │
                          │    update_memo / delete_memo     │
                          │  - shared/runner.py で           │
                          │    transport を切替              │
                          │  - httpx.Client + X-Api-Key      │
                          └─────────────────────────────────┘
                                            │ HTTP + X-Api-Key
                                            ▼
                          ┌─────────────────────────────────┐
                          │  pc-server (alcedo-personal-app) │
                          │  Fastify /api/v1                 │
                          │  GET  /api/v1/memos              │
                          │  POST /api/v1/sync/memos         │
                          │  PATCH  /api/v1/memos/:id        │
                          │  DELETE /api/v1/memos/:id        │
                          │        │                         │
                          │        ▼  SQLite (memos)         │
                          └─────────────────────────────────┘
```

- 起動形態は task-mcp と同一。`MCP_TRANSPORT` により、手元PCからの `stdio` 直起動と、
  docker-srv上の常駐 `streamable-http` を切り替える。
- pc-server は task-mcp と同一インスタンス。認証も同一の `X-Api-Key` 方式で、
  `MEMO_API_KEY` に `TASK_API_KEY` と同じ値を設定して運用する（変数自体は独立、値だけ同一）。

---

## 2. 技術スタック

| 技術 | 用途 | 選定理由 |
|------|------|----------|
| Python 3.12 | 実装言語 | task-mcp と同一。参照実装をそのまま踏襲でき、`python:3.12-slim` イメージも流用できる |
| mcp[cli] (FastMCP) | MCPサーバーフレームワーク | task-mcp と同じ `FastMCP`。`@mcp.tool()` デコレータで型ヒントからスキーマ自動生成でき、実装が最小で済む |
| httpx | pc-server へのHTTPクライアント | task-mcp と同一。同期 `httpx.Client` を `with` で使う既存パターンをそのまま流用 |
| shared/runner.py | transport 切替の共通起動 | 既存共通ヘルパー。DNS rebinding protection 無効化などの運用調整が一元化されており再実装不要 |
| Docker / docker-compose | デプロイ | docker-srv 上での常駐。task-mcp と同一ネットワーク（`alcedo-personal-app_default`）に参加 |
| uuid (標準ライブラリ) | 新規メモのID採番 | add_memo での `uuid4()` 生成。SPEC 指定の upsert パターンに必要 |
| datetime (標準ライブラリ) | createdAt/updatedAt のISO文字列生成 | task-mcp の `_now_iso()` と同一実装を流用 |

新規の外部依存は追加しない（task-mcp/requirements.txt と同一内容）。

---

## 3. ファイル構成

```
memo-mcp/
├── SPEC.md          # 仕様書（既存・入力）
├── DESIGN.md        # 本ファイル
├── server.py        # MCPサーバー本体。4ツールを定義（task-mcp/server.py と同型）
├── requirements.txt # 依存定義。mcp[cli] と httpx（task-mcp と同一内容）
└── Dockerfile       # streamable-http 常駐用イメージ定義（task-mcp/Dockerfile を8804向けに調整）
```

リポジトリルート側で変更するファイル:

```
docker-compose.yml   # memo-mcp サービスを追記（8804公開、環境変数 MEMO_*）
.env                 # MEMO_API_KEY を追加（TASK_API_KEY と同じ値を設定）
```

各ファイルの役割:

- **memo-mcp/server.py**: 本設計の中心。`BASE_URL`/`API_KEY` を環境変数から読み、
  `_client()` で認証付き `httpx.Client` を生成し、4つの `@mcp.tool()` 関数を定義する。
  `__main__` で `shared.runner.run_server(mcp)` を呼ぶ（task-mcp と完全同型のブート処理）。
- **memo-mcp/requirements.txt**: `mcp[cli]>=1.0.0` / `httpx>=0.27.0`（task-mcp と同一）。
- **memo-mcp/Dockerfile**: ビルドコンテキストはリポジトリルート。`shared/` と `memo-mcp/` を
  コピーし、`MCP_PORT=8804` / `EXPOSE 8804` / `CMD ["python3", "memo-mcp/server.py"]`。
- **docker-compose.yml**: `memo-mcp` サービスを追加し、`8804:8804` を公開、
  `MEMO_API_BASE_URL` / `MEMO_API_KEY`（独立変数 `${MEMO_API_KEY}` を参照）を設定。
- **.env**: `MEMO_API_KEY` を独立した設定変数として定義し、`TASK_API_KEY` と同一の値を設定する
  （task-mcp が `TASK_API_KEY` を参照するのと対称な運用）。

---

## 4. 主要コンポーネント

### 4.1 モジュールレベル初期化（server.py 冒頭）
- `BASE_URL = os.environ.get("MEMO_API_BASE_URL", "http://192.168.10.5:8787").rstrip("/")`
- `API_KEY = os.environ.get("MEMO_API_KEY")`（未設定なら stderr にエラー出力して `sys.exit(1)`）
- `mcp = FastMCP("memo-mcp")`
- task-mcp と同じガード。環境変数名だけ `TASK_*` → `MEMO_*` に置換。

### 4.2 ヘルパー関数
- `_client() -> httpx.Client`: `base_url`, `X-Api-Key`, `Content-Type: application/json`,
  `timeout=10.0` を持つクライアントを返す（task-mcp と同一）。
- `_now_iso() -> str`: `datetime.now(timezone.utc).isoformat()`（task-mcp と同一）。
- task-mcp の `_flatten` / `_find_task_recursive` はメモにツリー構造がないため**移植しない**。

### 4.3 ツール関数（責務）

| ツール | HTTP呼び出し | 責務 | エラー方針 |
|--------|-------------|------|-----------|
| `list_memos(limit=50, since=None)` | `GET /api/v1/memos?limit=&since=` | 一覧取得。`{count, memos, next_cursor}` を返す。`since` が None ならクエリに含めない | `raise_for_status()` |
| `add_memo(body, source_url=None, source_title=None)` | `POST /api/v1/sync/memos` | `uuid4()` で id 採番、`version:1`・`createdAt`/`updatedAt` を付与し `upserts:[...]` で送信。`{id, body, result}` を返す | `raise_for_status()` |
| `update_memo(memo_id, body)` | `PATCH /api/v1/memos/{memo_id}` | 本文更新。`{id, memo}` を返す | HTTP 404 を明示判定し `ValueError` |
| `delete_memo(memo_id)` | `DELETE /api/v1/memos/{memo_id}` | 削除。`{id, deleted: True}` を返す | HTTP 404 を明示判定し `ValueError` |

補足:
- `list_memos` のクエリは `params` を dict で組み立て、`since` が None のキーは除外する。
  戻り値の `next_cursor` は pc-server レスポンスの該当キーをそのまま透過（無ければ None）。
- `add_memo` は SPEC の「新規追加は version=1 の upsert として送る」パターン。
  ペイロードは `{"upserts": [{"id", "body", "sourceUrl", "sourceTitle", "version":1,
  "createdAt", "updatedAt"}]}`。`createdAt` と `updatedAt` は同一の `_now_iso()` 値。
- `update_memo` / `delete_memo` は PATCH/DELETE の専用エンドポイントを使う（add と異なり
  sync API ではない）。エラー方針は **task-mcp の sync ベース実装とは異なる**独自方針で、
  `resp.status_code == 404` を明示判定して `ValueError` を送出する。それ以外の非2xxは
  `raise_for_status()` に委ねる。

### 4.4 依存関係
```
server.py
  ├─ 依存 → mcp.server.fastmcp.FastMCP        （ツール登録・起動）
  ├─ 依存 → httpx                              （pc-server へのHTTP）
  ├─ 依存 → uuid.uuid4, datetime               （add_memo のID/時刻）
  └─ 依存 → shared.runner.run_server           （__main__ でのtransport切替）
              └─ 依存 → os                      （MCP_TRANSPORT/PORT/HOST）
server.py は他のサーバー（task-mcp等）に一切依存しない（横結合なし）。
```

### 4.5 ブート処理（__main__）
task-mcp と同一。`sys.path.insert(0, <repo root>)` の後 `from shared.runner import run_server`
を実行し `run_server(mcp)` を呼ぶ。`MCP_PORT` 未指定時のデフォルトは runner 側の 8800 だが、
Dockerfile と docker-compose で `MCP_PORT=8804` を明示するため実運用は 8804 で待受する。

---

## 5. リスクと対策

| リスク | 内容 | 対策 |
|--------|------|------|
| pc-server の memos API 実レスポンス形状のズレ | SPEC 記載のフィールド（`next_cursor`, `sourceUrl` 等）が実APIと微妙に異なる可能性 | ツールは受け取ったJSONを極力そのまま透過（`result`/`memo` にraw dictを載せる）。キーの有無は `.get()` で安全に扱い、KeyErrorで落とさない |
| PATCH/DELETE エンドポイントの実在 | update/delete は `PATCH/DELETE /api/v1/memos/:id` に依拠する。参照実装 task-mcp は全変更を `POST /api/v1/sync/tasks`（upserts/deletions）で行っており REST 変更系を使っていないため、memos だけ REST 変更系があるかが論点になり得る | **エンドポイントの実在は pc-server dev branch のソースコード（`pc-server/src/routes/memos.ts`）で確認済み**。`PATCH /api/v1/memos/:id` と `DELETE /api/v1/memos/:id` は実装されており、SPEC の記載どおり REST 方式を採用する。念のため実装フェーズ冒頭で受け入れシナリオ（add→list→update→delete）を1回通し、想定外の 404/405 が出た場合のみ sync API へのフォールバックを検討する |
| 404 とその他エラーの扱いの取り違え | update/delete で存在しないIDのとき、単純な `raise_for_status()` だと HTTPStatusError となり呼び出し元に伝わりにくい | **task-mcp とは異なり**、pc-server 側が 404 を返す REST エンドポイントを使うため、`resp.status_code == 404` を先に明示判定して `ValueError(f"メモが見つかりません: {memo_id}")` を送出する。SPEC の「404はValueError」を満たしつつ Claude に読みやすいメッセージを返す（task-mcp は HTTP 404 判定を行わず、一覧取得後のローカル未検出で ValueError を出す別方式であり、同一視しない） |
| MEMO_API_KEY 未設定での無言起動 | 認証キー欠落で全呼び出しが401になり原因が分かりにくい | task-mcp 同様、モジュール読込時にキー未設定なら stderr へ明示メッセージを出して `sys.exit(1)` |
| MEMO_API_KEY の変数モデル逸脱 | compose で `${TASK_API_KEY}` を直接補間すると、`.env` の `MEMO_API_KEY` が無視され、鍵ローテーションや memo 側の別鍵化ができず、`TASK_API_KEY` 未定義時に無言で空値になる（SPECの独立変数モデルからの逸脱＝仕様ドリフト） | compose は独立変数 `MEMO_API_KEY=${MEMO_API_KEY}` を参照し、`.env` に `MEMO_API_KEY` を定義して `TASK_API_KEY` と同一値を設定する運用にする（task-mcp の `TASK_API_KEY=${TASK_API_KEY}` と対称な変数モデル） |
| ポート衝突 | 8800(task) と重複すると起動失敗 | SPEC 指定の 8804 を Dockerfile / docker-compose / EXPOSE すべてで統一。docker-compose のポートマッピングも `8804:8804` |
| ルート直下 obsidian-mcp 資材との混線 | 同名ファイルが複数ディレクトリに存在 | 生成・変更対象を `memo-mcp/` 配下 + ルートの `docker-compose.yml` / `.env` 追記のみに限定。ルート直下の SPEC/DESIGN/PLAN には触れない |
| timeout=10s が長文メモ登録で不足する可能性 | 大きな body の同期で遅延 | 初期値は task-mcp と揃えて 10.0。問題が出れば環境変数化は将来拡張（今回スコープ外） |
| shared/runner.py の MCP_PORT デフォルト8800 依存 | server.py 単体起動時に 8800 で立つ | streamable-http 運用は必ず Dockerfile/compose 経由で `MCP_PORT=8804` を渡す前提を明記。stdio ローカル起動時はポート非使用のため影響なし |

---

## 付録: docker-compose.yml 追記イメージ（実装フェーズでの反映方針）

```yaml
  memo-mcp:
    build:
      context: .
      dockerfile: memo-mcp/Dockerfile
    ports:
      - "8804:8804"
    environment:
      - MCP_TRANSPORT=streamable-http
      - MCP_PORT=8804
      - MEMO_API_BASE_URL=http://backend:8787
      - MEMO_API_KEY=${MEMO_API_KEY}   # 独立変数。.env で TASK_API_KEY と同じ値を設定する
    restart: always
```

`.env` には次のように両変数へ同一値を設定する（task-mcp と対称な変数モデル）:

```dotenv
TASK_API_KEY=<pc-server の API_KEY>
MEMO_API_KEY=<TASK_API_KEY と同じ値>
```

`networks` セクション（`alcedo-personal-app_default`, external）は既存のものを共有する。
