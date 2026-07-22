"""
メモMCPサーバー

alcedo-personal-app の pc-server (Fastify, /api/v1) のメモAPIをMCPツールとして公開する。
認証は X-Api-Key ヘッダー方式。

環境変数:
  MEMO_API_BASE_URL   例: http://192.168.10.5:8787   (pc-serverのベースURL)
  MEMO_API_KEY         pc-server起動時の API_KEY と同じ値
"""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("MEMO_API_BASE_URL", "http://192.168.10.5:8787").rstrip("/")
API_KEY = os.environ.get("MEMO_API_KEY")

if not API_KEY:
    print("ERROR: MEMO_API_KEY が設定されていません", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("memo-mcp")


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"},
        timeout=10.0,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def list_memos(limit: int = 50, since: Optional[str] = None) -> dict[str, Any]:
    """
    メモ一覧を取得する。

    Args:
        limit: 取得件数の上限。デフォルトは50
        since: この日時以降に更新されたメモのみ取得する (ISO 8601)。省略可

    Returns:
        メモのリストと次ページ用カーソル
    """
    params: dict[str, Any] = {"limit": limit}
    if since is not None:
        params["since"] = since

    with _client() as c:
        resp = c.get("/api/v1/memos", params=params)
        resp.raise_for_status()
        data = resp.json()

    memos = data.get("memos", [])
    return {"count": len(memos), "memos": memos, "next_cursor": data.get("nextCursor")}


@mcp.tool()
def add_memo(
    body: str,
    source_url: Optional[str] = None,
    source_title: Optional[str] = None,
) -> dict[str, Any]:
    """
    新しいメモを追加する。

    Args:
        body: メモ本文（必須）
        source_url: 出典URL。なければ省略可
        source_title: 出典タイトル。なければ省略可

    Returns:
        作成したメモのID等
    """
    memo_id = str(uuid4())
    now = _now_iso()
    payload = {
        "upserts": [
            {
                "id": memo_id,
                "body": body,
                "sourceUrl": source_url,
                "sourceTitle": source_title,
                "version": 1,
                "createdAt": now,
                "updatedAt": now,
            }
        ]
    }
    with _client() as c:
        resp = c.post("/api/v1/sync/memos", json=payload)
        resp.raise_for_status()
        result = resp.json()

    return {"id": memo_id, "body": body, "result": result}


@mcp.tool()
def update_memo(memo_id: str, body: str) -> dict[str, Any]:
    """
    既存のメモ本文を更新する。

    Args:
        memo_id: 更新対象のメモID
        body: 更新後のメモ本文

    Returns:
        更新後のメモ情報
    """
    with _client() as c:
        resp = c.patch(f"/api/v1/memos/{memo_id}", json={"body": body})
        if resp.status_code == 404:
            raise ValueError(f"メモが見つかりません: {memo_id}")
        resp.raise_for_status()
        data = resp.json()

    return {"id": memo_id, "memo": data.get("memo")}
