"""feat-430: capabilities API forwards skill SKILL.md ``location`` to the frontend.

The IM slash picker distinguishes same-named skills at different paths by their
location; the capabilities response must carry it through from the Gateway payload.
"""

from __future__ import annotations

from IM.api.routes.agents import coerce_allowlist_options


def test_capability_options_preserve_current_and_legacy_skill_locations() -> None:
    options = coerce_allowlist_options(
        [
            {
                "name": "doc",
                "description": "doc skill",
                "location": "/ws/.nanoassistant/skills/doc/SKILL.md",
            },
            {"name": "legacy", "description": "old gateway"},
        ]
    )
    assert len(options) == 2
    assert options[0].location == "/ws/.nanoassistant/skills/doc/SKILL.md"
    assert options[1].location is None
