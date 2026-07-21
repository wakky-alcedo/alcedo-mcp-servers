#!/usr/bin/env python3
"""ファイル書き込み後に自動でlint/フォーマットを実行するHook"""

import sys
import json
import shutil
import subprocess
from pathlib import Path

hook_input = json.loads(sys.stdin.read())
tool_input = hook_input.get("tool_input", {})
file_path = tool_input.get("file_path", "")

if not file_path:
    sys.exit(0)

path = Path(file_path)

if path.suffix == ".py":
    if shutil.which("black"):
        subprocess.run(["black", file_path], capture_output=True, timeout=30)
    if shutil.which("flake8"):
        result = subprocess.run(
            ["flake8", "--max-line-length=100", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"[Hook] flake8 errors in {file_path}:\n{result.stdout}", file=sys.stderr)

elif path.suffix in (".ts", ".tsx", ".js", ".jsx"):
    if shutil.which("npx"):
        subprocess.run(
            ["npx", "eslint", "--fix", file_path],
            capture_output=True,
            timeout=30,
        )

elif path.suffix in (".json",):
    try:
        with open(file_path, encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        print(f"[Hook] JSON syntax error in {file_path}: {e}", file=sys.stderr)
