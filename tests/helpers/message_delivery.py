"""Construct the real Gateway delivery owner with isolated durable storage."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from personal_assistant.gateway.message_delivery import MessageDelivery
from personal_assistant.gateway.reply_images import ReplyImages


def message_delivery(
    *, connection=None, images=None, registry=None, router=None, shadow_publisher=None
):
    directory = TemporaryDirectory()
    owner = MessageDelivery(
        images=images or ReplyImages(Path(directory.name)),
        contexts=SimpleNamespace(get=lambda _: None),
        catalog=None,
        registry=registry,
        router=router,
        connection=connection,
        image_connection=None,
        tracker=None,
        kernel=None,
        owner_id="owner",
        writer=None,
        notify_pending=lambda: None,
        shadow_publisher=shadow_publisher,
    )
    owner._test_directory = directory
    return owner


def shadow_sync_with_delivery(
    *, images=None, before_publish=None, after_publish=None, **kwargs
):
    """Wire shadow preparation and publication to one real durable store."""
    from personal_assistant.gateway.shadow_reply_publisher import ShadowReplyPublisher
    from personal_assistant.gateway.shadow_sync import IMShadowConversationSync

    publisher = None
    if kwargs.get("saga_store") is not None:
        publisher = ShadowReplyPublisher(
            base_url=kwargs["base_url"],
            gateway_token_getter=kwargs["gateway_token_getter"],
            saga_store=kwargs["saga_store"],
            transport=kwargs.get("transport"),
            timeout_seconds=kwargs.get("timeout_seconds", 3.0),
            before_publish=before_publish,
            after_publish=after_publish,
        )
    delivery = message_delivery(images=images, shadow_publisher=publisher)
    return IMShadowConversationSync(delivery_provider=lambda: delivery, **kwargs)
