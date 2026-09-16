"""Ordinary image candidates authorize and publish before returning to the model."""

import asyncio

from agent.sdk import OutputCandidate, PermissionOutcome
from personal_assistant.gateway.pa_reply_delivery import (
    PaReplyDelivery,
    ReplyDestination,
)


class Control:
    def __init__(self, *, allowed=True, admission="committed"):
        self.allowed = allowed
        self.admission = admission
        self.calls = []

    async def authorize_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return PermissionOutcome(self.allowed, "denied" if not self.allowed else None)

    def try_commit(self, enqueue):
        if self.admission == "committed":
            enqueue()
        return self.admission


def test_image_candidate_is_private_on_prepare_failure(tmp_path):
    async def scenario():
        published = []
        owner = PaReplyDelivery(
            destination=lambda _: ReplyDestination("c_test", tmp_path),
            prepare=lambda *args: None,
            publish=lambda *args: published.append(args),
        )
        candidate = OutputCandidate(
            "s", "r", "m", 0, "Here ![a](</missing.png>)", ("m",)
        )
        result = await owner(candidate, Control())
        assert result.state == "withheld"
        assert "new messages" not in result.diagnostic
        assert published == []

    asyncio.run(scenario())


def test_permission_denial_never_reads_or_prepares(tmp_path):
    async def scenario():
        calls = []
        owner = PaReplyDelivery(
            destination=lambda _: ReplyDestination("c_test", tmp_path),
            prepare=lambda *args: calls.append(args),
            publish=lambda *args: calls.append(args),
        )
        path = tmp_path / "image.png"
        path.write_bytes(b"image")
        candidate = OutputCandidate("s", "r", "m", 0, f"![a](<{path}>)", ("m",))
        control = Control(allowed=False)
        result = await owner(candidate, control)
        assert result.state == "withheld"
        assert control.calls == [
            ("send_message", {"target": "c_test", "text": candidate.text})
        ]
        assert calls == []

    asyncio.run(scenario())


def test_text_skips_image_permission(tmp_path):
    async def scenario():
        owner = PaReplyDelivery(destination=lambda _: None, prepare=None, publish=None)
        control = Control()
        result = await owner(
            OutputCandidate("s", "r", "m", 0, "hello", ("m",)), control
        )
        assert result.state == "pass_through"
        assert control.calls == []

    asyncio.run(scenario())


def test_stale_candidate_does_not_publish_after_upload(tmp_path):
    async def scenario():
        published = []
        path = tmp_path / "image.png"
        path.write_bytes(b"image")

        async def prepare(candidate, files):
            return "private-upload"

        async def publish(*args):
            published.append(args)

        owner = PaReplyDelivery(
            destination=lambda _: ReplyDestination("c_test", tmp_path),
            prepare=prepare,
            publish=publish,
        )
        result = await owner(
            OutputCandidate("s", "r", "m", 0, f"![a](<{path}>)", ("m",)),
            Control(admission="stale"),
        )
        assert result.state == "withheld"
        assert result.reason_code == "new_input"
        assert published == []

    asyncio.run(scenario())


def test_permission_wait_keeps_original_file_descriptor(tmp_path):
    import os
    from agent.sdk import OutputResult

    async def scenario():
        path = tmp_path / "image.png"
        path.write_bytes(b"original")
        observed = []

        class ReplaceDuringApproval(Control):
            async def authorize_tool(self, name, arguments):
                path.unlink()
                path.write_bytes(b"replacement")
                return PermissionOutcome(True)

        async def prepare(candidate, files):
            observed.append(os.pread(files[str(path)], 100, 0))
            return "prepared"

        async def publish(candidate, prepared):
            return OutputResult(state="delivered")

        owner = PaReplyDelivery(
            destination=lambda _: ReplyDestination("c_test", tmp_path),
            prepare=prepare,
            publish=publish,
        )
        result = await owner(
            OutputCandidate("s", "r", "m", 0, f"![a](<{path}>)", ("m",)),
            ReplaceDuringApproval(),
        )
        assert result.state == "delivered"
        assert observed == [b"original"]

    asyncio.run(scenario())
