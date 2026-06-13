"""Product-owned tools for personal_assistant (refactor-406 决策 9).

These are PA's native tool objects, supplied to ``agent.sdk.build_kernel(tools=…)``
by the PA kernel factory. Side-effecting tools (cron / send_message) reach their
backing services directly — cron via a closure over the per-agent
``CronExecutionService`` map, send_message via the Gateway dispatch URL threaded
through session metadata. No HostCapabilityDispatcher round-trip into the kernel.
"""

from .cron import CronTool, make_cron_tool
from .send_message import SendMessageTool
from .web_search import WebSearchTool

__all__ = ["CronTool", "make_cron_tool", "SendMessageTool", "WebSearchTool"]
