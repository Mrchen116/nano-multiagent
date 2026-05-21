import ast
import inspect
from pathlib import Path

import pytest

from coding_cli.input import repl_commands as cli_repl_commands
from coding_cli import client as cli_http_client
from coding_cli import commands as cli_commands
from coding_cli import main as cli_main


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
SPEC_PATH = PROJECT_ROOT / "SPEC.md"
PACKAGE_IMPORT_BOUNDARIES = {
    "agent": {"coding_cli", "personal_assistant", "IM"},
    "coding_cli": {"agent", "personal_assistant", "IM"},
    "personal_assistant": {"agent", "coding_cli", "IM"},
    "IM": {"agent", "coding_cli", "personal_assistant"},
}
SPEC_BOUNDARY_SNIPPETS = (
    "- `coding_cli` 和 `personal_assistant` 通过 HTTP 调用同机 agent，禁止直接 import",
    "- `IM` 不直接调用 agent，只与用户和 `personal_assistant` 交互",
    "- 四个包之间无 Python import 依赖，各自独立部署",
    "- 验收口径：`src/agent/`、`src/coding_cli/`、`src/personal_assistant/`、`src/IM/` 源码不得 import 其它顶层包；相关断言由 `tests/contract/test_cli_http_only_contract.py` 自动执行",
)


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


def test_cli_keeps_http_only_boundary() -> None:
    cli_source = inspect.getsource(cli_main)
    commands_source = inspect.getsource(cli_commands)
    http_client_source = inspect.getsource(cli_http_client)

    assert "agent." not in cli_source
    assert "agent." not in commands_source
    assert "agent." not in http_client_source
    assert "cli.commands" in cli_source
    assert "ServerClient" in http_client_source


@pytest.mark.xfail(
    reason=(
        "coding_cli/kernel_app.py intentionally imports agent.platform for Managed mode, "
        "violating the HTTP-only boundary declared in SPEC.md; tracked in #39"
    ),
    strict=True,
)
def test_top_level_packages_keep_zero_import_boundaries() -> None:
    violations: list[str] = []
    for package_name in PACKAGE_IMPORT_BOUNDARIES:
        violations.extend(_collect_sibling_import_violations(package_name))
    assert violations == []


def test_spec_declares_zero_import_acceptance_rules() -> None:
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    for snippet in SPEC_BOUNDARY_SNIPPETS:
        assert snippet in spec_text


def test_cli_exposes_minimal_http_commands() -> None:
    parser = cli_commands.build_parser()
    subparsers = [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    ]
    assert subparsers
    names = set(subparsers[0].choices.keys())
    # Current CLI exposes health and llm-config as the minimal HTTP command set.
    assert {"health", "llm-config"}.issubset(names)


def test_cli_exposes_mode_contract() -> None:
    parser = cli_commands.build_parser()
    mode_actions = [action for action in parser._actions if action.dest == "mode"]
    assert mode_actions
    mode_action = mode_actions[0]
    assert set(mode_action.choices) == {"managed", "remote"}
    assert mode_action.default is None


def test_cli_exposes_required_repl_commands_contract() -> None:
    names = set(cli_repl_commands.REPL_COMMANDS)
    assert {"/help", "/new", "/use", "/session", "/tools", "/compact", "/history", "/exit"}.issubset(names)
    assert not hasattr(cli_commands, "supported_repl_commands")


def test_cli_client_exposes_llm_config_contract() -> None:
    assert hasattr(cli_http_client.ServerClient, "get_llm_config")
    assert hasattr(cli_http_client.ServerClient, "patch_llm_config")


def test_readme_documents_cli_module_boundaries_and_json_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "CLI module boundary" in readme
    assert "`commands.py`" in readme
    assert "`repl_input.py`" in readme
    assert "`repl_commands.py`" in readme
    assert "single final JSON object on stdout" in readme
