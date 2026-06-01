#!/usr/bin/env python3
# feat-388 触点 (a)：PostToolUse hook，在 Edit/Write 后对 src/|tests/ 下的 .py 文件
# 运行 ruff format + ruff check --fix（自动修），余下不可修违规 exit 2 回喂。
# src/ 下文件额外跑边界契约测试给 R1/R2/R3 即时反馈。
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

data = json.loads(sys.stdin.read())

# PostToolUse hook: tool_input 里有 file_path
tool_input = data.get("tool_input", {}) or {}
file_path_str = tool_input.get("file_path", "") or ""

if not file_path_str:
    sys.exit(0)

file_path = Path(file_path_str)

# 只处理 src/ 或 tests/ 下的 .py 文件
try:
    relative = file_path.relative_to(REPO_ROOT)
except ValueError:
    sys.exit(0)

parts = relative.parts
if not parts:
    sys.exit(0)

top_dir = parts[0]
if top_dir not in ("src", "tests"):
    sys.exit(0)

if file_path.suffix != ".py":
    sys.exit(0)

if not file_path.exists():
    sys.exit(0)

# Step 1: ruff format（autofix，静默）
subprocess.run(
    ["ruff", "format", str(file_path)],
    capture_output=True,
    cwd=str(REPO_ROOT),
)

# Step 2: ruff check --fix（autofix correctness，静默）
subprocess.run(
    ["ruff", "check", "--fix", str(file_path)],
    capture_output=True,
    cwd=str(REPO_ROOT),
)

# Step 3: 检查余下不可自动修的违规（用 returncode 而非 stdout 判断；exit 0 = clean）
lint_result = subprocess.run(
    ["ruff", "check", str(file_path)],
    capture_output=True,
    text=True,
    cwd=str(REPO_ROOT),
)

violations = lint_result.stdout.strip() if lint_result.returncode != 0 else ""

# Step 4: src/ 下额外跑边界契约测试（AST 检查极快，毫秒级）
contract_violations = ""
if top_dir == "src":
    contract_result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/contract/test_cli_http_only_contract.py",
            "tests/contract/test_core_no_platform_imports.py",
            "-q",
            "--tb=short",
            "--no-header",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if contract_result.returncode != 0:
        contract_violations = contract_result.stdout + contract_result.stderr

if violations or contract_violations:
    parts_out = []
    if violations:
        parts_out.append(f"[ruff] {file_path_str}\n{violations}")
    if contract_violations:
        parts_out.append(f"[contract] 边界契约测试失败:\n{contract_violations}")
    print("\n\n".join(parts_out), file=sys.stderr)
    sys.exit(2)

sys.exit(0)
