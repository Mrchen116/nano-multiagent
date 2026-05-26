"""Product-specific kernel app for personal_assistant.

This module provides the uvicorn-loadable ``app`` object with the
personal_assistant ProductProfile already wired.  The kernel command
in ``node-config.yaml`` should reference this module::

    python -m uvicorn personal_assistant.kernel_app:app --host 127.0.0.1 --port 18070
"""

import os

from agent.core.llm.config import LLMConfigPayload
from agent.core.llm.model_registry import init_model_registry
from agent.platform.http_api.app import create_app
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

_raw_llm_config = os.environ.get("NANO_MULTIAGENT_LLM_CONFIG_JSON")
if _raw_llm_config is None:
    raise RuntimeError(
        "NANO_MULTIAGENT_LLM_CONFIG_JSON is not set — "
        "personal_assistant kernel_app must be launched by the Gateway which injects this env var"
    )
_llm_payload = LLMConfigPayload.from_json(_raw_llm_config)
init_model_registry(_llm_payload)

app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE)
