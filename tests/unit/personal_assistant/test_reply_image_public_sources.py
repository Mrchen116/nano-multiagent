"""Public/data image snapshots preserve successful neighbours and failure reasons."""

import base64
from pathlib import Path

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.gateway.reply_images import (
    ImageDeliveryError,
    ReplyImageContext,
    ReplyImages,
)


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9ioAAAAASUVORK5CYII="
)


def _data_url(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


@pytest.mark.parametrize("outcome", ["ready", "limit", "type"])
def test_public_source_preparation_preserves_snapshot_or_specific_local_failure(
    tmp_path: Path, outcome: str
) -> None:
    content = {
        "ready": _PNG + b"different-source",
        "limit": _PNG + b"x" * (10 * 1024 * 1024),
        "type": b"<svg xmlns='http://www.w3.org/2000/svg'/>",
    }[outcome]
    source = _data_url(content)
    images = ReplyImages(tmp_path / "state")
    context = ReplyImageContext("run:bubble:0", "owner", "agent", "run", "0", tmp_path)

    markdown = f"before ![candidate]({source}) middle ![valid]({_data_url(_PNG)}) after"
    if outcome != "ready":
        with pytest.raises(ImageDeliveryError) as error:
            images.prepare(context, markdown)
        assert error.value.images[0]["error_code"] == outcome
        assert images.load(context.output_key) is None
        return
    prepared = images.prepare(context, markdown)
    candidate, valid = prepared.images
    assert images.image_bytes(valid) == _PNG
    assert images.image_bytes(candidate) == content
    assert candidate.status == valid.status == "ready"
    assert (
        prepared.markdown_template
        == "before ![candidate](nano-image-pending:0) middle ![valid](nano-image-pending:1) after"
    )
    assert images.load(context.output_key) == prepared


def test_remote_markdown_preserves_text_without_automatic_download(tmp_path):
    images = ReplyImages(tmp_path / "state")
    context = ReplyImageContext("run:bubble:0", "owner", "agent", "run", "0", tmp_path)
    prepared = images.prepare(
        context, "before ![remote](http://127.0.0.1/private) after"
    )
    assert (
        prepared.markdown_template == "before [remote](http://127.0.0.1/private) after"
    )
    assert prepared.images == []
