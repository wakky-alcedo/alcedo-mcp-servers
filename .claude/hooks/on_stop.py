#!/usr/bin/env python3
"""エージェントが停止した時にDONE.mdがなければ続きを促すHook"""

import sys
import json
import shutil
import subprocess
from pathlib import Path

hook_input = json.loads(sys.stdin.read())

# SubagentStop の場合はメインセッションの再起動をしない（多重起動防止）
if hook_input.get("hook_event_name") == "SubagentStop":
    sys.exit(0)

cwd = hook_input.get("cwd", ".")
done_path = Path(cwd) / "DONE.md"
plan_path = Path(cwd) / "PLAN.md"

if done_path.exists():
    sys.exit(0)

if not plan_path.exists():
    sys.exit(0)

# PLAN.mdに未チェック項目があるか確認
plan_content = plan_path.read_text(encoding="utf-8")
has_unchecked = "- [ ]" in plan_content

if not has_unchecked:
    sys.exit(0)

# 未完了タスクがある場合のみ再起動
if not shutil.which("claude"):
    sys.exit(0)

subprocess.run(
    [
        "claude",
        "--dangerously-skip-permissions",
        "PLAN.mdを確認して未完了タスクの実装を続けてください。SPEC.mdを参照して仕様ドリフトがないか確認してから進めること。",
    ],
    cwd=cwd,
    encoding="utf-8",
)
