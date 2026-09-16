"""Construct the real Gateway delivery owner with isolated durable storage."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from personal_assistant.gateway.message_delivery import MessageDelivery
from personal_assistant.gateway.reply_images import ReplyImages


def message_delivery(*, connection=None, images=None, registry=None, router=None):
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
    )
    owner._test_directory = directory
    return owner
