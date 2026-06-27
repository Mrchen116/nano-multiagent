"""feat-430: capabilities API forwards skill SKILL.md ``location`` to the frontend.

The IM slash picker distinguishes same-named skills at different paths by their
location; the capabilities response must carry it through from the Gateway payload.
"""

from __future__ import annotations

from IM.api.routes.agents import AllowlistOptionResponse, coerce_allowlist_options


def test_coerce_allowlist_options_forwards_location() -> None:
    options = coerce_allowlist_options(
        [
            {
                "name": "doc",
                "description": "doc skill",
                "location": "/ws/.nanoassistant/skills/doc/SKILL.md",
            }
        ]
    )
    assert len(options) == 1
    assert options[0].location == "/ws/.nanoassistant/skills/doc/SKILL.md"


def test_coerce_allowlist_options_location_defaults_to_none() -> None:
    """Older Gateway payloads without ``location`` degrade to None, not an error."""
    options = coerce_allowlist_options([{"name": "doc", "description": "d"}])
    assert options[0].location is None


def test_allowlist_option_response_location_is_optional() -> None:
    assert AllowlistOptionResponse(name="x").location is None
