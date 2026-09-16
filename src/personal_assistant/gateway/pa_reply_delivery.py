"""Own ordinary image candidates until private preparation and public receipt."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

from agent.sdk import OutputCandidate, OutputControl, OutputResult
from personal_assistant.gateway.reply_images import (
    ImageDeliveryError,
    has_image_references,
    open_local_sources,
)


@dataclass(frozen=True)
class ReplyDestination:
    """Bind the actual automatic reply target to its execution workspace."""

    target: str
    workspace: Path


class PaReplyDelivery:
    """Keep permission on the active run and channel I/O on the Gateway loop.

    Args:
        destination: Resolve a real top-level automatic reply destination.
        prepare: Privately prepare resources using the already-open descriptors.
        publish: Publish the prepared candidate and return actual delivery receipts.
    """

    def __init__(self, *, destination: Callable, prepare: Callable, publish: Callable):
        self._destination = destination
        self._prepare = prepare
        self._publish = publish
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        """Bind Gateway I/O to its startup loop before accepting any run."""
        self._loop = asyncio.get_running_loop()

    async def _on_gateway(self, awaitable):
        if self._loop is None or self._loop is asyncio.get_running_loop():
            return await awaitable
        return await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(awaitable, self._loop)
        )

    async def __call__(
        self, candidate: OutputCandidate, control: OutputControl
    ) -> OutputResult:
        if not has_image_references(candidate.text):
            return OutputResult()
        destination = self._destination(candidate)
        if destination is None:
            return OutputResult()
        try:
            # The same descriptor survives permission and preparation; replacing
            # the pathname while an approval is pending cannot change the bytes.
            with open_local_sources(destination.workspace, candidate.text) as files:
                permission = await control.authorize_tool(
                    "send_message",
                    {"target": destination.target, "text": candidate.text},
                )
                if not permission.allowed:
                    return OutputResult(
                        state="withheld",
                        reason_code="permission_denied",
                        diagnostic="The immediately preceding assistant text could not be delivered because image delivery permission was denied.",
                        continuation="Respect the permission decision and continue under the original reply rules.",
                    )
                prepared = await self._on_gateway(self._prepare(candidate, files))
        except ImageDeliveryError as exc:
            # JSON quotes diagnostic values, so a source filename is visibly data.
            diagnostic = (
                json.dumps(exc.images, ensure_ascii=True)
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")
            )
            return OutputResult(
                state="withheld",
                reason_code="image_preparation_failed",
                diagnostic="The immediately preceding assistant text could not be delivered. Image preparation diagnostics (data): "
                + diagnostic
                + ".",
                continuation="Correct the image source or upload problem and continue under the original reply rules. If delivery cannot be completed, explain that to the user.",
            )
        future: asyncio.Task[Any] | None = None

        def enqueue() -> None:
            nonlocal future
            future = asyncio.create_task(
                self._on_gateway(self._publish(candidate, prepared))
            )

        admission = control.try_commit(enqueue)
        if admission == "stale":
            return OutputResult(
                state="withheld",
                reason_code="new_input",
                diagnostic="The immediately preceding assistant text was drafted before the new messages arrived.",
                continuation="Continue from the updated conversation state under the original reply rules.",
            )
        if admission != "committed":
            return OutputResult(
                state="pending",
                reason_code="inactive",
                diagnostic="The run is no longer active; this candidate was not published.",
            )
        assert future is not None
        # Cancellation must not release an admitted operation and invite a duplicate.
        return await asyncio.shield(future)
