# SPEC.md: homeassistant-mcp サーバー追加

## 背景・目的
alcedo-mcp-serversモノレポに、自宅のHome Assistant（`http://192.168.10.4:8123`）をMCPツールとして
公開する `homeassistant-mcp` を追加する。task-mcp/memo-mcpと同一パターン（Python/FastMCP、
`shared/runner.py`経由でstdio/streamable-http切り替え）で実装し、docker-compose経由で
streamable-http（ポート8805、README記載の空き番号8802/8803は firefly-mcp/monica-mcp用に予約済みのため
その次）として起動する。

## ① ユーザーとユースケース
- 利用者: リポジトリ所有者本人（wakky-alcedo）。Claude Code / claude.ai カスタムコネクタから利用。
- 用途: 手元PC（stdio）・スマホ含む外出先（streamable-http + Cloudflare Tunnel）の両方から、
  Home Assistant配下の家電操作とセンサー値取得を行う。
- コアユースケース: 照明・スイッチ・空調の操作と、センサー値の確認を同じくらい重視する。

## ② 機能の境界
- 含む: 状態取得（get_state, list_entities）、汎用サービス呼び出し（call_service）による
  light / switch / climate の操作、sensor値の取得、automation.trigger / scene.turn_on など
  既存の自動化・シーンの起動
- 含まない: Home Assistant自体の設定変更（configuration.yaml編集、統合の追加/削除等）、
  ユーザー・エリア・デバイス管理、通知(notify)の送信（今回はスコープ外、フェーズ2以降）、
  WebSocket API経由のイベント購読・リアルタイムプッシュ（pollingのみ）
- 既存システム連携: Home Assistant REST API（`http://192.168.10.4:8123/api/`）を
  Long-Lived Access Token（Bearer認証）で呼び出す

## ③ データと状態
- データ: entity状態（light/switch/climate/sensorの現在値）、automation/scene一覧
- 永続化: 不要。homeassistant-mcp自体は状態を持たず、都度HAに問い合わせて最新値を返す
  （履歴はHA自体のRecorder/History機能に委ねる）
- 複数ユーザー間共有: なし（単一ユーザーの自宅HAインスタンスに対する操作）

## ④ 非機能要件
- 応答速度: 対話的ツール呼び出しなので数秒以内を想定。厳密なリアルタイム性は不要
- 同時利用者: 基本1人
- セキュリティ: HA側で発行するLong-Lived Access Tokenを`HA_TOKEN`環境変数で保持し、
  `Authorization: Bearer <token>`ヘッダーで送信（task-mcpのAPIキー方式と同様の運用）
- 障害時: HAに接続できない/エラー応答の場合は例外内容をそのままツールの返り値・エラーとして
  呼び出し元に伝える。自動リトライやフォールバックは実装しない

## ⑤ 制約
- 使用技術: Python, mcp[cli], httpx, shared/runner.py の起動方式を流用（他MCPと同一構成）
- デプロイ先: docker-srv上のDockerコンテナ。ホストのLAN内にある192.168.10.4:8123へ
  到達可能なネットワーク構成であること（docker-compose上のネットワーク設定を確認）
- ポート: 8805（README記載の空き番号のうち、firefly-mcp(8802)/monica-mcp(8803)/memo-mcp(8804)の次）
- 予算・期限: 特になし

## ⑥ 完了の定義
- `python3 -m py_compile homeassistant-mcp/server.py` が構文エラーなく通る
- `MCP_TRANSPORT=stdio` でローカル起動でき、全ツールがMCPツールとして認識される
- `docker compose up -d --build homeassistant-mcp` でコンテナが起動する
- 受け入れシナリオ: light / switch / climate / sensor / automation の各ドメインで
  最低1操作ずつ（例: 指定照明のON/OFF、指定スイッチのON/OFF、指定エアコンの温度設定、
  指定センサーの現在値取得、指定automationのtrigger）が例外なく成功する

## 提供ツール仕様

### list_entities(domain: str | None = None) -> dict
- `GET /api/states` を呼び出し、`entity_id`が`domain.`で始まるものだけに絞り込む
  （domain未指定時は全件）
- 戻り値: `{count: int, entities: list[dict]}`（各entityは`entity_id, state, attributes`を含む）

### get_state(entity_id: str) -> dict
- `GET /api/states/{entity_id}` を呼び出す
- 存在しない場合はValueErrorを送出
- 戻り値: `{entity_id: str, state: str, attributes: dict, last_changed: str}`

### call_service(domain: str, service: str, entity_id: str, data: dict | None = None) -> dict
- `POST /api/services/{domain}/{service}` に `{"entity_id": entity_id, **(data or {})}` を送信
- light.turn_on / light.turn_off / switch.turn_on / switch.turn_off /
  climate.set_temperature / climate.set_hvac_mode / automation.trigger / scene.turn_on など、
  domain/serviceの組み合わせは呼び出し側（Claude）が指定する汎用ツールとする
- エラー応答（4xx/5xx）の場合はValueErrorを送出
- 戻り値: `{domain: str, service: str, entity_id: str, result: list[dict]}`

## 環境変数
- `HA_BASE_URL`（デフォルト `http://192.168.10.4:8123`）
- `HA_TOKEN`（Home Assistantの「プロフィール→セキュリティ→長期利用トークン」で発行するBearerトークン）
- `MCP_TRANSPORT`, `MCP_PORT`（shared/runner.py が解釈。デフォルトポートは8805）
