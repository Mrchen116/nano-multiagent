from pathlib import Path

import pytest

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.errors import ToolError
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.loader import load_hooks_from_directories
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.base import LoadedSession, SessionStore
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.registry import ToolRegistry


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.snapshots: dict[str, dict[str, object]] = {}

    def append_event(self, session_id: str, entry: object) -> None:
        self.events.append((session_id, entry))

    def load_session(self, session_id: str) -> LoadedSession | None:
        session_events = tuple(entry for sid, entry in self.events if sid == session_id)
        if not session_events and session_id not in self.snapshots:
            return None
        return LoadedSession(
            session_id=session_id,
            events=session_events,
            snapshot=self.snapshots.get(session_id),
        )

    def save_snapshot(self, session_id: str, snapshot: dict[str, object]) -> None:
        self.snapshots[session_id] = snapshot


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}"),
            finish_reason="stop",
        )


class EchoTool:
    name = "echo"
    description = "Echo text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):
        del ctx
        return {"text": args["text"]}


def test_runtime_uses_loaded_hooks_for_input_transform_chain(tmp_path: Path) -> None:
    builtins_dir = tmp_path / "builtin_hooks"
    workspace_dir = tmp_path / ".nano" / "hooks"
    builtins_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    (builtins_dir / "prefix.py").write_text(
        """
def setup(hooks):
    async def on_input(event, ctx):
        del ctx
        return {"action": "transform", "text": f"builtin:{event['text']}"}
    hooks.on("input", on_input, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "suffix.py").write_text(
        """
def setup(hooks):
    async def on_input(event, ctx):
        del ctx
        return {"action": "transform", "text": f"{event['text']}:workspace"}
    hooks.on("input", on_input, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    hook_registry, loaded = load_hooks_from_directories(
        repo_root=tmp_path,
        builtins_dir=builtins_dir,
        workspace_dir=workspace_dir,
    )
    assert len(loaded) == 2

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=hook_registry),
        repo_root=tmp_path,
    )

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm.requests[-1].messages[-1].content == "builtin:ping:workspace"
    assert result.messages[0].content == "ack:builtin:ping:workspace"


def test_tool_registry_uses_loaded_hooks_for_block_and_rewrite(tmp_path: Path) -> None:
    workspace_dir = tmp_path / ".nano" / "hooks"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "tool_rules.py").write_text(
        """
def setup(hooks):
    async def on_tool_call(event, ctx):
        del ctx
        if event["name"] == "echo" and event["args"].get("text") == "blocked":
            return {"block": True, "reason": "workspace-policy"}
        return {"block": False}

    async def on_tool_result(event, ctx):
        del ctx
        if event["name"] == "echo":
            return {"content": {"text": f"rewritten:{event['output']['text']}"}}
        return None

    hooks.on("tool_call", on_tool_call, priority=100)
    hooks.on("tool_result", on_tool_result, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    hook_registry, loaded = load_hooks_from_directories(repo_root=tmp_path, workspace_dir=workspace_dir)
    assert len(loaded) == 1
    runner = HookRunner(registry=hook_registry)
    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=runner,
    )
    tool_registry.register(EchoTool())

    with pytest.raises(ToolError, match="blocked by hook"):
        tool_registry.execute(
            "echo",
            {"text": "blocked"},
            hook_context=HookContext(session_id="sess_tool_block", repo_root=tmp_path),
        )

    rewritten = tool_registry.execute(
        "echo",
        {"text": "ping"},
        hook_context=HookContext(session_id="sess_tool_rewrite", repo_root=tmp_path),
    )
    assert rewritten == {"text": "rewritten:ping"}
