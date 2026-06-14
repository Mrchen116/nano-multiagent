"""Contract test: no new hardcoded workspace dirnames outside product defaults.py.

Per-workspace 路径治理原则:
  Any per-workspace resource path must be derived from
  <session.workspace_root> / <profile.workspace_config_dirname> / <subdir>.

  Hardcoding '.nano' / '.nanoassistant' / '.nanocode' as string literals
  for workspace-relative paths outside product defaults.py is forbidden.

This contract maintains an explicit whitelist of pre-existing legitimate usages
so that any NEW hardcode is caught immediately.

Whitelisted items document WHY they are allowed and what would need to change
to fully remove the hardcode in a future unit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Pre-existing legitimate hardcodes (platform defaults, docstring examples, etc.)
# Format: set of "relative_path:lineno" strings.
# WHY: Each entry documents the reason it's allowed.
_WHITELIST: frozenset[str] = frozenset(
    {
        # bootstrap.py: JsonlSessionStore fallback dirname — platform default, not product-specific
        # feat-388 ruff format: line shifted to 136
        "src/agent/platform/bootstrap.py:136",
        # runtime.py: tool-results dir uses .nano — platform default dir, not per-workspace
        # feat-388 ruff format: line shifted to 156; refactor-395 import logging: shifted to 159
        # feat-394-M14: _can_use_tool attr added in __init__; shifted to 165
        # refactor-406-M1: _session_prompt_slots map + register method added in __init__; shifted to 172
        "src/agent/core/agent/runtime.py:172",
        # kernel.py: build_kernel new-path workspace_config_dirname default — platform
        # default fallback when a consumer omits it (same role as jsonl_store default);
        # consumers always pass their own (.nanocode / .nanoassistant). refactor-406-M1 决策 1.
        # refactor-406-M1 R7: host_capabilities= param + _inject removed (141→137),
        # then legacy product_profile build_kernel path removed (137→122);
        # refactor-406-M2 added build_kernel skill_search_roots param + docstring (122→131).
        "src/agent/sdk/kernel.py:131",
        # skills/discovery.py: .nano skill search root — platform default, pre-185
        "src/agent/core/skills/discovery.py:45",
        # jsonl_store.py: .nano default parameter — used as fallback, not per-workspace hardcode
        # bugfix-402-M1: prepare_transcript_for_run + append_tool_call_recovery added, line shifted to 81
        "src/agent/core/session/jsonl_store.py:81",
        # tools/loader.py: .nano/tools platform dir
        # feat-388 ruff format: line shifted to 95
        "src/agent/platform/tools/loader.py:95",
        # dangerous_paths.py: .nanocode in safe-path list — correct: this references the product dirname
        "src/agent/platform/tools/dangerous_paths.py:52",
        # background tasks output: .nano/background-tasks platform dir
        # feat-388 ruff format: line shifted to 67
        "src/agent/platform/background_tasks/file_output.py:67",
        # hooks/loader.py: .nano/hooks platform dir
        # feat-388 ruff format: line shifted to 111
        "src/agent/platform/hooks/loader.py:111",
        # bash_policy.py: .nano/policy.toml platform dir
        # feat-388 ruff format: line shifted to 158
        "src/agent/platform/tools/builtins/bash_policy.py:158",
        # auto_mode_gate.py: .nanocode workspace_config_dir — this IS a hardcode, but pre-existing
        # feat-394-M7 _UNATTENDED_ORIGINS insert shifted line from 703 to 707
        "src/agent/platform/hooks/builtins/auto_mode_gate.py:707",
        # coding_cli/commands.py: .nanocode global/workspace config — CLI UX, pre-existing
        # refactor-395-M1: logging import + _log added, lines shifted to 1162/1163
        # refactor-395 ruff fix: TERMINAL_RUN_STATUSES dead import removed, lines shifted to 1164/1165
        # bugfix-402-M3 R2: finally block comment+await kernel.aclose() inserted in _async_main, lines shifted to 1166/1167
        # refactor-406-M1 R5: dead _build_llm_config_from_args removed, lines shifted to 1144/1145
        # refactor-406-M2: _build_llm_config_payload→_build_cli_llm_config (SDK-owned
        # LLMConfig.from_json/from_catalog), net +2 lines shifted to 1146/1147
        "src/coding_cli/commands.py:1146",
        "src/coding_cli/commands.py:1147",
    }
)

# Patterns to detect (as string literals in code)
_FORBIDDEN_PATTERNS = [
    '".nanoassistant"',
    '".nanocode"',
    '".nano"',
    "'.nanoassistant'",
    "'.nanocode'",
    "'.nano'",
]

# Files where these strings are legitimately allowed (product-owned dirname definition).
# refactor-406-M1: with products/ dissolved, each consumer's product.py is the new
# single definition point for its own workspace_config_dirname (决策 1/10 — the
# consumer owns its dirname). Same role the old products/*/defaults.py played.
_ALLOWED_STEMS = {"defaults", "product"}


def _collect_violations() -> list[tuple[str, int, str]]:
    violations = []
    scan_dirs = [
        _REPO_ROOT / "src" / "agent",
        _REPO_ROOT / "src" / "personal_assistant",
        _REPO_ROOT / "src" / "coding_cli",
    ]
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if py_file.stem in _ALLOWED_STEMS:
                continue
            try:
                lines = py_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            rel = str(py_file.relative_to(_REPO_ROOT))
            for lineno, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for pattern in _FORBIDDEN_PATTERNS:
                    if pattern in line:
                        key = f"{rel}:{lineno}"
                        if key not in _WHITELIST:
                            violations.append((rel, lineno, line.rstrip()))
    return violations


def test_no_new_hardcoded_workspace_dirname_in_src() -> None:
    """No NEW hardcoded workspace dirname outside product defaults.py.

    Pre-existing platform defaults are whitelisted. Any new occurrence fails
    immediately — fix by using profile.workspace_config_dirname or derive_memory_root.
    """
    violations = _collect_violations()
    if not violations:
        return

    messages = [f"  {rel}:{lineno}: {line}" for rel, lineno, line in violations]
    pytest.fail(
        "NEW hardcoded workspace dirname found outside product defaults.py "
        "(per-workspace path governance: dirnames must be defined in product defaults.py only).\n"
        "Use profile.workspace_config_dirname or core.memory.path.derive_memory_root.\n"
        "To whitelist a pre-existing legitimate use, add it to _WHITELIST with a WHY comment.\n"
        "Violations:\n" + "\n".join(messages)
    )
