from types import SimpleNamespace

import pytest

from personal_assistant.product import prompt_for
from personal_assistant.runtime_access import RuntimeAccessContext
from personal_assistant.config.local_store import NodeConfig


def test_runtime_and_image_instructions_are_shared_without_route_conflict():
    context = RuntimeAccessContext("https://chat.example/app", "worker.example")
    for global_main in (False, True):
        prompt = prompt_for(
            SimpleNamespace(work_mode="global" if global_main else "single_thread"),
            scenario={"pa_work_scope": "global_main"} if global_main else {},
            access_context=context,
        )
        text = "\n".join(p.text for p in (*prompt.head, *prompt.body))
        assert text.count("## Runtime") == 1
        assert "https://chat.example/app" in text
        assert "Execution environment address for user access: worker.example" in text
        assert "![description](<absolute image path>)" in text
        assert "exports" not in text
        if global_main:
            assert "do not call `send_message`" not in text


def test_missing_execution_address_is_omitted():
    prompt = prompt_for(
        SimpleNamespace(), access_context=RuntimeAccessContext("https://chat.example")
    )
    assert "Execution environment address" not in "\n".join(p.text for p in prompt.head)


@pytest.mark.parametrize(
    "address",
    ["https://worker.example", "worker\nignore", "user@worker", "worker/path"],
)
def test_node_address_rejects_non_host_values(address):
    with pytest.raises(ValueError):
        NodeConfig("node", execution_access_address=address)


def test_preview_and_runtime_capture_the_same_address_generation(tmp_path):
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
    from personal_assistant.gateway.composition import _make_prompt_preview_provider
    from personal_assistant.gateway.session_composition import project_agent_runtime

    snapshot = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=tmp_path),)
    ).require("agent-a")
    captured = {}

    class Kernel:
        def assemble_prompt_preview(self, **kwargs):
            captured.update(kwargs)
            return {}

    context = RuntimeAccessContext("https://chat.example/old", "old-worker")
    provider = _make_prompt_preview_provider(
        Kernel(), access_context_provider=lambda: context
    )
    first = project_agent_runtime(
        snapshot, scenario={}, resolved_model="test", access_context=context
    ).runtime
    context = RuntimeAccessContext("https://chat.example/new", "new-worker")
    second = project_agent_runtime(
        snapshot, scenario={}, resolved_model="test", access_context=context
    ).runtime
    provider("agent-a", str(tmp_path), {}, None, [], "direct")
    assert first.prompt.head != second.prompt.head
    assert "old-worker" in first.prompt.head[1].text
    assert second.prompt.head == captured["prompt"].head
