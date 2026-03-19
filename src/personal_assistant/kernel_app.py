"""Product-specific kernel app for personal_assistant.

This module provides the uvicorn-loadable ``app`` object with the
personal_assistant ProductProfile already wired.  The kernel command
in ``node-config.yaml`` should reference this module::

    python -m uvicorn personal_assistant.kernel_app:app --host 127.0.0.1 --port 18070
"""

from agent.platform.http_api.app import create_app
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE)
