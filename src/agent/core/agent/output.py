"""Private structural output controls and shared unpublished-draft feedback."""

from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4


def withheld_reminder(reason: str, continuation: str) -> str:
    """Render the common unpublished-output feedback with its actual cause."""
    return (
        "<system-reminder>\n" + reason + " It was withheld before publication "
        "and was never delivered to the conversation, so the participants "
        "have not received its content. Earlier successfully published "
        "assistant messages remain part of the shared conversation.\n\n"
        + continuation
        + " If a public response is warranted, include all "
        "information the recipients still need, since the withheld draft "
        "communicated nothing to them.\n</system-reminder>"
    )


class BoundOutputControl:
    """Bind product callback capabilities to the current run and registry."""

    def __init__(self, controller, revision: int, registry, context) -> None:
        self._controller = controller
        self._revision = revision
        self._registry = registry
        self._context = context

    async def authorize_tool(self, name: str, arguments: Mapping[str, Any]):
        if self._registry is None:
            return {"block": True, "reason": "tool registry unavailable"}
        return await self._registry.evaluate_permission(
            name,
            arguments,
            hook_context=self._context,
            action_id="output_permission_" + uuid4().hex,
            permission_only=True,
        )

    def try_commit(self, enqueue: Callable[[], None]) -> str:
        if self._controller is None:
            enqueue()
            return "committed"
        return self._controller.try_commit_output(self._revision, enqueue)
