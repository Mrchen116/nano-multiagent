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
_WHITELIST: frozenset[str] = frozenset({
    # bootstrap.py: JsonlSessionStore fallback dirname — platform default, not product-specific
    "src/agent/platform/bootstrap.py:133",
    # runtime.py: tool-results dir uses .nano — platform default dir, not per-workspace
    "src/agent/core/agent/runtime.py:131",
    # skills/discovery.py: .nano skill search root — platform default, pre-185
    "src/agent/core/skills/discovery.py:45",
    # jsonl_store.py: .nano default parameter — used as fallback, not per-workspace hardcode
    "src/agent/core/session/jsonl_store.py:75",
    # tools/loader.py: .nano/tools platform dir
    "src/agent/platform/tools/loader.py:91",
    # dangerous_paths.py: .nanocode in safe-path list — correct: this references the product dirname
    "src/agent/platform/tools/dangerous_paths.py:52",
    # background tasks output: .nano/background-tasks platform dir
    "src/agent/platform/background_tasks/file_output.py:61",
    # hooks/loader.py: .nano/hooks platform dir
    "src/agent/platform/hooks/loader.py:101",
    # bash_policy.py: .nano/policy.toml platform dir
    "src/agent/platform/tools/builtins/bash_policy.py:159",
    # auto_mode_gate.py: .nanocode workspace_config_dir — this IS a hardcode, but pre-existing
    "src/agent/platform/hooks/builtins/auto_mode_gate.py:679",
    # coding_cli/commands.py: .nanocode global/workspace config — CLI UX, pre-existing
    "src/coding_cli/commands.py:655",
    "src/coding_cli/commands.py:659",
})

# Patterns to detect (as string literals in code)
_FORBIDDEN_PATTERNS = ['".nanoassistant"', '".nanocode"', '".nano"',
                       "'.nanoassistant'", "'.nanocode'", "'.nano'"]

# Files where these strings are legitimately allowed (product defaults, docstrings)
_ALLOWED_STEMS = {"defaults"}


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
