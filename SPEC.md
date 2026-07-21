# SPEC.md: obsidian-mcp サーバー追加

## 背景・目的
alcedo-mcp-serversモノレポに、Obsidian vault（`~/ObsidianAlcedoVault`、git管理済み）を
読み書きするMCPサーバー `obsidian-mcp` を追加する。task-mcpと同一パターンで実装し、
docker-compose経由でstreamable-http（ポート8801）として起動する。

## ① ユーザーとユースケース
- 利用者: リポジトリ所有者本人（wakky-alcedo）。Claude Code / claude.ai カスタムコネクタから利用。
- 用途: 複数PC（kawasemiPC等）間でObsidian vaultの内容をMCP経由で参照・追記する。
  git pull/pushにより最新状態を同期する。
- コアユースケース: 日次ノートへの追記・取得、vault内の検索・読み書き。

## ② 機能の境界
- 含む: vault_search, vault_read, vault_write, vault_append, daily_note_get, daily_note_append
- 含まない: vault_sync（明示的に不要と指示あり）、ファイル削除、添付ファイル（画像等）の扱い、
  Obsidianプラグイン固有機能（Dataview等）の解釈
- 既存システム連携: なし（vaultはgitリポジトリとして直接操作するのみ）

## ③ データと状態
- データ: Markdownファイル群（vaultディレクトリ配下）
- 永続化: gitリポジトリ（ローカルファイル + リモートリポジトリへのpush/pull）
- 複数ユーザー間共有: 複数PC間でgit push/pullにより同期（単一ユーザーが複数端末から利用）

## ④ 非機能要件
- 応答速度: 対話的ツール呼び出しなので数秒以内を想定。git pull/pushの待ち時間は許容。
- 同時利用者: 基本1人（複数端末からほぼ同時に使う可能性はあるが、競合はgit任せ）
- セキュリティ: 認証はネットワークレベル（Cloudflare Tunnel等、他サーバーと同様）。
  MCPツール自体には追加の認証は設けない（task-mcpと異なりAPIキー方式ではない）。
- 障害時: git push失敗時はエラーメッセージをツールの返り値に含めて呼び出し元に伝える
  （例外で落とさない）。

## ⑤ 制約
- 使用技術: Python, mcp[cli], shared/runner.py の起動方式を流用
- 検索: ripgrep（rg）コマンドをsubprocessから呼び出す。Dockerイメージにインストールする。
- デプロイ先: docker-srv上のDockerコンテナ。vaultディレクトリはホストからbind mount
  （`/home/wakky/ObsidianAlcedoVault:/vault`）するため、DockerfileにCOPYは不要。
- git操作: SSH鍵認証済みのため追加設定不要。subprocessでgit pull/add/commit/pushを実行。
- ポート: 8801（task-mcpの8800の次）

## ⑥ 完了の定義
- `python3 -m py_compile obsidian-mcp/server.py` が構文エラーなく通る
- `MCP_TRANSPORT=stdio` でローカル起動でき、テンプレートファイル探索処理を含め例外なく動作する
- `docker compose up -d --build` で obsidian-mcp サービスが起動する
- 受け入れシナリオ: daily_note_get(date未指定)で当日の日次ノートを取得（存在しなければ
  テンプレートから新規作成）でき、daily_note_append で指定セクション配下に追記→git pushされる

## 提供ツール仕様

### vault_search(query: str, folder: str | None = None) -> dict
- 事前に `_git_pull()`
- `rg <query> [<vault>/<folder> | <vault>]` を実行し、マッチ結果（ファイルパス・行番号・行内容）を返す

### vault_read(path: str) -> dict
- 事前に `_git_pull()`
- vault相対pathのファイル内容を返す。存在しなければエラーを返す

### vault_write(path: str, content: str) -> dict
- 指定pathへ新規作成/上書き
- 事後に `_git_push("obsidian-mcp: write {path}")`

### vault_append(path: str, content: str) -> dict
- 既存ファイル末尾に追記（存在しなければエラー）
- 事後に `_git_push("obsidian-mcp: append {path}")`

### daily_note_get(date: str | None = None) -> dict
- 事前に `_git_pull()`
- `10_Daily/YYYY-MM-DD.md` を取得。date未指定なら今日の日付
- 存在しない場合、`99_System/99_Template/` 配下から日次ノート用テンプレートを探索し、
  Templater構文のうち `tp.date.now()` 系のみ現在時刻に置換して新規作成（他の`<% %>`構文はそのまま残す）
- 事後に `_git_push("obsidian-mcp: create daily note {date}")`（新規作成時のみ）

### daily_note_append(content: str, section: str | None = None) -> dict
- 事前に `_git_pull()`
- 当日の日次ノートに追記。section指定時はその見出し配下（次の見出しの直前）に挿入。
  見出しが存在しなければファイル末尾に追記
- 事後に `_git_push("obsidian-mcp: append daily note")`

## git操作ヘルパー
- `_git_pull()`: `git -C <vault> pull` を実行。失敗しても例外にせず警告を返り値に含める設計とする
- `_git_push(message)`: `git -C <vault> add -A && git -C <vault> commit -m <message> && git -C <vault> push`
  を実行。commit対象がない場合はpushをスキップ。失敗時はエラーメッセージを返り値に含める

## 環境変数
- `VAULT_PATH`（デフォルト `/vault`、ローカル実行時は `~/ObsidianAlcedoVault` 展開）
- `GIT_USER_NAME`, `GIT_USER_EMAIL`（git commit用。vault内で `git config user.name/email` を設定）
- `MCP_TRANSPORT`, `MCP_PORT`（shared/runner.py が解釈）
