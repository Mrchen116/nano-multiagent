import asyncio
from pathlib import Path

from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookRunner
from agent.platform.hooks.loader import load_hooks_from_directories


def test_loaded_hooks_compose_builtin_and_workspace_layers(
    tmp_path: Path,
) -> None:
    builtins_dir = tmp_path / "builtin_hooks"
    workspace_dir = tmp_path / ".nano" / "hooks"
    builtins_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    (builtins_dir / "a_builtin.py").write_text(
        """
def setup(hooks):
    def on_turn_start(event, ctx):
        del ctx
        event["order"].append("builtin-a")
    hooks.on("turn_start", on_turn_start, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (builtins_dir / "b_builtin.py").write_text(
        """
def setup(hooks):
    def on_turn_start(event, ctx):
        del ctx
        event["order"].append("builtin-b")
    hooks.on("turn_start", on_turn_start, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "local.py").write_text(
        """
def setup(hooks):
    def on_turn_start(event, ctx):
        del ctx
        event["order"].append("workspace")
    hooks.on("turn_start", on_turn_start, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    registry, loaded = load_hooks_from_directories(
        repo_root=tmp_path,
        builtins_dir=builtins_dir,
        workspace_dir=workspace_dir,
    )

    assert [item.source for item in loaded] == ["builtin", "builtin", "workspace"]

    runner = HookRunner(registry=registry)
    payload = {"order": []}
    asyncio.run(
        runner.dispatch_observe(
            "turn_start",
            payload,
            HookContext(session_id="sess-loader", repo_root=tmp_path),
        )
    )
    assert payload["order"] == ["builtin-a", "builtin-b", "workspace"]
