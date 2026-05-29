"""CLI 架构边界合约测试 (refactor-387 M2).

M2 后：CLI 从「只通过 HTTP 访问内核」变为「只通过 agent.sdk 访问内核」。
- agent.core / agent.platform 内部仍禁止直接 import
- agent.sdk 是唯一合法接触点
- --mode/--base-url/health 子命令已删除
"""

import ast
import inspect
from pathlib import Path

import pytest

from coding_cli.input import repl_commands as cli_repl_commands
from coding_cli import commands as cli_commands
from coding_cli import main as cli_main


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
SPEC_PATH = PROJECT_ROOT / "SPEC.md"

# M2: coding_cli may import agent.sdk but NOT agent.core or agent.platform internals.
# Only agent.sdk is the allowed surface; all other agent.* sub-packages are internal.
_FORBIDDEN_CLI_AGENT_INTERNALS = (
    "agent.core",
    "agent.platform",
    "agent.products",
)


def _collect_cli_agent_internal_imports(package_name: str = "coding_cli") -> list[str]:
    """Find coding_cli imports of agent.core/platform/products (forbidden after M2)."""
    package_root = SOURCE_ROOT / package_name
    violations: list[str] = []
    for file_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name.startswith(forbidden) for forbidden in _FORBIDDEN_CLI_AGENT_INTERNALS):
                        relative_path = file_path.relative_to(PROJECT_ROOT)
                        violations.append(f"{relative_path}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if any(node.module.startswith(forbidden) for forbidden in _FORBIDDEN_CLI_AGENT_INTERNALS):
                    relative_path = file_path.relative_to(PROJECT_ROOT)
                    violations.append(f"{relative_path}:{node.lineno} imports {node.module}")
    return violations


def test_cli_only_uses_agent_sdk_not_agent_internals() -> None:
    """coding_cli must not import agent.core / agent.platform / agent.products directly.

    agent.sdk is the only allowed surface (refactor-387 M2).
    kernel_app.py and managed_server.py are still present in the source but will be
    deleted in M4; they are excluded from this check as they are being phased out.
    """
    violations = _collect_cli_agent_internal_imports()
    # Exclude files that are known to be phased out in M4.
    m4_phase_out = {"src/coding_cli/kernel_app.py"}
    relevant_violations = [
        v for v in violations
        if not any(phase_out in v for phase_out in m4_phase_out)
    ]
    assert relevant_violations == [], (
        "coding_cli must not import agent.core/platform/products directly.\n"
        "These files violate the agent.sdk-only boundary:\n"
        + "\n".join(f"  {v}" for v in relevant_violations)
    )


def test_cli_main_module_delegates_to_commands() -> None:
    """main.py must delegate to commands via run_cli."""
    cli_source = inspect.getsource(cli_main)
    assert "cli.commands" in cli_source


PACKAGE_IMPORT_BOUNDARIES = {
    "agent": {"coding_cli", "personal_assistant", "IM"},
    "coding_cli": {"agent", "personal_assistant", "IM"},
    "personal_assistant": {"agent", "coding_cli", "IM"},
    "IM": {"agent", "coding_cli", "personal_assistant"},
}


def _collect_sibling_import_violations(package_name: str) -> list[str]:
    package_root = SOURCE_ROOT / package_name
    forbidden_roots = PACKAGE_IMPORT_BOUNDARIES[package_name]
    violations: list[str] = []
    for file_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            imported_root: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_root = alias.name.split(".", 1)[0]
                    if imported_root in forbidden_roots:
                        relative_path = file_path.relative_to(PROJECT_ROOT)
                        violations.append(f"{relative_path}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_root = node.module.split(".", 1)[0]
                if imported_root in forbidden_roots:
                    relative_path = file_path.relative_to(PROJECT_ROOT)
                    violations.append(f"{relative_path}:{node.lineno} imports {node.module}")
    return violations


@pytest.mark.xfail(
    reason=(
        "coding_cli/kernel_app.py intentionally imports agent.platform for Managed mode, "
        "violating the HTTP-only boundary declared in SPEC.md; tracked in #39. "
        "This file is being deleted in M4."
    ),
    strict=True,
)
def test_top_level_packages_keep_zero_import_boundaries() -> None:
    """Full zero-import boundary check (kept as xfail pending M4 cleanup)."""
    violations: list[str] = []
    for package_name in PACKAGE_IMPORT_BOUNDARIES:
        violations.extend(_collect_sibling_import_violations(package_name))
    assert violations == []


@pytest.mark.xfail(
    reason=(
        "SPEC.md §5 boundary snippets reference old HTTP arch (coding_cli 通过 HTTP 调用); "
        "doc cleanup is in M4. Tracked in #39 / refactor-387-M4."
    ),
    strict=True,
)
def test_spec_declares_zero_import_acceptance_rules() -> None:
    """SPEC.md must describe M4 target state boundary rules (xfail pending M4 doc)."""
    SPEC_BOUNDARY_SNIPPETS = (
        "- `coding_cli` 和 `personal_assistant` 通过 HTTP 调用同机 agent，禁止直接 import",
        "- `IM` 不直接调用 agent，只与用户和 `personal_assistant` 交互",
        "- 四个包之间无 Python import 依赖，各自独立部署",
        "- 验收口径：`src/agent/`、`src/coding_cli/`、`src/personal_assistant/`、`src/IM/` 源码不得 import 其它顶层包；相关断言由 `tests/contract/test_cli_http_only_contract.py` 自动执行",
    )
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    for snippet in SPEC_BOUNDARY_SNIPPETS:
        assert snippet in spec_text


def test_cli_exposes_sdk_subcommands() -> None:
    """CLI parser must expose llm-config subcommand (health removed in M2)."""
    parser = cli_commands.build_parser()
    subparsers = [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    ]
    assert subparsers
    names = set(subparsers[0].choices.keys())
    assert "llm-config" in names
    # health is gone (HTTP-only command removed in M2)
    assert "health" not in names, "health subcommand should have been removed in M2"


def test_cli_has_no_mode_flag() -> None:
    """--mode flag must be absent after M2 (managed/remote modes removed)."""
    parser = cli_commands.build_parser()
    mode_actions = [action for action in parser._actions if action.dest == "mode"]
    assert not mode_actions, "--mode should have been removed in M2"


def test_cli_exposes_required_repl_commands_contract() -> None:
    names = set(cli_repl_commands.REPL_COMMANDS)
    assert {"/help", "/new", "/use", "/session", "/tools", "/compact", "/history", "/exit"}.issubset(names)
    assert not hasattr(cli_commands, "supported_repl_commands")


def test_readme_documents_cli_module_boundaries_and_json_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "CLI module boundary" in readme
    assert "`commands.py`" in readme
    assert "`repl_input.py`" in readme
    assert "`repl_commands.py`" in readme
    assert "single final JSON object on stdout" in readme
