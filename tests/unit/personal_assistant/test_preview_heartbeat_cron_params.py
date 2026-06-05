"""Tests for feat-394-M5 R2: prompt preview endpoint respects heartbeat/cron params.

R3-2 fix: PromptPreviewRequest must accept heartbeat_enabled/cron_enabled fields
so the preview reflects the requested toggle state, not just the stored profile state.

Background: acceptance.md Round 3 Issue R3-2 found that POST /im/v1/agents/{id}/prompt-preview
with {"heartbeat_enabled": false, "cron_enabled": true} in the body was ignored —
_extract_enabled reads from profile.heartbeat_json/cron_json regardless of request params.
All 4 combinations (hb T/F × cron T/F) returned identical prompts.

Fix: PromptPreviewRequest adds optional heartbeat_enabled / cron_enabled fields;
the route handler uses them when present, falling back to profile-stored values.
The IM gateway_handler.request_prompt_preview already forwarded these; the IM route
was the missing link.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch


class TestPromptPreviewRequestModel:
    """PromptPreviewRequest must expose heartbeat_enabled and cron_enabled fields."""

    def _get_model(self):
        from IM.api.routes.agents import PromptPreviewRequest

        return PromptPreviewRequest

    def test_accepts_heartbeat_enabled_true(self) -> None:
        """PromptPreviewRequest must accept heartbeat_enabled=True."""
        model = self._get_model()
        req = model(heartbeat_enabled=True)
        assert req.heartbeat_enabled is True

    def test_accepts_heartbeat_enabled_false(self) -> None:
        """PromptPreviewRequest must accept heartbeat_enabled=False."""
        model = self._get_model()
        req = model(heartbeat_enabled=False)
        assert req.heartbeat_enabled is False

    def test_accepts_cron_enabled_true(self) -> None:
        """PromptPreviewRequest must accept cron_enabled=True."""
        model = self._get_model()
        req = model(cron_enabled=True)
        assert req.cron_enabled is True

    def test_accepts_cron_enabled_false(self) -> None:
        model = self._get_model()
        req = model(cron_enabled=False)
        assert req.cron_enabled is False

    def test_defaults_to_none_when_absent(self) -> None:
        """When heartbeat_enabled/cron_enabled not provided, should be None (use profile)."""
        model = self._get_model()
        req = model()
        assert req.heartbeat_enabled is None
        assert req.cron_enabled is None

    def test_existing_fields_still_present(self) -> None:
        """Adding new fields must not remove existing ones."""
        model = self._get_model()
        req = model(
            features={"x": True},
            custom_prompt="hello",
            tool_ids=["read"],
            scenario="direct",
            skill_ids=["my_skill"],
            heartbeat_enabled=True,
            cron_enabled=False,
        )
        assert req.features == {"x": True}
        assert req.custom_prompt == "hello"
        assert req.tool_ids == ["read"]
        assert req.scenario == "direct"
        assert req.skill_ids == ["my_skill"]
        assert req.heartbeat_enabled is True
        assert req.cron_enabled is False


class TestPreviewRoutePassesParams:
    """agent_prompt_preview route must pass heartbeat_enabled/cron_enabled to gateway.

    When request body provides explicit heartbeat_enabled/cron_enabled, those values
    must override the profile-stored values (so preview is interactive).
    When absent (None), fall back to profile values (backward compat).
    """

    def _call_route(
        self,
        profile_hb_json: str | None,
        profile_cron_json: str | None,
        request_hb: "bool | None",
        request_cron: "bool | None",
        captured_calls: list,
    ):
        """Invoke the route and capture what gateway_handler.request_prompt_preview received."""
        import asyncio
        from IM.api.routes.agents import PromptPreviewRequest, agent_prompt_preview

        # feat-394 M9: effective_hb/cron now reads profile.features (not hb/cron_json).
        # Derive the features dict from the json payloads so the fallback path works.
        def _extract_enabled_from_json(s: "str | None") -> bool:
            if not s:
                return False
            try:
                obj = json.loads(s)
                return (
                    bool(obj.get("enabled", False)) if isinstance(obj, dict) else False
                )
            except (ValueError, TypeError):
                return False

        profile_features = {
            "heartbeat": _extract_enabled_from_json(profile_hb_json),
            "cron_scheduling": _extract_enabled_from_json(profile_cron_json),
        }

        mock_profile = MagicMock()
        mock_profile.node_id = "test-node"
        mock_profile.heartbeat_json = profile_hb_json
        mock_profile.cron_json = profile_cron_json
        mock_profile.features = profile_features

        mock_service = MagicMock()
        mock_service.get_profile_for_owner.return_value = mock_profile
        mock_service.workspace_root_for_profile.return_value = "/tmp/workspace"

        async def mock_request_preview(**kwargs):
            captured_calls.append(kwargs)
            return {"prompt": "## Runtime\n", "section_count": 1}

        mock_gateway = MagicMock()
        mock_gateway.request_prompt_preview = mock_request_preview

        mock_user = MagicMock()
        mock_user.owner_id = "owner-123"

        payload = PromptPreviewRequest(
            heartbeat_enabled=request_hb,
            cron_enabled=request_cron,
        )

        asyncio.run(
            agent_prompt_preview(
                agent_id="Alpha",
                payload=payload,
                user=mock_user,
                service=mock_service,
                gateway_handler=mock_gateway,
            )
        )

    def test_request_params_override_profile_when_explicit(self) -> None:
        """When request provides heartbeat_enabled=False, it overrides profile True."""
        profile_hb = json.dumps({"enabled": True})  # profile says heartbeat ON
        profile_cron = json.dumps({"enabled": True})  # profile says cron ON

        calls: list = []
        self._call_route(
            profile_hb_json=profile_hb,
            profile_cron_json=profile_cron,
            request_hb=False,  # request says OFF — must override profile
            request_cron=False,  # request says OFF — must override profile
            captured_calls=calls,
        )
        assert len(calls) == 1
        assert calls[0]["heartbeat_enabled"] is False, (
            "heartbeat_enabled=False from request body must override profile True. "
            "Got: " + repr(calls[0].get("heartbeat_enabled"))
        )
        assert calls[0]["cron_enabled"] is False, (
            "cron_enabled=False from request body must override profile True. "
            "Got: " + repr(calls[0].get("cron_enabled"))
        )

    def test_profile_used_when_request_param_absent(self) -> None:
        """When request does not provide heartbeat_enabled, profile value is used."""
        profile_hb = json.dumps({"enabled": True})
        profile_cron = json.dumps({"enabled": False})

        calls: list = []
        self._call_route(
            profile_hb_json=profile_hb,
            profile_cron_json=profile_cron,
            request_hb=None,  # absent: fall back to profile
            request_cron=None,  # absent: fall back to profile
            captured_calls=calls,
        )
        assert len(calls) == 1
        assert calls[0]["heartbeat_enabled"] is True, (
            "heartbeat_enabled should come from profile (True) when request param absent"
        )
        assert calls[0]["cron_enabled"] is False, (
            "cron_enabled should come from profile (False) when request param absent"
        )

    def test_request_false_overrides_profile_true_for_cron(self) -> None:
        """cron_enabled=False in request body must override profile True."""
        profile_hb = json.dumps({"enabled": True})
        profile_cron = json.dumps({"enabled": True})

        calls: list = []
        self._call_route(
            profile_hb_json=profile_hb,
            profile_cron_json=profile_cron,
            request_hb=True,
            request_cron=False,  # override profile True with False
            captured_calls=calls,
        )
        assert calls[0]["heartbeat_enabled"] is True
        assert calls[0]["cron_enabled"] is False
