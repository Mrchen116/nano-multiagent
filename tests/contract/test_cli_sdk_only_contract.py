"""Guard top-level package imports and the current CLI surface."""

from pathlib import Path

from coding_cli import commands as cli_commands
from coding_cli.input import repl_commands as cli_repl_commands
from tests.contract.import_rules import ImportReference, forbidden_imports


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
_SIBLING_FORBIDDEN_PREFIXES: dict[str, tuple[str, ...]] = {
    "agent": ("coding_cli", "personal_assistant", "IM"),
    "coding_cli": ("personal_assistant", "IM"),
    "personal_assistant": ("coding_cli", "IM"),
    "IM": ("agent", "coding_cli", "personal_assistant"),
}


def _render(reference: ImportReference) -> str:
    return (
        f"{reference.path.relative_to(PROJECT_ROOT)}:{reference.line}: "
        f"imports {reference.module}"
    )


def test_top_level_packages_keep_zero_import_boundaries() -> None:
    """Top-level deployable packages must not import sibling products."""
    violations = [
        reference
        for package_name, forbidden in _SIBLING_FORBIDDEN_PREFIXES.items()
        for reference in forbidden_imports(SOURCE_ROOT / package_name, forbidden)
    ]
    assert not violations, (
        "Top-level packages must not import each other directly:\n"
        + "\n".join(f"  {_render(reference)}" for reference in violations)
    )


def test_cli_exposes_sdk_subcommands() -> None:
    """CLI parser must expose only current kernel configuration commands."""
    parser = cli_commands.build_parser()
    subparsers = [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    ]
    assert subparsers
    names = set(subparsers[0].choices.keys())
    assert "llm-config" in names
    assert "health" not in names


def test_cli_has_no_mode_flag() -> None:
    """The local in-process CLI must not expose remote kernel modes."""
    parser = cli_commands.build_parser()
    mode_actions = [action for action in parser._actions if action.dest == "mode"]
    assert not mode_actions


def test_cli_exposes_required_repl_commands_contract() -> None:
    names = set(cli_repl_commands.REPL_COMMANDS)
    assert {
        "/help",
        "/new",
        "/use",
        "/session",
        "/tools",
        "/compact",
        "/history",
        "/exit",
    }.issubset(names)
    assert not hasattr(cli_commands, "supported_repl_commands")
