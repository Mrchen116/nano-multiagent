from pathlib import Path

from nano_multiagent.hooks.registry import HookRegistry
from nano_multiagent.server.routes.hook import build_event_descriptors, build_hook_descriptors


def test_build_event_descriptors_include_mode_and_return_contract() -> None:
    descriptors = build_event_descriptors()
    by_name = {item.event: item for item in descriptors}

    assert by_name["input"].mode == "intercept"
    assert "action" in by_name["input"].return_contract

    assert by_name["turn_end"].mode == "observe"
    assert by_name["turn_end"].return_contract == "none"


def test_build_hook_descriptors_include_registry_metadata() -> None:
    registry = HookRegistry()

    def on_input(payload, ctx):
        del payload, ctx
        return {"action": "continue"}

    def on_turn_end(payload, ctx):
        del payload, ctx
        return None

    registry.on(
        "input",
        on_input,
        source="workspace",
        priority=40,
        timeout_ms=900,
        module_name="hooks.workspace",
        file_path=Path("/tmp/workspace_hook.py"),
    )
    registry.on(
        "turn_end",
        on_turn_end,
        source="runtime",
        priority=60,
        timeout_ms=1200,
    )

    descriptors = build_hook_descriptors(registry)

    assert [item.event for item in descriptors] == ["input", "turn_end"]
    first = descriptors[0]
    assert first.source == "workspace"
    assert first.mode == "intercept"
    assert first.module_name == "hooks.workspace"
    assert first.file_path == "/tmp/workspace_hook.py"
    assert first.priority == 40
    assert first.timeout_ms == 900
