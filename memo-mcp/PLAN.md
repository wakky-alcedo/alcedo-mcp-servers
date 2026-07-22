# 実装計画: memo-mcp サーバー

本計画は `memo-mcp/SPEC.md` および `memo-mcp/DESIGN.md` に基づく。
生成・変更対象は `memo-mcp/` 配下、およびリポジトリルートの
`docker-compose.yml` / `.env.example` / `README.md` への追記に限定する。
ルート直下の SPEC.md / DESIGN.md / PLAN.md（obsidian-mcp 用の別機能）には一切触れない。

参照実装は `task-mcp/`。環境変数名は `TASK_*` → `MEMO_*`、ポートは 8800 → 8804 に置換する。

補足（DESIGN との整合）: DESIGN.md（3節・付録）は変更対象を `.env` と記載しているが、
`.env` は `.gitignore` 対象で非コミットのため、リポジトリにコミットされているのは
`.env.example`（テンプレート、現状 `TASK_API_KEY=` のみ）である。本計画では DESIGN の
`.env` 記述をコミット対象の `.env.example` を指すものと解釈し、コミット対象の変更は
タスク9で `.env.example` に対して行う。実運用の `.env`（非コミット）への `MEMO_API_KEY`
設定は動作確認の運用前提として受け入れ確認セクションに記載する。

---

## タスクリスト

- [ ] タスク1: memo-mcp/requirements.txt を作成
  - 内容: `mcp[cli]>=1.0.0` と `httpx>=0.27.0` の2行（task-mcp/requirements.txt と同一内容）
  - 完了条件: `/home/wakky/alcedo-mcp-servers/memo-mcp/requirements.txt` が存在し、上記2行を含む
  - 依存: なし

- [ ] タスク2: memo-mcp/server.py を作成（モジュール初期化とヘルパー）
  - 内容: モジュール docstring、import（os, sys, datetime, typing, uuid4, httpx, FastMCP）、
    `BASE_URL = os.environ.get("MEMO_API_BASE_URL", "http://192.168.10.5:8787").rstrip("/")`、
    `API_KEY = os.environ.get("MEMO_API_KEY")`（未設定なら stderr 出力して `sys.exit(1)`）、
    `mcp = FastMCP("memo-mcp")`、`_client()`、`_now_iso()` を実装。
    task-mcp の `_flatten` / `_find_task_recursive` は移植しない。
  - 完了条件: `/home/wakky/alcedo-mcp-servers/memo-mcp/server.py` が存在し、
    上記の初期化・ガード・2ヘルパーが記述されている（後続タスクでツールを追記）
  - 依存: なし

- [ ] タスク3: server.py に list_memos ツールを実装
  - 内容: `@mcp.tool() def list_memos(limit: int = 50, since: Optional[str] = None)`。
    `GET /api/v1/memos` を `params`（since が None のキーは除外）で呼び出し、
    `raise_for_status()`。戻り値 `{count, memos, next_cursor}`。
    memos は `data.get("memos", [])`、next_cursor は `data.get(...)` で安全に透過（無ければ None）
  - 完了条件: list_memos 関数が server.py に定義され、`python3 -m py_compile memo-mcp/server.py` が通る
  - 依存: タスク2

- [ ] タスク4: server.py に add_memo ツールを実装
  - 内容: `@mcp.tool() def add_memo(body: str, source_url=None, source_title=None)`。
    `uuid4()` で id 採番、`_now_iso()` を createdAt/updatedAt に同一値で付与、
    `{"upserts":[{id, body, sourceUrl, sourceTitle, version:1, createdAt, updatedAt}]}` を
    `POST /api/v1/sync/memos` に送信し `raise_for_status()`。戻り値 `{id, body, result}`
  - 完了条件: add_memo 関数が server.py に定義され、`python3 -m py_compile memo-mcp/server.py` が通る
  - 依存: タスク2

- [ ] タスク5: server.py に update_memo ツールを実装
  - 内容: `@mcp.tool() def update_memo(memo_id: str, body: str)`。
    `PATCH /api/v1/memos/{memo_id}` に `{body}` を送信。
    `resp.status_code == 404` を明示判定して `ValueError(f"メモが見つかりません: {memo_id}")`、
    それ以外の非2xxは `raise_for_status()`。戻り値 `{id, memo}`
  - 完了条件: update_memo 関数が server.py に定義され、404判定分岐を含み、
    `python3 -m py_compile memo-mcp/server.py` が通る
  - 依存: タスク2

- [ ] タスク6: server.py に delete_memo ツールと __main__ ブート処理を実装
  - 内容: `@mcp.tool() def delete_memo(memo_id: str)`。
    `DELETE /api/v1/memos/{memo_id}`。404 を明示判定して `ValueError`、それ以外は `raise_for_status()`。
    戻り値 `{id, deleted: True}`。加えて `if __name__ == "__main__":` で
    `sys.path.insert(0, <repo root>)` 後 `from shared.runner import run_server` → `run_server(mcp)`
    （task-mcp と同型）
  - 完了条件: delete_memo と __main__ が server.py に定義され、
    `python3 -m py_compile memo-mcp/server.py` が構文エラーなく通る
  - 依存: タスク2, タスク3, タスク4, タスク5

- [ ] タスク7: memo-mcp/Dockerfile を作成
  - 内容: `python:3.12-slim` ベース、ビルドコンテキストはリポジトリルート。
    `memo-mcp/requirements.txt` をコピーして pip install、`shared/` と `memo-mcp/` をコピー、
    `ENV MCP_TRANSPORT=streamable-http`、`ENV MCP_PORT=8804`、`EXPOSE 8804`、
    `CMD ["python3", "memo-mcp/server.py"]`（task-mcp/Dockerfile を8804向けに調整）
  - 完了条件: `/home/wakky/alcedo-mcp-servers/memo-mcp/Dockerfile` が存在し、
    8804 と memo-mcp パスを参照している
  - 依存: タスク1, タスク6

- [ ] タスク8: ルート docker-compose.yml に memo-mcp サービスを追記
  - 内容: `services:` 配下に `memo-mcp` サービスを追加。
    `build.context: .`、`dockerfile: memo-mcp/Dockerfile`、`ports: ["8804:8804"]`、
    environment に `MCP_TRANSPORT=streamable-http`、`MCP_PORT=8804`、
    `MEMO_API_BASE_URL=http://backend:8787`、`MEMO_API_KEY=${MEMO_API_KEY}`（独立変数）、
    `restart: always`。既存の task-mcp サービスと networks セクションは変更しない
  - 完了条件: docker-compose.yml に memo-mcp サービスが存在し、`${MEMO_API_KEY}` を参照、
    `8804:8804` を公開している
  - 依存: タスク7

- [ ] タスク9: ルート .env.example に MEMO_API_KEY を追記
  - 対象確定: DESIGN.md（3節・付録）が変更対象として記載する `.env` は `.gitignore` 対象で
    非コミットであるため、本タスクではコミット対象のテンプレートである `.env.example` を
    変更対象として確定させる（DESIGN の `.env` 表記は `.env.example` を指すものと解釈する）。
    実運用の `.env` への同名キー追記はコミット対象ではなく、受け入れ確認セクションの
    運用前提として扱う。
  - 内容: `.env.example` に `MEMO_API_KEY=` 行を追加し、TASK_API_KEY と同一値を設定する旨の
    コメントを付す（独立変数モデル。compose での `${TASK_API_KEY}` 直接補間はしない）
  - 完了条件: `/home/wakky/alcedo-mcp-servers/.env.example` に `MEMO_API_KEY=` が存在する
  - 依存: なし

- [ ] タスク10: ルート README.md に memo-mcp の記載を追記
  - 内容: サーバー一覧・ポート表（8804）、提供ツール（list_memos/add_memo/update_memo/delete_memo）、
    環境変数（MEMO_API_BASE_URL / MEMO_API_KEY）、起動方法（stdio / docker compose）を
    task-mcp と同じ書式で追記する
  - 完了条件: README.md に memo-mcp とポート 8804 の記載が含まれる
  - 依存: タスク6, タスク8, タスク9

---

## 受け入れ確認（実装完了後）

前提（動作確認の運用手順・コミット対象外）:
- server.py はモジュール読込時に `MEMO_API_KEY` が未設定だと `sys.exit(1)` する。したがって
  stdio 起動・docker 起動のいずれの動作確認も、事前に `MEMO_API_KEY` の設定が必須である。
- docker 起動確認の前提として、実運用の `.env`（`.gitignore` 対象・非コミット）に
  `MEMO_API_KEY`（`TASK_API_KEY` と同一値）を追記しておくこと。compose は `${MEMO_API_KEY}` を
  参照するため、`.env` に値が無いと空値補間となり起動即終了（`sys.exit(1)`）になる。
  この `.env` への追記はコミット対象ではない（タスク9 で更新するのはあくまで `.env.example`）。
  動作確認を行う環境でのローカル設定作業として実施する。
- stdio でローカル起動して確認する場合も同様に、環境変数 `MEMO_API_KEY` の設定が必要。

確認項目:
- `python3 -m py_compile memo-mcp/server.py` が構文エラーなく通る（タスク6で担保）
- `MCP_TRANSPORT=stdio` でローカル起動でき、4ツール（list_memos/add_memo/update_memo/delete_memo）が
  MCPツールとして認識される
- `docker compose up -d --build memo-mcp` でコンテナが起動する
- 受け入れシナリオ: add_memo → list_memos（一覧に含まれる）→ update_memo → delete_memo が
  例外なく成功する
