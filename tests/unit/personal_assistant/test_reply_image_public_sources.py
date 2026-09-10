"""Public/data image snapshots preserve successful neighbours and failure reasons."""

import base64
import io
from pathlib import Path
import socket
from unittest.mock import MagicMock

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu import client
from personal_assistant.gateway.reply_images import ReplyImageContext, ReplyImages


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9ioAAAAASUVORK5CYII="
)


def _data_url(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


@pytest.mark.parametrize("source_kind", ["data", "https"])
@pytest.mark.parametrize("outcome", ["ready", "limit", "type"])
def test_public_source_preparation_preserves_snapshot_or_specific_local_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_kind: str, outcome: str
) -> None:
    content = {
        "ready": _PNG + b"different-source",
        "limit": _PNG + b"x" * (10 * 1024 * 1024),
        "type": b"<svg xmlns='http://www.w3.org/2000/svg'/>",
    }[outcome]
    if source_kind == "https":
        monkeypatch.setattr(
            client.socket,
            "getaddrinfo",
            lambda *_args, **_kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
            ],
        )
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        response.read.side_effect = io.BytesIO(content).read
        monkeypatch.setattr(
            client.http.client, "HTTPSConnection", lambda *_args, **_kwargs: connection
        )
        source = "https://images.example/chart.png"
    else:
        source = _data_url(content)
    images = ReplyImages(tmp_path / "state")
    context = ReplyImageContext("run:bubble:0", "owner", "agent", "run", "0", tmp_path)

    prepared = images.prepare(
        context,
        f"before ![candidate]({source}) middle ![valid]({_data_url(_PNG)}) after",
    )

    candidate, valid = prepared.images
    assert images.image_bytes(valid) == _PNG
    assert valid.status == "ready"
    if outcome == "ready":
        assert candidate.status == "ready"
        assert images.image_bytes(candidate) == content
        candidate_projection = "![candidate](nano-image-pending:0)"
    else:
        assert candidate.status == "failed"
        assert candidate.error_code == outcome
        reason = "超过图片数量或大小限制" if outcome == "limit" else "图片格式不支持"
        candidate_projection = f"（图片未能展示：{reason}）"
    assert (
        prepared.markdown_template
        == f"before {candidate_projection} middle ![valid](nano-image-pending:1) after"
    )
    assert images.load(context.output_key) == prepared
