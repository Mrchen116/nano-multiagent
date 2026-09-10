"""IM lifecycle summaries must not expose raw reply image destinations."""

from unittest.mock import AsyncMock

import pytest

from personal_assistant.channels.base import (
    IMRelayIngress,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.config.local_store import NodeConfig
from personal_assistant.gateway.inbound_models import (
    RelayLifecycleUpdate,
    RoutedInbound,
)
from personal_assistant.gateway.runtime_delivery.lifecycle import (
    build_relay_lifecycle_callback,
)
from personal_assistant.reporter.upstream_reporter import UpstreamReporter


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["running", "completed"])
async def test_lifecycle_projects_images_in_reports_and_receipts_without_mutating_reply(
    phase: str,
) -> None:
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node"), agents=(), send_frame=lambda *_: None
    )
    manager = AsyncMock()
    callback = build_relay_lifecycle_callback(
        reporter=reporter, im_connection_manager_factory=lambda: manager
    )
    routed = RoutedInbound(
        message=InboundMessage(
            channel_name="web_relay",
            text="show image",
            external_user_id="owner",
            external_chat_id="conversation",
            is_group=False,
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id="relay",
                    idempotency_key="idem",
                    im_message_id="message",
                )
            ),
        )
    )
    code = "`![example](/example.png)`\n```md\n![example](/example.png)\n```"
    raw = (
        "before ![chart](</private/export/a b.png>) middle ![](data:image/png;base64,AAAA) after\n"
        + code
    )
    expected = "before [图片] middle [图片] after\n" + code
    update = RelayLifecycleUpdate(
        phase=phase,
        agent_id="agent",
        session_key="session",
        run_id="run",
        reply_text=raw,
    )

    await callback(routed, update)

    frames = {call.args[0]: call.args[1] for call in manager.send_json.call_args_list}
    assert frames["node.report"]["summary"] == expected
    if phase == "completed":
        assert frames["node.delivery_receipt"]["detail"] == expected
    assert update.reply_text == raw
