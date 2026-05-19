import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.compaction.types import CompactionReason, CompactionSettings
from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.platform.http_api.app import create_app
from agent.core.session.entries import CompactionEntry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService


def _is_compaction_request(request: LLMGenerateRequest) -> bool:
    return any("Do NOT call any tools" in (m.content or "") for m in request.messages)


class OverflowRetryLLMClient:
    def __init__(self) -> None:
        self.calls: list[LLMGenerateRequest] = []
        self._overflow_triggered = False

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:  # type: ignore[override]
        self.calls.append(request)
        if _is_compaction_request(request):
            yield LLMMessage(role="assistant", content="summary for overflow recovery")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return
        if not self._overflow_triggered and len(request.messages) >= 4:
            self._overflow_triggered = True
            raise ModelError(
                "overflow",
                details={
                    "status_code": 400,
                    "response": "maximum context length exceeded",
                },
            )
        yield LLMMessage(role="assistant", content="recovered")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


class SummaryFailingOverflowLLMClient:
    def __init__(self) -> None:
        self.calls: list[LLMGenerateRequest] = []
        self._overflow_triggered = False

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:  # type: ignore[override]
        self.calls.append(request)
        if _is_compaction_request(request):
            raise ModelError(
                "summary backend unavailable",
                details={"status_code": 503, "response": "summary service unavailable"},
            )
        if not self._overflow_triggered and len(request.messages) >= 4:
            self._overflow_triggered = True
            raise ModelError(
                "overflow",
                details={
                    "status_code": 400,
                    "response": "maximum context length exceeded",
                },
            )
        yield LLMMessage(role="assistant", content="recovered-with-fallback")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_completed_run(client: TestClient, run_id: str, request_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers(request_id))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_message_route_recovers_from_overflow_via_compaction(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    llm_client = OverflowRetryLLMClient()
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=llm_client,
        model="main-model",
        compaction_settings=CompactionSettings(
            enabled=True,
            context_window=300,
            reserve_tokens=60,
            min_kept_messages=2,
            summary_model="summary-model",
        ),
    )
    client = TestClient(create_app(session_store=service.manager._store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-compaction-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    first = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "first"}]},
        headers=_auth_headers("req-compaction-first"),
    )
    assert first.status_code == 200
    _wait_for_completed_run(client, first.json()["run_id"], "req-compaction-first-poll")

    second = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "second"}]},
        headers=_auth_headers("req-compaction-second"),
    )
    assert second.status_code == 200
    terminal = _wait_for_completed_run(client, second.json()["run_id"], "req-compaction-second-poll")
    assert terminal["output_text"] == "recovered"

    entries = service.manager.list_entries(session_id)
    compactions = [event for event in entries if isinstance(event, CompactionEntry)]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.OVERFLOW.value
    assert isinstance(compactions[-1].first_kept_event_id, str)

    main_calls = [request for request in llm_client.calls if request.model == "main-model"]
    # 1st turn + 2nd turn (overflow) + compaction summary + retry = 4
    assert len(main_calls) == 4


def test_message_route_recovers_even_if_summary_model_fails(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions-fallback"))
    llm_client = SummaryFailingOverflowLLMClient()
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=llm_client,
        model="main-model",
        compaction_settings=CompactionSettings(
            enabled=True,
            context_window=300,
            reserve_tokens=60,
            min_kept_messages=2,
            summary_model="summary-model",
        ),
    )
    client = TestClient(create_app(session_store=service.manager._store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-compaction-fallback-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    first = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "first"}]},
        headers=_auth_headers("req-compaction-fallback-first"),
    )
    assert first.status_code == 200
    _wait_for_completed_run(client, first.json()["run_id"], "req-compaction-fallback-first-poll")

    second = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "second"}]},
        headers=_auth_headers("req-compaction-fallback-second"),
    )
    assert second.status_code == 200
    terminal = _wait_for_completed_run(client, second.json()["run_id"], "req-compaction-fallback-second-poll")
    assert terminal["output_text"] == "recovered-with-fallback"

    entries = service.manager.list_entries(session_id)
    compactions = [event for event in entries if isinstance(event, CompactionEntry)]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.OVERFLOW.value
    assert compactions[-1].summary  # fallback summary is non-empty
