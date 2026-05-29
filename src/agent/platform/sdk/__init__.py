"""agent.platform.sdk — legacy HTTP client module stub.

The ServerClient HTTP client has been deleted in refactor-387-M1 as part of
removing the internal HTTP API. Products now use agent.sdk (in-process Kernel)
instead of HTTP.

This __init__.py is left empty to avoid breaking existing import machinery
during the transition (M1–M4). It will be removed in M4.
"""

__all__: list = []
