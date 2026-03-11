import os

import httpx
import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.factory import create_llm_client
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


def _llm_proxy_available() -> bool:
    try:
        response = httpx.get("http://127.0.0.1:4000/health", timeout=1.5)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


@pytest.mark.e2e
def test_runtime_can_complete_text_only_turn_with_real_proxy(tmp_path) -> None:
    if os.getenv("NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E") != "1":
        pytest.skip("set NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 to run live proxy e2e tests")

    if not _llm_proxy_available():
        pytest.skip("LLM_PROXY is unavailable on http://127.0.0.1:4000")

    store = SQLiteSessionStore(db_path=tmp_path / "runtime-e2e.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()

    with create_llm_client() as llm_client:
        runtime = AgentRuntime(session_manager=manager, llm_client=llm_client, model="")
        result = runtime.run(
            session.session_id,
            [{"type": "text", "text": "reply one word: pong"}],
            stream=False,
        )

    assert result.messages[0].role == "assistant"
    assert "pong" in result.messages[0].content.lower()
