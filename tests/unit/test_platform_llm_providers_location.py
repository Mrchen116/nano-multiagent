"""Verify platform/llm/providers is the canonical home for provider adapters."""

from importlib.util import find_spec

import nano_multiagent.platform.llm.providers as platform_provider_package
from nano_multiagent.platform.llm.providers.anthropic import AnthropicClient, AnthropicMapper
from nano_multiagent.platform.llm.providers.openai_compat import OpenAICompatClient, OpenAICompatMapper
from nano_multiagent.platform.llm.providers.translator import LLMTranslator, ProviderMapper, ProviderRequest



def test_platform_llm_providers_package_is_canonical_home() -> None:
    assert platform_provider_package.__name__ == "nano_multiagent.platform.llm.providers"
    assert AnthropicClient.__module__ == "nano_multiagent.platform.llm.providers.anthropic.client"
    assert AnthropicMapper.__module__ == "nano_multiagent.platform.llm.providers.anthropic.mapper"
    assert OpenAICompatClient.__module__ == "nano_multiagent.platform.llm.providers.openai_compat.client"
    assert OpenAICompatMapper.__module__ == "nano_multiagent.platform.llm.providers.openai_compat.mapper"
    assert LLMTranslator.__module__ == "nano_multiagent.platform.llm.providers.translator"
    assert ProviderMapper.__module__ == "nano_multiagent.platform.llm.providers.translator"
    assert ProviderRequest.__module__ == "nano_multiagent.platform.llm.providers.translator"



def test_legacy_llm_provider_root_is_removed() -> None:
    assert find_spec("nano_multiagent.llm") is None
