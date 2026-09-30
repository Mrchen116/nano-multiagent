"""A connected Gateway never starts the removed remote binding protocol."""

from unittest.mock import MagicMock
from personal_assistant.gateway.im_bootstrap import IMBootstrapClient


def test_auto_bind_does_not_claim_nodes_after_runtime_registration(monkeypatch):
    monkeypatch.setenv("NANO_MULTIAGENT_AUTO_BIND", "1")
    client = MagicMock()
    browser = MagicMock()
    bootstrap = IMBootstrapClient(
        base_url="http://im.test",
        token="device-runtime",
        client=client,
        browser_opener=browser,
    )
    assert bootstrap.ensure_node_binding(node_id="registered-node") is None
    client.post.assert_not_called()
    client.get.assert_not_called()
    browser.assert_not_called()
