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

## `.mcp.json` の設定

各プロジェクトの `.mcp.json`（または `~/.claude/settings.json` の `mcpServers`）に以下を記載する。

### Claude Code から HTTP で接続する場合（docker-srv 上のコンテナに繋ぐ）

```json
{
  "mcpServers": {
    "task-mcp": {
      "type": "http",
      "url": "http://<docker-srv-ip>:8800/mcp"
    },
    "obsidian-mcp": {
      "type": "http",
      "url": "http://<docker-srv-ip>:8801/mcp"
    },
    "memo-mcp": {
      "type": "http",
      "url": "http://<docker-srv-ip>:8804/mcp"
    }
  }
}
```

> `<docker-srv-ip>` は docker-srv の LAN 上の IP アドレス（例: `192.168.10.5`）。

### claude.ai カスタムコネクタ（Cloudflare Tunnel 経由）

claude.ai の Settings → Integrations → Add custom integration で以下を入力する。

| サーバー | URL |
|---|---|
| task-mcp | `https://<tunnel-subdomain>.trycloudflare.com/mcp` |
| obsidian-mcp | `https://<tunnel-subdomain-2>.trycloudflare.com/mcp` |
| memo-mcp | `https://<tunnel-subdomain-3>.trycloudflare.com/mcp` |

> Cloudflare Tunnel の subdomain は `cloudflared tunnel route` で払い出したもの。

### stdio モードでローカル実行する場合（開発・デバッグ用）

```json
{
  "mcpServers": {
    "task-mcp": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/alcedo-mcp-servers/task-mcp/server.py"],
      "env": {
        "TASK_API_BASE_URL": "http://192.168.10.5:8787",
        "TASK_API_KEY": "your-api-key"
      }
    },
    "memo-mcp": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/alcedo-mcp-servers/memo-mcp/server.py"],
      "env": {
        "MEMO_API_BASE_URL": "http://192.168.10.5:8787",
        "MEMO_API_KEY": "your-api-key"
      }
    }
  }
}
```

### サーバー一覧とポート対応

| サービス名 | ポート | 状態 |
|---|---|---|
| task-mcp | 8800 | 稼働中 |
| obsidian-mcp | 8801 | 実装予定 (SPEC.md 参照) |
| firefly-mcp | 8802 | 未着手 |
| monica-mcp | 8803 | 未着手 |
| memo-mcp | 8804 | 稼働中 |

## 各サーバーの詳細

- [task-mcp/README.md](./task-mcp/README.md)（予定）
- [memo-mcp/README.md](./memo-mcp/README.md)（予定）

### memo-mcp

alcedo-personal-app pc-server の `/api/v1/memos` 系APIをラップする、task-mcp と同一パターン
（Python/FastMCP、`shared/runner.py` 経由でstdio/streamable-http切り替え）のMCPサーバー。

提供ツール:

- `list_memos(limit, since)` - メモ一覧を取得する
- `add_memo(body, source_url, source_title)` - 新規メモを追加する
- `update_memo(memo_id, body)` - 既存メモの本文を更新する
- `delete_memo(memo_id)` - メモを削除する

環境変数:

- `MEMO_API_BASE_URL` - pc-server の接続先URL（例: `http://192.168.10.5:8787`）
- `MEMO_API_KEY` - pc-server の `X-Api-Key` 認証用キー（`TASK_API_KEY` と同じ値を設定する）
