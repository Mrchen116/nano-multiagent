"""Cross-layer routing for overlapping self-evolution update receipts."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.sdk import LLMConfig, build_kernel
from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)
from personal_assistant.gateway.runtime_delivery.background import (
    build_session_event_callback,
)
from tests.helpers.self_evolution import allow_all, wait_for_terminal


class _OverlappingReviewLLM:
    """Drive two review forks from structural tool availability and call state."""

    def __init__(self, first_review_gate: asyncio.Event) -> None:
        self._first_review_gate = first_review_gate
        self._request_indexes: defaultdict[str, int] = defaultdict(int)

    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        if request.tools == ():

            async def _classify() -> AsyncIterator[LLMMessage]:
                yield LLMMessage(role="assistant", content="<block>no</block>")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")

            return _classify()

        assert {tool.name for tool in request.tools} <= {
            "skill_manage",
            "skill_view",
        }
        route = next(
            (
                str(message.content)
                for message in request.messages
                if message.role == "user"
                and message.content in {"route-one", "route-two"}
            ),
            None,
        )
        assert route is not None
        request_index = self._request_indexes[route]
        self._request_indexes[route] += 1

        async def _stream() -> AsyncIterator[LLMMessage]:
            if request_index == 0:
                yield LLMMessage(role="assistant", content=f"foreground-{route}")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return
            if request_index == 1:
                if route == "route-one":
                    await self._first_review_gate.wait()
                skill_name = f"overlap-{route}"
                call = LLMToolCall(
                    call_id=f"review-{route}-create",
                    name="skill_manage",
                    arguments={
                        "action": "create",
                        "name": skill_name,
                        "scope": "agent",
                        "content": (
                            f"---\nname: {skill_name}\n"
                            "description: Verify overlap routing.\n---\n\n"
                            "# Overlap route skill\n\n"
                            "Use the overlap route sentinel.\n"
                        ),
                    },
                )
                yield LLMMessage(role="assistant", content="", tool_calls=(call,))
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
                return
            assert request_index == 2
            expected_call_id = f"review-{route}-create"
            assert any(
                message.role == "tool" and message.tool_call_id == expected_call_id
                for message in request.messages
            )
            yield LLMMessage(role="assistant", content=f"private-saved-{route}")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

        return _stream()


class _RecordingIMManager:
    connected = True

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, Any]
    ) -> dict[str, str]:
        assert message_type == "node.system_message"
        self.messages.append(dict(payload))
        return {"message_id": f"notice-{len(self.messages)}"}


async def _wait_for_count(items: list[object], count: int) -> None:
    async with asyncio.timeout(15):
        while len(items) < count:
            await asyncio.sleep(0)


async def _next_review(
    kernel: Any, session_id: str, after_sequence: int
) -> dict[str, Any]:
    async with asyncio.timeout(15):
        async for event in kernel.stream(session_id, after_sequence=after_sequence):
            if event.get("event") == "self_evolution_review":
                return event
    raise AssertionError("session stream closed before review receipt")


def _session_metadata() -> dict[str, object]:
    return {
        "self_evolution": {
            "enabled": True,
            "skill_creation": True,
            "memory_curation": False,
            "skill_nudge_interval": 1,
            "memory_nudge_interval": 100,
        }
    }


@pytest.mark.asyncio
async def test_overlapping_real_reviews_use_their_own_gateway_trace_routes(
    tmp_path: Path,
) -> None:
    """A later IM turn cannot steal a delayed Feishu review's frozen route."""

    first_review_gate = asyncio.Event()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        can_use_tool=allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=_OverlappingReviewLLM(first_review_gate),
    )
    im_manager = _RecordingIMManager()
    external: list[tuple[str, dict[str, str]]] = []
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: im_manager,  # type: ignore[arg-type]
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
        delivery_incarnation="integration-gateway",
    )
    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=callback,
    )
    try:
        first_session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["skill_manage"],
            features={},
            metadata=_session_metadata(),
        )
        second_session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["skill_manage"],
            features={},
            metadata=_session_metadata(),
        )
        feishu_route = ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="feishu:app:dm:chat-original",
            metadata={
                "external_source": "feishu",
                "trigger_source": "feishu",
                "shadow_conversation_id": "shadow-feishu",
            },
        )
        im_route = ReplyContext(
            channel_name="web_relay",
            target_chat_id="shadow-im",
            metadata={"trigger_source": "im"},
        )
        manager.register_session_event_route("trace-first", feishu_route)
        first_run = kernel.submit(
            session_id=first_session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "route-one"}],
            trace_id="trace-first",
        )
        await wait_for_terminal(kernel, first_run.run_id)
        await manager.ensure_after_foreground_terminal(
            BackgroundSubscriptionRequest(
                session_id=first_session.session_id,
                after_sequence=first_run.start_sequence,
                reply_context=feishu_route,
                agent_id="agent-a",
            )
        )

        manager.register_session_event_route("trace-second", im_route)
        second_run = kernel.submit(
            session_id=second_session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "route-two"}],
            trace_id="trace-second",
        )
        await wait_for_terminal(kernel, second_run.run_id)
        await manager.ensure_after_foreground_terminal(
            BackgroundSubscriptionRequest(
                session_id=second_session.session_id,
                after_sequence=second_run.start_sequence,
                reply_context=im_route,
                agent_id="agent-a",
            )
        )

        second_review = await _next_review(
            kernel, second_session.session_id, second_run.start_sequence
        )
        assert second_review["originating_trace_id"] == "trace-second"
        await _wait_for_count(im_manager.messages, 1)
        assert im_manager.messages[0]["conversation_id"] == "shadow-im"
        assert external == []

        first_review_gate.set()
        await _wait_for_count(im_manager.messages, 2)

        by_conversation = {
            str(message["conversation_id"]): message for message in im_manager.messages
        }
        assert set(by_conversation) == {"shadow-im", "shadow-feishu"}
        assert by_conversation["shadow-im"]["system_notice"]["updated_targets"] == [
            "skills"
        ]
        assert by_conversation["shadow-feishu"]["system_notice"]["updated_targets"] == [
            "skills"
        ]
        assert len(external) == 1
        assert external[0][1]["target_chat_id"] == "feishu:app:dm:chat-original"
        assert "skills updated" in external[0][0]
        visible = "\n".join(
            [external[0][0]]
            + [str(message.get("text") or "") for message in im_manager.messages]
        )
        assert "private-saved" not in visible
    finally:
        first_review_gate.set()
        await manager.aclose(asyncio.get_running_loop().time() + 1)
        await kernel.aclose()
