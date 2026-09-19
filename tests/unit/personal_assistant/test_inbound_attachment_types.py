"""Attachment MIME and legacy image locators share one classification contract."""

import pytest

from personal_assistant.gateway.inbound_attachments import is_image_attachment


@pytest.mark.parametrize(
    ("descriptor", "expected"),
    [
        ({"content_type": " Image/PNG ; charset=binary", "url": "/files/1"}, True),
        ({"content_type": "text/plain", "file_name": "fake.png"}, False),
        ({"content_type": "application/octet-stream", "file_name": "photo.JPG"}, True),
        ({"url": "https://im.example/a.png?download=1"}, True),
        ({"url": "/im/v1/conversations/c/images/123"}, True),
        ({"url": "data:image/png;base64,broken"}, True),
        ({"url": "/im/v1/conversations/c/attachments/123"}, False),
        ({"content_type": "application/octet-stream", "file_name": "a.zip"}, False),
    ],
)
def test_image_classification_preserves_declared_types_and_legacy_locators(
    descriptor, expected
):
    assert is_image_attachment(descriptor) is expected
