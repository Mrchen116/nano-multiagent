"""Product-specific kernel app for personal_assistant.

This module provides the uvicorn-loadable ``app`` object with the
personal_assistant ProductProfile already wired.  The kernel command
in ``node-config.yaml`` should reference this module::

    python -m uvicorn personal_assistant.kernel_app:app --host 127.0.0.1 --port 18070
"""

import os

from agent.core.llm.config import LLMConfigPayload
from agent.core.llm.model_registry import init_model_registry

# Initialize registry BEFORE importing create_app — app.py runs create_app() at
# module level, which calls get_default_provider() via LLMFactoryConfig.from_env().
_raw_llm_config = os.environ.get("NANO_MULTIAGENT_LLM_CONFIG_JSON")
if _raw_llm_config is None:
    raise RuntimeError(
        "NANO_MULTIAGENT_LLM_CONFIG_JSON is not set — "
        "personal_assistant kernel_app must be launched by the Gateway which injects this env var"
    )
init_model_registry(LLMConfigPayload.from_json(_raw_llm_config))

from agent.platform.http_api.app import create_app  # noqa: E402
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE  # noqa: E402

app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE)
