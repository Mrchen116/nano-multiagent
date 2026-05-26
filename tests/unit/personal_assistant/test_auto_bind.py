"""refactor-381: cover the NANO_MULTIAGENT_AUTO_BIND env-gated path through
_IMBootstrapClient.ensure_node_binding and the _extract_bind_token helper.

bugfix-380 retro identified the IM node-binding step as a worktree-e2e blocker
(operator must click a URL — automation cannot). The fix routes the same flow
through POST /im/v1/bind {action: confirm, bind_token: ...} when the env var
is set, mirroring what the IM frontend does when the user clicks "confirm".
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personal_assistant.main import _IMBootstrapClient, _extract_bind_token


class TestExtractBindToken:
    def test_extracts_token_from_token_query_param(self) -> None:
        assert _extract_bind_token("http://x/bind/confirm?token=abc123") == "abc123"

    def test_extracts_bind_token_alias(self) -> None:
        # Older fixtures / clients may emit `bind_token=` instead of `token=`.
        assert _extract_bind_token("http://x/bind/confirm?bind_token=xyz") == "xyz"

    def test_missing_token_returns_none(self) -> None:
        assert _extract_bind_token("http://x/bind/confirm") is None

    def test_prefers_token_over_bind_token(self) -> None:
        # When both appear, `token` wins — matches IM's canonical query param.
        url = "http://x/bind/confirm?token=primary&bind_token=fallback"
        assert _extract_bind_token(url) == "primary"

    def test_handles_extra_params(self) -> None:
        url = "http://x/?other=1&token=tk&extra=2"
        assert _extract_bind_token(url) == "tk"


class TestAutoBindFlow:
    def _make_client(self) -> tuple[_IMBootstrapClient, MagicMock, list, list]:
        """Build an _IMBootstrapClient wired to MagicMock httpx + capture lists."""
        client = MagicMock()
        start_resp = MagicMock()
        start_resp.json.return_value = {"bind_url": "http://x/bind/confirm?token=tok42"}
        start_resp.raise_for_status.return_value = None
        confirm_resp = MagicMock()
        confirm_resp.raise_for_status.return_value = None

        def post(path: str, json: dict | None = None):
            if json and json.get("action") == "start":
                return start_resp
            if json and json.get("action") == "confirm":
                assert json.get("bind_token") == "tok42"
                return confirm_resp
            raise AssertionError(f"unexpected POST: {path} {json}")

        client.post.side_effect = post

        opened_urls: list = []
        feedback: list = []
        bc = _IMBootstrapClient(
            base_url="http://x",
            token="dummy",
            client=client,
            browser_opener=lambda *a, **k: opened_urls.append(a),
            feedback_sink=lambda *a: feedback.append(a),
        )
        # Bypass _wait_for_owner network polling — pretend node has no owner yet.
        bc._wait_for_owner = lambda *, node_id: ("", "http://x")  # type: ignore[method-assign]
        return bc, client, opened_urls, feedback

    def test_auto_bind_env_set_confirms_without_browser(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NANO_MULTIAGENT_AUTO_BIND", "1")
        bc, client, opened_urls, feedback = self._make_client()

        result = bc.ensure_node_binding(node_id="test-node")

        assert result is None, "auto-bind should return None (binding complete)"
        assert opened_urls == [], "auto-bind must NOT open a browser"
        # Verify confirm POST happened.
        post_calls = [c for c in client.post.call_args_list]
        actions = [c.kwargs["json"]["action"] for c in post_calls]
        assert actions == ["start", "confirm"]
        # User-visible feedback announces success.
        assert any("auto-bound" in f[1] for f in feedback)

    def test_auto_bind_env_unset_falls_back_to_browser(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NANO_MULTIAGENT_AUTO_BIND", raising=False)
        bc, client, opened_urls, feedback = self._make_client()

        result = bc.ensure_node_binding(node_id="test-node")

        assert result == "http://x/bind/confirm?token=tok42"
        assert opened_urls, "legacy path must open the browser"
        # No confirm POST in legacy path.
        post_calls = [c for c in client.post.call_args_list]
        actions = [c.kwargs["json"]["action"] for c in post_calls]
        assert actions == ["start"]
        assert any("waiting for IM binding" in f[1] for f in feedback)

    def test_auto_bind_missing_token_raises_startup_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from personal_assistant.main import GatewayStartupError

        monkeypatch.setenv("NANO_MULTIAGENT_AUTO_BIND", "1")
        client = MagicMock()
        # bind_url with no token query param — auto-bind should bail fast.
        start_resp = MagicMock()
        start_resp.json.return_value = {"bind_url": "http://x/bind/confirm"}
        start_resp.raise_for_status.return_value = None
        client.post.return_value = start_resp

        bc = _IMBootstrapClient(
            base_url="http://x",
            token="dummy",
            client=client,
            browser_opener=lambda *a, **k: None,
            feedback_sink=lambda *a: None,
        )
        bc._wait_for_owner = lambda *, node_id: ("", "http://x")  # type: ignore[method-assign]

        with pytest.raises(GatewayStartupError, match="missing token"):
            bc.ensure_node_binding(node_id="test-node")
