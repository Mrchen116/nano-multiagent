"""Atomic preparation rejects failures before any channel receives draft text."""

from pathlib import Path

import pytest

from personal_assistant.gateway.reply_images import (
    ImageDeliveryError,
    ReplyImageContext,
    ReplyImages,
    open_local_sources,
)

PNG = b"\x89PNG\r\n\x1a\nfixture"


def ctx(tmp_path: Path, key="draft"):
    return ReplyImageContext(key, "owner", "agent", "run", "bubble", tmp_path)


def test_outside_exports_is_bound_to_open_descriptor(tmp_path):
    source = tmp_path / "outside.png"
    source.write_bytes(PNG)
    markdown = f"![image](<{source}>)"
    store = ReplyImages(tmp_path / "state")
    with open_local_sources(tmp_path, markdown) as files:
        source.unlink()
        source.write_bytes(b"replacement must not be read")
        prepared = store.prepare(ctx(tmp_path), markdown, local_files=files)
    assert store.image_bytes(prepared.images[0]) == PNG


@pytest.mark.parametrize(
    "kind,code",
    [
        ("missing", "file_not_found"),
        ("symlink", "symlink_not_allowed"),
        ("directory", "not_regular_file"),
        ("text", "unsupported_image_type"),
    ],
)
def test_failure_is_private_and_prevents_entire_message(tmp_path, kind, code):
    source = tmp_path / "source.png"
    if kind == "symlink":
        other = tmp_path / "other.png"
        other.write_bytes(PNG)
        source.symlink_to(other)
    elif kind == "directory":
        source.mkdir()
    elif kind == "text":
        source.write_text("not image")
    store = ReplyImages(tmp_path / "state")
    with pytest.raises(ImageDeliveryError) as caught:
        store.prepare(ctx(tmp_path), f"Done! ![result](<{source}>)")
    result = caught.value.as_result(target="c_target", draft_id="draft")
    assert result["status"] == "delivery_failed"
    assert result["images"][0]["error_code"] == code
    assert store.load("draft") is None


def test_receipts_survive_restart(tmp_path):
    store = ReplyImages(tmp_path / "state")
    store.record_delivery(
        "draft", "feishu:chat", {"status": "delivered", "message_id": "om_known"}
    )
    assert (
        ReplyImages(tmp_path / "state").delivery_receipt("draft", "feishu:chat")[
            "message_id"
        ]
        == "om_known"
    )


@pytest.mark.asyncio
async def test_im_upload_failure_never_becomes_public_placeholder(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(PNG)
    store = ReplyImages(tmp_path / "state")
    prepared = store.prepare(ctx(tmp_path), f"Done! ![result](<{source}>)")
    with pytest.raises(ImageDeliveryError) as caught:
        await store.project_im(prepared, "c_target", agent_id="agent")
    assert caught.value.images[0]["error_code"] == "upload_failed"
