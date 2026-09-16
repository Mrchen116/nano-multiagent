"""Durable reply image preparation at the Gateway resource boundary."""

from pathlib import Path

import pytest

from personal_assistant.gateway.reply_images import (
    MAX_IMAGE_BYTES,
    ImageDeliveryError,
    ReplyImageContext,
    ReplyImages,
)

PNG = b"\x89PNG\r\n\x1a\nfixture-image"
JPEG = b"\xff\xd8\xfffixture-image"
WEBP = b"RIFF\x00\x00\x00\x00WEBPfixture-image"


def context(tmp_path: Path, key: str = "run:bubble") -> ReplyImageContext:
    workspace = tmp_path / "workspace"
    (workspace / ".nanoassistant/exports").mkdir(parents=True, exist_ok=True)
    return ReplyImageContext(key, "owner", "agent", "run", "bubble", workspace)


def test_snapshot_survives_source_change_and_restart(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    source = ctx.workspace / ".nanoassistant/exports/图 one.png"
    source.write_bytes(PNG)
    store = ReplyImages(tmp_path / "state")
    reply = store.prepare(ctx, f"before ![图](<{source}>) after ![again](<{source}>)")
    assert len(reply.images) == 1
    assert reply.markdown_template.count("nano-image-pending:0") == 2
    source.unlink()
    restarted = ReplyImages(tmp_path / "state")
    recovered = restarted.prepare(ctx, "changed input must not replace snapshot")
    assert recovered == reply
    assert restarted.image_bytes(recovered.images[0]) == PNG


@pytest.mark.asyncio
async def test_hosted_im_image_reference_does_not_grant_another_chat_access(
    tmp_path: Path,
):
    url = "/im/v1/conversations/c_known/images/" + "a" * 32
    store = ReplyImages(tmp_path / "state")
    reply = store.prepare(
        context(tmp_path),
        f"before ![earlier]({url}) after",
        im_conversation_id="c_known",
    )
    assert (
        await store.project_im(reply, "c_known", agent_id="agent")
        == f"before ![earlier]({url}) after"
    )
    with pytest.raises(ImageDeliveryError):
        await store.project_im(reply, "c_elsewhere", agent_id="agent")


@pytest.mark.parametrize(
    "conversation_id, image_id",
    [
        ("c_elsewhere", "a" * 32),
        ("c_known", "not-an-image-id"),
        ("c_known", "../private.png"),
    ],
)
def test_only_exact_current_chat_image_reference_is_reused(
    tmp_path: Path, conversation_id: str, image_id: str
):
    url = f"/im/v1/conversations/{conversation_id}/images/{image_id}"
    store = ReplyImages(tmp_path / "state")
    with pytest.raises(ImageDeliveryError):
        store.prepare(
            context(tmp_path),
            f"before ![earlier]({url}) after",
            im_conversation_id="c_known",
        )


@pytest.mark.parametrize(
    ("suffix", "data", "content_type"),
    [("jpg", JPEG, "image/jpeg"), ("webp", WEBP, "image/webp")],
)
def test_local_jpeg_and_webp_are_snapshotted(
    tmp_path: Path, suffix: str, data: bytes, content_type: str
) -> None:
    ctx = context(tmp_path, f"run:{suffix}")
    source = ctx.workspace / f".nanoassistant/exports/image.{suffix}"
    source.write_bytes(data)

    store = ReplyImages(tmp_path / f"state-{suffix}")
    reply = store.prepare(ctx, f"![image]({source})")

    assert reply.markdown_template == "![image](nano-image-pending:0)"
    assert reply.images[0].content_type == content_type
    assert reply.images[0].file_name == f"image.{suffix}"
    assert store.image_bytes(reply.images[0]) == data


def test_local_size_boundary_preserves_exact_limit_and_fails_only_oversize(
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    exports = ctx.workspace / ".nanoassistant/exports"
    exact = exports / "exact.png"
    exact.write_bytes(PNG + b"x" * (MAX_IMAGE_BYTES - len(PNG)))
    oversized = exports / "oversized.png"
    with oversized.open("wb") as stream:
        stream.seek(MAX_IMAGE_BYTES)
        stream.write(b"x")

    store = ReplyImages(tmp_path / "state")
    with pytest.raises(ImageDeliveryError) as caught:
        store.prepare(
            ctx, f"before ![exact]({exact}) middle ![large]({oversized}) after"
        )
    assert caught.value.images[0]["error_code"] == "image_too_large"
    assert store.load(ctx.output_key) is None


def test_unreadable_file_and_symlinked_parent_are_rejected(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    exports = ctx.workspace / ".nanoassistant/exports"
    unreadable = exports / "unreadable.png"
    unreadable.write_bytes(PNG)
    unreadable.chmod(0)
    outside = tmp_path / "outside-directory"
    outside.mkdir()
    (outside / "image.png").write_bytes(PNG)
    (exports / "linked-parent").symlink_to(outside, target_is_directory=True)

    try:
        with pytest.raises(ImageDeliveryError) as caught:
            ReplyImages(tmp_path / "state").prepare(
                ctx,
                f"![unreadable]({unreadable}) ![linked]({exports / 'linked-parent/image.png'})",
            )
    finally:
        unreadable.chmod(0o600)
    assert {item["error_code"] for item in caught.value.images} == {
        "permission_denied",
        "symlink_not_allowed",
    }


@pytest.mark.parametrize("kind", ["symlink", "directory", "wrong_type"])
def test_local_failures_are_private_and_preserve_other_images(
    tmp_path: Path, kind: str
) -> None:
    ctx = context(tmp_path)
    exports = ctx.workspace / ".nanoassistant/exports"
    good = exports / "good.png"
    good.write_bytes(PNG)
    bad = exports / "bad.png"
    if kind == "outside":
        bad = tmp_path / "outside.png"
        bad.write_bytes(PNG)
    elif kind == "symlink":
        bad.symlink_to(good)
    elif kind == "directory":
        bad.mkdir()
    else:
        bad.write_text("not an image")
    with pytest.raises(ImageDeliveryError) as caught:
        ReplyImages(tmp_path / "state").prepare(
            ctx, f"text ![bad]({bad}) ![ok]({good}) end"
        )
    assert caught.value.images[0]["source"] == str(bad)


def test_code_examples_are_untouched_and_sixth_source_fails_locally(
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    source = ctx.workspace / ".nanoassistant/exports/one.png"
    source.write_bytes(PNG)
    code = f"`![inline]({source})`\n```md\n![fenced]({source})\n```\n\\![escaped]({source})\n"
    body = code
    for index in range(6):
        path = source.with_name(f"{index}.png")
        path.write_bytes(PNG)
        body += f"![{index}]({path})\n"
    with pytest.raises(ImageDeliveryError) as caught:
        ReplyImages(tmp_path / "state").prepare(ctx, body)
    assert caught.value.images[0]["ordinal"] == 6
    assert caught.value.images[0]["error_code"] == "too_many_images"


@pytest.mark.parametrize(
    "tail",
    ["![cut](/private/exports/secret.png", "![cut](</private/exports/my image.png"],
)
def test_final_preparation_sanitizes_truncated_image_without_losing_good_image(
    tmp_path: Path, tail: str
) -> None:
    ctx = context(tmp_path)
    source = ctx.workspace / ".nanoassistant/exports/good.png"
    source.write_bytes(PNG)
    code = "`![example](/private/example`\\![escaped](/private/example\n"
    store = ReplyImages(tmp_path / "state")
    with pytest.raises(ImageDeliveryError) as caught:
        store.prepare(ctx, f"{code}Before ![good]({source}) after {tail}")
    assert caught.value.images[0]["error_code"] == "invalid_image_reference"
    assert store.load(ctx.output_key) is None


def test_invalid_closed_image_is_local_failure_and_following_prose_survives(
    tmp_path: Path,
) -> None:
    with pytest.raises(ImageDeliveryError) as caught:
        ReplyImages(tmp_path / "state").prepare(
            context(tmp_path),
            "Before ![bad](/private/unquoted image.png) following prose",
        )
    assert caught.value.images[0]["error_code"] == "invalid_image_reference"
