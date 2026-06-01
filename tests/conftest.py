"""Top-level test conftest — initializes model registry for all tests.

The model registry is now a process-level singleton that must be explicitly
initialized via init_model_registry(payload). Tests that used to import and
call registry functions without setup will now fail with RuntimeError.

Module-level initialization here ensures the registry is populated before pytest
collection imports test modules that transitively call registry functions (e.g.
src/agent/platform/http_api/app.py calls create_app() at module level, which
invokes AgentRuntime.__init__ → LLMFactoryConfig.from_env() → get_default_provider()).

The autouse fixture resets/re-initializes before each test, so tests get a clean
slate and explicit "not initialized" tests can call _reset_for_tests() safely.
"""

import pytest

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from agent.core.llm.model_registry import _reset_for_tests, init_model_registry


_DEFAULT_TEST_PAYLOAD = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(
                LLMModelPayload(
                    name="kimiCoding:K2.6",
                    extra_request_body={"thinking": {"type": "adaptive"}},
                ),
                LLMModelPayload(
                    name="volcanoArk:doubao-seed-2-0-code-preview-260215",
                    extra_request_body={"thinking": {"type": "adaptive"}},
                ),
            ),
        ),
        LLMProviderPayload(
            name="openai_compat",
            base_url="http://127.0.0.1:4000",
            models=(LLMModelPayload(name="codex_oauth:gpt-5.5"),),
        ),
    ),
)

# Module-level init: must run before any test module that imports registry-dependent
# code (e.g. app.py calls create_app() at module level during collection).
init_model_registry(_DEFAULT_TEST_PAYLOAD)


@pytest.fixture(autouse=True)
def _init_model_registry_for_tests():
    """Reset and re-initialize model registry before each test.

    Provides clean state per test. Tests that need to verify "not initialized"
    behavior call _reset_for_tests() explicitly before their assertion.
    """
    _reset_for_tests()
    init_model_registry(_DEFAULT_TEST_PAYLOAD)
    yield
    _reset_for_tests()
