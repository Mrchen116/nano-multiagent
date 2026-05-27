"""Product-specific kernel app for local_coding.

This module provides the uvicorn-loadable ``app`` object with the
local_coding ProductProfile already wired.  The managed server should
reference this module::

    python -m uvicorn coding_cli.kernel_app:app --factory ...
"""

import os

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from agent.core.llm.model_registry import init_model_registry

# Initialize registry BEFORE importing create_app — app.py runs create_app() at
# module level, which calls get_default_provider() via LLMFactoryConfig.from_env().
_raw_llm_config = os.environ.get("NANO_MULTIAGENT_LLM_CONFIG_JSON")
if _raw_llm_config is not None:
    # Gateway-style: full config JSON injected by parent process
    _llm_payload = LLMConfigPayload.from_json(_raw_llm_config)
else:
    # CLI managed-mode: construct minimal payload from individual env vars
    _provider = os.environ.get("NANO_MULTIAGENT_LLM_PROVIDER", "anthropic")
    _model = os.environ.get("NANO_MULTIAGENT_LLM_MODEL", "kimiCoding:K2.6")
    _base_url = os.environ.get("NANO_MULTIAGENT_LLM_BASE_URL", "http://127.0.0.1:4000")
    _llm_payload = LLMConfigPayload(
        default_model=_model,
        providers=(
            LLMProviderPayload(
                name=_provider,
                base_url=_base_url,
                models=(LLMModelPayload(name=_model),),
            ),
        ),
    )
init_model_registry(_llm_payload)

from agent.platform.http_api.app import create_app  # noqa: E402
from agent.products.local_coding import LOCAL_CODING_PROFILE  # noqa: E402

app = create_app(product_profile=LOCAL_CODING_PROFILE)
