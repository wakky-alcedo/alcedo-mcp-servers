# alcedo-mcp-servers

AI秘書システムのために自作しているMCPサーバー群。モノレポ構成。

## 構成方針

各サブディレクトリが1つのMCPサーバーに対応する。すべて Python (FastMCP) で統一し、
共通処理は `shared/` に置いて各サーバーから import する。

```
alcedo-mcp-servers/
├── task-mcp/        alcedo-personal-app のタスクAPIをラップ
├── firefly-mcp/      (予定) Firefly III 連携
├── monica-mcp/        (予定) Monica 連携
├── shared/            共通ヘルパー（起動方式の切り替え等）
├── docker-compose.yml 全サーバーをまとめて起動
└── README.md
```

## 起動方式

各サーバーは環境変数 `MCP_TRANSPORT` で起動方式を切り替える。

| 値 | 用途 |
|---|---|
| `stdio` (デフォルト) | 手元PCのClaude Code等からローカルプロセスとして起動 |
| `streamable-http` | docker-srv上に常駐させ、Cloudflare Tunnel経由で claude.ai のカスタムコネクタやスマホアプリから接続 |

## 新しいMCPサーバーを追加する手順

1. `xxx-mcp/` フォルダを作成し、`server.py` を実装（`shared.runner.run_server` を使う）
2. `xxx-mcp/requirements.txt` を作成
3. `xxx-mcp/Dockerfile` を `task-mcp/Dockerfile` をコピーして作成（ポート番号だけ変更）
4. ルートの `docker-compose.yml` にサービスを追記（ポートは 8801, 8802... と空いている番号を割り当てる）

## デプロイ（docker-srv上）

```bash
git clone https://github.com/wakky-alcedo/alcedo-mcp-servers.git
cd alcedo-mcp-servers
cp .env.example .env  # TASK_API_KEY 等を設定
docker compose up -d --build
```

## 各サーバーの詳細

- [task-mcp/README.md](./task-mcp/README.md)（予定）
