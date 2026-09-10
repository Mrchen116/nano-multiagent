"""Durable reply image preparation at the Gateway resource boundary."""

from pathlib import Path

import pytest

from personal_assistant.gateway.reply_images import (
    MAX_IMAGE_BYTES,
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
    reply = store.prepare(
        ctx, f"before ![exact]({exact}) middle ![large]({oversized}) after"
    )

    assert "![exact](nano-image-pending:0)" in reply.markdown_template
    assert "（图片未能展示：超过图片数量或大小限制）" in reply.markdown_template
    assert reply.markdown_template.startswith("before ")
    assert reply.markdown_template.endswith(" after")
    assert len(store.image_bytes(reply.images[0])) == MAX_IMAGE_BYTES
    assert reply.images[1].error_code == "limit"


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
        reply = ReplyImages(tmp_path / "state").prepare(
            ctx,
            f"![unreadable]({unreadable}) ![linked]({exports / 'linked-parent/image.png'})",
        )
    finally:
        unreadable.chmod(0o600)

    assert reply.markdown_template.count("图片来源不可用") == 2
    assert all(image.error_code == "source" for image in reply.images)


@pytest.mark.parametrize("kind", ["outside", "symlink", "directory", "wrong_type"])
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
    reply = ReplyImages(tmp_path / "state").prepare(
        ctx, f"text ![bad]({bad}) ![ok]({good}) end"
    )
    assert "图片未能展示" in reply.markdown_template
    assert str(tmp_path) not in reply.markdown_template
    assert "![ok](nano-image-pending:1)" in reply.markdown_template
    assert reply.markdown_template.startswith("text ")
    assert reply.markdown_template.endswith(" end")


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
    reply = ReplyImages(tmp_path / "state").prepare(ctx, body)
    assert reply.markdown_template.startswith(code)
    assert reply.markdown_template.count("nano-image-pending:") == 5
    assert "图片未能展示" in reply.markdown_template


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
    reply = store.prepare(ctx, f"{code}Before ![good]({source}) after {tail}")
    assert reply.markdown_template.startswith(
        code + "Before ![good](nano-image-pending:0) after "
    )
    assert "图片未能展示" in reply.markdown_template
    assert "/private/exports" not in reply.markdown_template
    assert store.load(ctx.output_key) == reply
    assert len(reply.images) == 1


def test_invalid_closed_image_is_local_failure_and_following_prose_survives(
    tmp_path: Path,
) -> None:
    reply = ReplyImages(tmp_path / "state").prepare(
        context(tmp_path), "Before ![bad](/private/unquoted image.png) following prose"
    )
    assert reply.markdown_template.startswith("Before ")
    assert reply.markdown_template.endswith(" following prose")
    assert "图片未能展示" in reply.markdown_template
    assert "/private" not in reply.markdown_template
