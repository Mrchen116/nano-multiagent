import asyncio
from pathlib import Path

from agent.core.hooks.context import HookContext
from agent.platform.hooks.loader import load_hooks_from_directories
from agent.core.hooks.runner import HookRunner


def test_hooks_e2e_input_transform_and_session_isolated_closure_state(tmp_path: Path) -> None:
    builtins_dir = tmp_path / "builtin_hooks"
    workspace_dir = tmp_path / ".nano" / "hooks"
    builtins_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    (builtins_dir / "prefix.py").write_text(
        """
def setup(hooks):
    async def on_input(event, ctx):
        del ctx
        return {"action": "transform", "text": f"builtin:{event['text']}", "images": event.get("images")}
    hooks.on("input", on_input, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "stateful.py").write_text(
        """
def setup(hooks):
    state_by_session = {}

    def state(session_id):
        return state_by_session.setdefault(session_id, {"seen": 0})

    async def on_input(event, ctx):
        snapshot = state(ctx.session_id)
        snapshot["seen"] += 1
        return {
            "action": "transform",
            "text": f"{event['text']}|seen={snapshot['seen']}",
            "images": event.get("images"),
        }

    hooks.on("input", on_input, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    registry, loaded = load_hooks_from_directories(
        repo_root=tmp_path,
        builtins_dir=builtins_dir,
        workspace_dir=workspace_dir,
    )
    runner = HookRunner(registry=registry)

    assert len(loaded) == 2

    result_s1_first = asyncio.run(
        runner.dispatch_intercept(
            "input",
            {"text": "hello", "images": []},
            HookContext(session_id="s1", repo_root=tmp_path),
        )
    )
    result_s1_second = asyncio.run(
        runner.dispatch_intercept(
            "input",
            {"text": "hello", "images": []},
            HookContext(session_id="s1", repo_root=tmp_path),
        )
    )
    result_s2_first = asyncio.run(
        runner.dispatch_intercept(
            "input",
            {"text": "hello", "images": []},
            HookContext(session_id="s2", repo_root=tmp_path),
        )
    )

    assert result_s1_first.payload["text"] == "builtin:hello|seen=1"
    assert result_s1_second.payload["text"] == "builtin:hello|seen=2"
    assert result_s2_first.payload["text"] == "builtin:hello|seen=1"

