"""Verify platform/llm/providers is the canonical home for provider adapters."""


import nano_multiagent.llm.providers as legacy_provider_package
import nano_multiagent.platform.llm.providers as platform_provider_package
from nano_multiagent.llm.protocols import anthropic as legacy_protocol_anthropic
from nano_multiagent.llm.protocols import openai_compat as legacy_protocol_openai_compat
from nano_multiagent.llm.providers.anthropic import AnthropicClient as LegacyAnthropicClient
from nano_multiagent.llm.providers.anthropic import AnthropicMapper as LegacyAnthropicMapper
from nano_multiagent.llm.providers.openai_compat import OpenAICompatClient as LegacyOpenAICompatClient
from nano_multiagent.llm.providers.openai_compat import OpenAICompatMapper as LegacyOpenAICompatMapper
from nano_multiagent.platform.llm.providers.anthropic import AnthropicClient, AnthropicMapper
from nano_multiagent.platform.llm.providers.openai_compat import OpenAICompatClient, OpenAICompatMapper


def test_platform_llm_providers_package_is_canonical_home() -> None:
    assert platform_provider_package.__name__ == "nano_multiagent.platform.llm.providers"
    assert AnthropicClient.__module__ == "nano_multiagent.platform.llm.providers.anthropic.client"
    assert AnthropicMapper.__module__ == "nano_multiagent.platform.llm.providers.anthropic.mapper"
    assert OpenAICompatClient.__module__ == "nano_multiagent.platform.llm.providers.openai_compat.client"
    assert OpenAICompatMapper.__module__ == "nano_multiagent.platform.llm.providers.openai_compat.mapper"



def test_old_llm_provider_paths_are_compat_shims() -> None:
    assert legacy_provider_package is platform_provider_package
    assert LegacyAnthropicClient is AnthropicClient
    assert LegacyAnthropicMapper is AnthropicMapper
    assert LegacyOpenAICompatClient is OpenAICompatClient
    assert LegacyOpenAICompatMapper is OpenAICompatMapper
    assert legacy_protocol_anthropic.AnthropicClient is AnthropicClient
    assert legacy_protocol_anthropic.AnthropicMapper is AnthropicMapper
    assert legacy_protocol_openai_compat.OpenAICompatClient is OpenAICompatClient
    assert legacy_protocol_openai_compat.OpenAICompatMapper is OpenAICompatMapper
