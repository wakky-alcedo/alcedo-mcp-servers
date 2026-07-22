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
