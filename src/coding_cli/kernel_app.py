"""Product-specific kernel app for local_coding.

This module provides the uvicorn-loadable ``app`` object with the
local_coding ProductProfile already wired.  The managed server should
reference this module::

    python -m uvicorn coding_cli.kernel_app:app --factory ...
"""

from agent.platform.http_api.app import create_app
from agent.products.local_coding import LOCAL_CODING_PROFILE

app = create_app(product_profile=LOCAL_CODING_PROFILE)
