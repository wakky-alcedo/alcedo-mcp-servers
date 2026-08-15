"""
タスクMCPサーバー

alcedo-personal-app の pc-server (Fastify, /api/v1) をMCPツールとして公開する。
認証は X-Api-Key ヘッダー方式。

環境変数:
  TASK_API_BASE_URL   例: http://192.168.10.5:3000   (pc-serverのベースURL)
  TASK_API_KEY         pc-server起動時の API_KEY と同じ値
"""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("TASK_API_BASE_URL", "http://192.168.10.5:8787").rstrip("/")
API_KEY = os.environ.get("TASK_API_KEY")

if not API_KEY:
    print("ERROR: TASK_API_KEY が設定されていません", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("task-mcp")


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"},
        timeout=10.0,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _flatten(tasks: list[dict], depth: int = 0) -> list[dict]:
    """サブタスクを含む木構造を、人間が読みやすいフラットなリストに変換する"""
    out = []
    for t in tasks:
        out.append(
            {
                "id": t["id"],
                "title": t["title"],
                "status": t["status"],
                "priority": t["priority"],
                "dueAt": t.get("dueAt"),
                "dueTime": t.get("dueTime"),
                "category": t.get("categoryName"),
                "depth": depth,
            }
        )
        if t.get("subtasks"):
            out.extend(_flatten(t["subtasks"], depth + 1))
    return out


@mcp.tool()
def list_tasks(include_done: bool = False) -> dict[str, Any]:
    """
    タスク一覧を取得する。

    Args:
        include_done: 完了済み(done)のタスクも含めるか。デフォルトは未完了のみ。

    Returns:
        タスクのフラットなリスト（サブタスクも depth 付きで展開される）
    """
    with _client() as c:
        resp = c.get("/api/v1/tasks")
        resp.raise_for_status()
        data = resp.json()

    flat = _flatten(data.get("tasks", []))
    if not include_done:
        flat = [t for t in flat if t["status"] != "done"]

    return {"count": len(flat), "tasks": flat}


@mcp.tool()
def add_task(
    title: str,
    category_name: str = "default",
    category_type: str = "short_term",
    priority: str = "medium",
    due_at: Optional[str] = None,
    due_time: Optional[str] = None,
    description: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    新しいタスクを追加する。

    Args:
        title: タスク名（必須）
        category_name: カテゴリ名（例: "仕事", "買い物"）。未指定なら "default"
        category_type: "short_term"（短期） or "long_term"（長期）
        priority: "low" / "medium" / "high"
        due_at: 期限日 (ISO 8601, 例: "2026-07-01") 。なければ省略可
        due_time: 期限時刻 (例: "18:00")。なければ省略可
        description: タスクの詳細説明
        parent_id: 親タスクのID（list_tasksで取得したid）。指定するとそのタスクの
            サブタスクとして作成される。省略するとトップレベルのタスクになる。

    Returns:
        作成したタスクのID等
    """
    if parent_id is not None:
        with _client() as c:
            resp = c.get("/api/v1/tasks")
            resp.raise_for_status()
            parent = _find_task_recursive(resp.json().get("tasks", []), parent_id)
        if parent is None:
            raise ValueError(f"親タスクが見つかりません: {parent_id}")

    task_id = str(uuid4())
    payload = {
        "upserts": [
            {
                "id": task_id,
                "title": title,
                "description": description,
                "categoryType": category_type,
                "categoryName": category_name,
                "priority": priority,
                "dueAt": due_at,
                "dueTime": due_time,
                "parentId": parent_id,
                "status": "todo",
                "updatedAt": _now_iso(),
                "version": 1,
            }
        ]
    }
    with _client() as c:
        resp = c.post("/api/v1/sync/tasks", json=payload)
        resp.raise_for_status()
        result = resp.json()

    return {"id": task_id, "title": title, "result": result}


@mcp.tool()
def update_task_status(task_id: str, status: str) -> dict[str, Any]:
    """
    タスクのステータスを更新する。

    Args:
        task_id: 対象タスクのID（list_tasksで取得したid）
        status: "todo" / "doing" / "done" のいずれか

    Returns:
        更新結果
    """
    if status not in ("todo", "doing", "done"):
        raise ValueError("status は todo / doing / done のいずれかである必要があります")

    # 現在のタスク情報を取得して、必要なフィールドを引き継いだ上で更新する
    with _client() as c:
        resp = c.get("/api/v1/tasks")
        resp.raise_for_status()
        all_tasks = _flatten(resp.json().get("tasks", []), 0)
        # 元の完全なレコードを取得するため、もう一度ツリーから探す
        target = _find_task_recursive(resp.json().get("tasks", []), task_id)

    if target is None:
        raise ValueError(f"タスクが見つかりません: {task_id}")

    payload = {
        "upserts": [
            {
                "id": target["id"],
                "title": target["title"],
                "description": target.get("description"),
                "categoryType": target["categoryType"],
                "categoryName": target["categoryName"],
                "priority": target["priority"],
                "dueAt": target.get("dueAt"),
                "dueTime": target.get("dueTime"),
                "status": status,
                "updatedAt": _now_iso(),
                "version": target.get("version", 1) + 1,
            }
        ]
    }
    with _client() as c:
        resp = c.post("/api/v1/sync/tasks", json=payload)
        resp.raise_for_status()
        result = resp.json()

    return {"id": task_id, "new_status": status, "result": result}


def _find_task_recursive(tasks: list[dict], task_id: str) -> Optional[dict]:
    for t in tasks:
        if t["id"] == task_id:
            return t
        if t.get("subtasks"):
            found = _find_task_recursive(t["subtasks"], task_id)
            if found:
                return found
    return None


@mcp.tool()
def delete_task(task_id: str) -> dict[str, Any]:
    """
    タスクを削除する（論理削除。statusがdoneになりdeletedAtが立つ）。

    Args:
        task_id: 削除するタスクのID
    """
    payload = {
        "deletions": [
            {
                "id": task_id,
                "updatedAt": _now_iso(),
                "version": 999999,  # 既存レコードより必ず新しいバージョンにするため大きな値を使う
            }
        ]
    }
    with _client() as c:
        resp = c.post("/api/v1/sync/tasks", json=payload)
        resp.raise_for_status()
        result = resp.json()

    return {"id": task_id, "result": result}


if __name__ == "__main__":
    # MCP_TRANSPORT 環境変数で stdio / streamable-http を切り替える。
    # 詳細は shared/runner.py を参照。
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared.runner import run_server

    run_server(mcp)
