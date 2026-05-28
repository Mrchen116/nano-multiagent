"""Tests for agent.core.llm.config — LLMConfigPayload wire schema and JSON roundtrip."""

import json

import pytest


def _make_minimal_payload():
    from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

    model = LLMModelPayload(name="kimiCoding:K2.6", extra_request_body={"thinking": {"type": "adaptive"}})
    provider = LLMProviderPayload(name="anthropic", base_url="http://127.0.0.1:4000", models=(model,))
    return LLMConfigPayload(default_model="kimiCoding:K2.6", providers=(provider,))


def test_llm_config_payload_roundtrip():
    from agent.core.llm.config import LLMConfigPayload

    payload = _make_minimal_payload()
    serialized = payload.to_json()
    restored = LLMConfigPayload.from_json(serialized)

    assert restored.default_model == payload.default_model
    assert len(restored.providers) == 1
    assert restored.providers[0].name == "anthropic"
    assert restored.providers[0].base_url == "http://127.0.0.1:4000"
    assert len(restored.providers[0].models) == 1
    assert restored.providers[0].models[0].name == "kimiCoding:K2.6"
    assert restored.providers[0].models[0].extra_request_body == {"thinking": {"type": "adaptive"}}


def test_llm_config_payload_null_extra_request_body():
    from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

    model = LLMModelPayload(name="codex_oauth:gpt-5.5", extra_request_body=None)
    provider = LLMProviderPayload(name="openai_compat", base_url=None, models=(model,))
    payload = LLMConfigPayload(default_model="codex_oauth:gpt-5.5", providers=(provider,))

    restored = LLMConfigPayload.from_json(payload.to_json())
    assert restored.providers[0].models[0].extra_request_body is None
    assert restored.providers[0].base_url is None


def test_llm_config_payload_multiple_providers():
    from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

    anthropic_model = LLMModelPayload(name="kimiCoding:K2.6", extra_request_body={"thinking": {"type": "adaptive"}})
    openai_model = LLMModelPayload(name="codex_oauth:gpt-5.5")
    providers = (
        LLMProviderPayload(name="anthropic", base_url="http://127.0.0.1:4000", models=(anthropic_model,)),
        LLMProviderPayload(name="openai_compat", base_url="http://127.0.0.1:4000", models=(openai_model,)),
    )
    payload = LLMConfigPayload(default_model="kimiCoding:K2.6", providers=providers)

    restored = LLMConfigPayload.from_json(payload.to_json())
    assert len(restored.providers) == 2
    names = {p.name for p in restored.providers}
    assert names == {"anthropic", "openai_compat"}


def test_llm_config_payload_from_json_invalid():
    from agent.core.llm.config import LLMConfigPayload

    with pytest.raises((ValueError, KeyError, json.JSONDecodeError)):
        LLMConfigPayload.from_json("not-json")


def test_llm_model_payload_default_extra_request_body_is_none():
    from agent.core.llm.config import LLMModelPayload

    model = LLMModelPayload(name="foo:bar")
    assert model.extra_request_body is None
