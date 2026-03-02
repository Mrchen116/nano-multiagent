from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.compaction.types import CompactionReason, CompactionSettings
from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.errors import ModelError
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.server.app import create_app
from nano_multiagent.session.entries import CompactionEntry
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class OverflowRetryLLMClient:
    def __init__(self) -> None:
        self.calls: list[LLMGenerateRequest] = []
        self._overflow_triggered = False

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.calls.append(request)
        if request.model == "summary-model":
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(role="assistant", content="summary for overflow recovery"),
                finish_reason="stop",
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
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="recovered"),
            finish_reason="stop",
        )


class SummaryFailingOverflowLLMClient:
    def __init__(self) -> None:
        self.calls: list[LLMGenerateRequest] = []
        self._overflow_triggered = False

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.calls.append(request)
        if request.model == "summary-model":
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
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="recovered-with-fallback"),
            finish_reason="stop",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_message_route_recovers_from_overflow_via_compaction(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-overflow-e2e.sqlite3")
    llm_client = OverflowRetryLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
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
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-compaction-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    first = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "first"}], "stream": False},
        headers=_auth_headers("req-compaction-first"),
    )
    assert first.status_code == 200

    second = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "second"}], "stream": False},
        headers=_auth_headers("req-compaction-second"),
    )
    assert second.status_code == 200
    assert second.json()["message"]["content"] == "recovered"

    loaded = store.load_session(session_id)
    assert loaded is not None
    compactions = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.OVERFLOW.value
    assert isinstance(compactions[-1].first_kept_event_id, str) and compactions[-1].first_kept_event_id

    main_calls = [request for request in llm_client.calls if request.model == "main-model"]
    assert len(main_calls) == 3


def test_message_route_recovers_even_if_summary_model_fails(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "compaction-overflow-fallback-e2e.sqlite3")
    llm_client = SummaryFailingOverflowLLMClient()
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
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
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-compaction-fallback-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    first = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "first"}], "stream": False},
        headers=_auth_headers("req-compaction-fallback-first"),
    )
    assert first.status_code == 200

    second = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "second"}], "stream": False},
        headers=_auth_headers("req-compaction-fallback-second"),
    )
    assert second.status_code == 200
    assert second.json()["message"]["content"] == "recovered-with-fallback"

    loaded = store.load_session(session_id)
    assert loaded is not None
    compactions = [event for event in loaded.events if isinstance(event, CompactionEntry)]
    assert compactions
    assert compactions[-1].data["reason"] == CompactionReason.OVERFLOW.value
    assert "触发原因为 overflow" in compactions[-1].summary
