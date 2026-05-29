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

    agent.sdk is the only allowed surface (refactor-387 M2/M4).
    Dead HTTP files (kernel_app.py, client.py, managed_server.py, session_stream.py)
    deleted in M4; no exclusions needed.
    """
    violations = _collect_cli_agent_internal_imports()
    # M4: kernel_app.py and all other dead HTTP files deleted; no more exclusions.
    assert violations == [], (
        "coding_cli must not import agent.core/platform/products directly.\n"
        "These files violate the agent.sdk-only boundary:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_cli_main_module_delegates_to_commands() -> None:
    """main.py must delegate to commands via run_cli."""
    cli_source = inspect.getsource(cli_main)
    assert "cli.commands" in cli_source


# Products (coding_cli / personal_assistant) may ONLY import agent.sdk; all other
# agent.* sub-packages are forbidden (agent.core, agent.platform, agent.products).
# IM and agent internals keep the old full-root boundary.
_SIBLING_FORBIDDEN_PREFIXES: dict[str, tuple[str, ...]] = {
    # agent must never import products
    "agent": ("coding_cli", "personal_assistant", "IM"),
    # products must not import agent.core/platform/products — only agent.sdk
    "coding_cli": ("agent.core", "agent.platform", "agent.products", "personal_assistant", "IM"),
    "personal_assistant": ("agent.core", "agent.platform", "agent.products", "coding_cli", "IM"),
    # IM must not import agent at all, nor sibling products
    "IM": ("agent", "coding_cli", "personal_assistant"),
}

# Keep for backward compat (used in test function name)
PACKAGE_IMPORT_BOUNDARIES = {
    "agent": {"coding_cli", "personal_assistant", "IM"},
    "coding_cli": {"agent", "personal_assistant", "IM"},
    "personal_assistant": {"agent", "coding_cli", "IM"},
    "IM": {"agent", "coding_cli", "personal_assistant"},
}


def _collect_sibling_import_violations(package_name: str) -> list[str]:
    """Check package imports against the refined forbidden-prefix table."""
    package_root = SOURCE_ROOT / package_name
    forbidden_prefixes = _SIBLING_FORBIDDEN_PREFIXES.get(package_name, ())
    violations: list[str] = []
    for file_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name == p or alias.name.startswith(p + ".") for p in forbidden_prefixes):
                        relative_path = file_path.relative_to(PROJECT_ROOT)
                        violations.append(f"{relative_path}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                module = node.module
                if any(module == p or module.startswith(p + ".") for p in forbidden_prefixes):
                    relative_path = file_path.relative_to(PROJECT_ROOT)
                    violations.append(f"{relative_path}:{node.lineno} imports {module}")
    return violations


def test_top_level_packages_keep_zero_import_boundaries() -> None:
    """Full zero-import boundary check — active after M4 cleanup (Closes #39).

    coding_cli/kernel_app.py (which violated the HTTP-only boundary) was deleted
    in M4; this test is now a hard assertion with no xfail.
    """
    violations: list[str] = []
    for package_name in PACKAGE_IMPORT_BOUNDARIES:
        violations.extend(_collect_sibling_import_violations(package_name))
    assert violations == [], (
        "Top-level packages must not import each other directly:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_spec_declares_sdk_only_boundary_rules() -> None:
    """SPEC.md §5 must declare the post-M4 agent.sdk-only boundary rules.

    These are the NEW rules that replace the old HTTP-only boundary snippets.
    Verifies that the final SPEC.md reflects the refactor-387 target architecture
    (#39 Closes: products only import agent.sdk, not agent.core/platform).
    """
    SPEC_BOUNDARY_SNIPPETS = (
        # §5 dependency rules — new agent.sdk-only phrasing (exact text from SPEC.md §5)
        "coding_cli` 和 `personal_assistant` 通过 **`import agent.sdk` 进程内调用** agent",
        "**只允许 import `agent.sdk`**，禁止 import `agent.core` / `agent.platform` 内部模块",
        # Verification clause
        "test_cli_http_only_contract.py",
    )
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    for snippet in SPEC_BOUNDARY_SNIPPETS:
        assert snippet in spec_text, f"SPEC.md missing M4 boundary rule: {snippet!r}"


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
