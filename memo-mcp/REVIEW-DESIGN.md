# REVIEW-DESIGN.md: memo-mcp/DESIGN.md 再レビュー結果

対象: `memo-mcp/DESIGN.md`（architect 修正版）
比較仕様: `memo-mcp/SPEC.md`
参照実装: `task-mcp/server.py` / `docker-compose.yml` / `shared/runner.py`

## 総評
前回の指摘3点すべてが適切に反映されている。4ツール（list_memos / add_memo /
update_memo / delete_memo）のシグネチャ・HTTPメソッド・戻り値はSPECと整合し、
ポート8804・task-mcpとの同型性も妥当。仕様ドリフトは解消された。

## 前回指摘の解消確認

### 1. MEMO_API_KEY の変数モデル（解消）
- §1・§3・付録・§5リスク表で `MEMO_API_KEY=${MEMO_API_KEY}` の独立変数参照に統一。
- `.env` に `MEMO_API_KEY` を独立定義し `TASK_API_KEY` と同一値を設定する運用を明記
  （付録の dotenv 例まで提示）。task-mcp の `TASK_API_KEY=${TASK_API_KEY}` と対称な
  変数モデルになり、SPECの「独立変数として同一値をコピー」意図と一致した。
- §5 に「変数モデル逸脱＝仕様ドリフト」リスク行が追加され、背景も残されている。

### 2. PATCH/DELETE エンドポイントの実在前提（解消）
- §5リスク表に専用行が追加され、`pc-server/src/routes/memos.ts` で
  `PATCH /api/v1/memos/:id` / `DELETE /api/v1/memos/:id` の実装を確認済みと明記。
- さらに実装フェーズ冒頭で受け入れシナリオ（add→list→update→delete）を1回通し、
  想定外の 404/405 時は sync API フォールバックを検討する保険も記載。前提が
  裏取りされ、代替方針も用意されており妥当。

### 3. 404処理の説明精度（解消）
- §4.3補足・§5リスク表とも「task-mcp と同じパターン」の表現を撤去。
- `resp.status_code == 404` を明示判定する独自方式であること、task-mcp は HTTP 404
  判定をせず一覧取得後のローカル未検出で ValueError を出す別方式である旨を正しく区別。

## その他確認事項（問題なし）
- ポート8804は server.py 補足・Dockerfile・compose・EXPOSE・risk表で一貫。
- runner のデフォルト8800を正しく認識し MCP_PORT=8804 で明示上書きする設計も正確。
- 技術スタック・依存（新規外部依存なし）・ネットワーク共有は task-mcp と同型で妥当。
- 変更対象ファイルに `.env` が追加され、ルート直下 obsidian-mcp 資材への非干渉方針も維持。

---

判定: LGTM
