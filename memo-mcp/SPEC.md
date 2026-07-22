# SPEC.md: memo-mcp サーバー追加

## 背景・目的
alcedo-mcp-serversモノレポに、alcedo-personal-app のメモ機能（pc-serverの`/api/v1/memos`系API）を
MCPツールとして公開する `memo-mcp` を追加する。task-mcpと同一パターン（Python/FastMCP、
`shared/runner.py`経由でstdio/streamable-http切り替え）で実装し、docker-compose経由で
streamable-http（ポート8801〜8803は既存/予定で埋まっているため8804）として起動する。

task-mcpに統合せず別サーバーとする判断の経緯: ツール数だけなら統合可能な規模（統合しても
合計8ツール程度）だが、リポジトリの「1サブディレクトリ=1 MCPサーバー」規約、および
alcedo-personal-app自身がtasks.tsとmemos.tsを別リソースとして扱っている点を踏まえ、
ドメイン境界を明確にするため分離する。

## ① ユーザーとユースケース
- 利用者: リポジトリ所有者本人（wakky-alcedo）。Claude Code / claude.ai カスタムコネクタから利用。
- 用途: AI秘書システムからメモの一覧・追加・編集・削除を行う。task-mcpと同じ pc-server
  （alcedo-personal-app）を参照する。
- コアユースケース: 会話中に思いついたことをメモとして追加し、後で一覧・編集する。

## ② 機能の境界
- 含む: list_memos, add_memo, update_memo, delete_memo
- 含まない: メモの全文検索（pc-server側APIが未対応）、添付ファイル、カーソルページネーションの
  高度な制御（cursor引数は将来拡張として今回は実装しない。limit/sinceのみ）
- 既存システム連携: alcedo-personal-app pc-server の `/api/v1/memos`, `/api/v1/sync/memos`,
  `/api/v1/memos/:id` (PATCH/DELETE) を呼び出す（task-mcpと同一バックエンド）

## ③ データと状態
- データ: メモ本文（body）とオプションの出典情報（sourceUrl, sourceTitle）
- 永続化: pc-server側のSQLiteに保存される（memo-mcp自体は状態を持たない、単なるAPIラッパー）
- 複数ユーザー間共有: なし（単一ユーザーのpc-serverインスタンスに対する操作）

## ④ 非機能要件
- 応答速度: 対話的ツール呼び出しなので数秒以内を想定（task-mcpと同水準）
- 同時利用者: 基本1人
- セキュリティ: pc-server側の `X-Api-Key` ヘッダー認証を使用（task-mcpと同じ方式）。
  同一pc-serverインスタンスのため、認証キーの値自体はTASK_API_KEYと同じものを
  MEMO_API_KEYとして設定する運用とする。
- 障害時: pc-server側が404/エラーを返した場合はValueErrorを送出し、呼び出し元（Claude）に
  エラー内容を伝える（task-mcpのupdate_task_status/delete_taskと同じパターン）

## ⑤ 制約
- 使用技術: Python, mcp[cli], httpx, shared/runner.py の起動方式を流用
- デプロイ先: docker-srv上のDockerコンテナ（task-mcpと同一ネットワーク・同一pc-serverに接続）
- ポート: 8804（README記載の空き番号8801〜8803の次）
- コード構成はtask-mcp/server.pyと可能な限り同型にし、レビュー・保守コストを下げる

## ⑥ 完了の定義
- `python3 -m py_compile memo-mcp/server.py` が構文エラーなく通る
- `MCP_TRANSPORT=stdio` でローカル起動でき、4ツールがすべてMCPツールとして認識される
- `docker compose up -d --build memo-mcp` でコンテナが起動する
- 受け入れシナリオ: add_memo(body="テスト")でメモを作成 → list_memosで一覧に含まれることを確認
  → update_memoで本文を更新 → delete_memoで削除 → 一連の呼び出しが例外なく成功する

## 提供ツール仕様

### list_memos(limit: int = 50, since: str | None = None) -> dict
- `GET /api/v1/memos?limit=&since=` を呼び出す
- 戻り値: `{count: int, memos: list[dict], next_cursor: str | None}`
  （各memoは `id, body, sourceUrl, sourceTitle, version, createdAt, updatedAt` を含む）

### add_memo(body: str, source_url: str | None = None, source_title: str | None = None) -> dict
- `uuid4()` でid生成し `POST /api/v1/sync/memos` に
  `upserts:[{id, body, sourceUrl, sourceTitle, version:1, createdAt, updatedAt}]` を送信
  （task-mcpのadd_taskと同じ「新規追加はversion=1のupsertとして送る」パターン）
- 戻り値: `{id: str, body: str, result: dict}`

### update_memo(memo_id: str, body: str) -> dict
- `PATCH /api/v1/memos/{memo_id}` に `{body}` を送信
- 404の場合はValueErrorを送出
- 戻り値: `{id: str, memo: dict}`

### delete_memo(memo_id: str) -> dict
- `DELETE /api/v1/memos/{memo_id}` を呼び出す
- 404の場合はValueErrorを送出
- 戻り値: `{id: str, deleted: bool}`

## 環境変数
- `MEMO_API_BASE_URL`（デフォルト task-mcpと同じpc-server URL、例: `http://192.168.10.5:8787`）
- `MEMO_API_KEY`（pc-server起動時の`API_KEY`と同じ値。TASK_API_KEYと同一の値を設定する）
- `MCP_TRANSPORT`, `MCP_PORT`（shared/runner.py が解釈。デフォルトポートは8804）
