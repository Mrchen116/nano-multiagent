"""Guard the current IM capability wire payload.

The node and agent capability operations expose an ordered protocol containing
models, skills, tools, features and defaults. The contract is recorded against:

- the conftest-fixed model registry (deterministic models/default),
- a controlled ``HOME`` so skill discovery roots (``~/.nanoassistant/skills``,
  ``~/.claude/skills``, ``~/.codex/skills``) resolve to controlled empty dirs —
  removing the only environment-dependent input (the operator's real
  ``~/.claude/skills``), and
- a controlled workspace seeded with two known skills.

Controlled inputs must reproduce the same public payload; absolute skill locations
are validated structurally because their prefixes vary by host.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Controlled environment: isolate skill discovery from the operator's real HOME
# ---------------------------------------------------------------------------


def _write_skill(root: Path, name: str, desc: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\nbody\n",
        encoding="utf-8",
    )


def _seed_workspace_skills(workspace: Path) -> None:
    """Seed two known skills under <workspace>/.nanoassistant/skills."""
    skills_root = workspace / ".nanoassistant" / "skills"
    _write_skill(skills_root, "alpha-skill", "Alpha skill for baseline")
    _write_skill(skills_root, "beta-skill", "Beta skill for baseline")


def _seed_user_level_skills(home: Path) -> None:
    """Seed user-level skills advertised by the current reporter.

    PA skill search roots are four-tier: workspace
    ``<ws>/.nanoassistant/skills`` + global ``~/.nanoassistant/skills`` + compat
    ``~/.claude/skills`` + ``~/.codex/skills``. These global/compat user-level skills
    are part of the advertised capability.
    """
    _write_skill(home / ".nanoassistant" / "skills", "global-pa-skill", "Global PA")
    _write_skill(home / ".claude" / "skills", "compat-claude-skill", "Compat Claude")
    _write_skill(home / ".codex" / "skills", "compat-codex-skill", "Compat Codex")


@pytest.fixture
def controlled_caps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Yield reporter payload builders under a fully controlled environment.

    HOME and CODEX_HOME are redirected to a temporary tree, then the workspace and
    three user-level roots are seeded explicitly so host state cannot affect output.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))
    # CODEX_HOME may shadow ~/.codex; pin it under the fake home too.
    monkeypatch.setenv("CODEX_HOME", str(fake_home / ".codex"))
    _seed_user_level_skills(fake_home)

    workspace = tmp_path / "agent-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    _seed_workspace_skills(workspace)

    # Kernel repo_root is a separate empty dir (no per-workspace skills) — it stands
    # in for the gateway's working dir at node level. Node-level skills then resolve
    # to the shared user-level (global/compat) roots only; agent-level skills add the
    # per-agent workspace on top (R-CFG-2). Keeping them separate mirrors production
    # (the gateway dir is not an agent workspace).
    kernel_root = tmp_path / "kernel-root"
    kernel_root.mkdir(parents=True, exist_ok=True)

    # Build the real PA kernel so the contract exercises the production projection
    # from neutral Kernel list_* queries under the controlled environment.
    import tests.conftest as _conftest  # noqa: PLC0415
    from agent.sdk import LLMConfig  # noqa: PLC0415
    from personal_assistant.product import build_pa_kernel  # noqa: PLC0415

    llm = LLMConfig.from_payload(_conftest._DEFAULT_TEST_PAYLOAD)
    kernel = build_pa_kernel(llm=llm, cron_services={}, repo_root=kernel_root)

    from personal_assistant.reporter import upstream_reporter as ur  # noqa: PLC0415

    return ur, kernel, workspace


# ---------------------------------------------------------------------------
# Golden: environment-independent payload fields (pinned byte-for-byte)
# ---------------------------------------------------------------------------

# models: conftest _DEFAULT_TEST_PAYLOAD order, deduped preserving order.
# bugfix-429 R5: each model carries its registered provider/format.
GOLDEN_MODELS: list[dict[str, str]] = [
    {"name": "kimiCoding:K2.6", "provider": "anthropic"},
    {"name": "volcanoArk:doubao-seed-2-0-code-preview-260215", "provider": "anthropic"},
    {"name": "codex_oauth:gpt-5.5", "provider": "openai_compat"},
]
GOLDEN_PLATFORM_DEFAULT_MODEL = "kimiCoding:K2.6"

# tools: PERSONAL_ASSISTANT_PROFILE default_tool_ids (default_on=True) then
# optional_tool_ids (default_on=False), in declaration order, description="".
GOLDEN_TOOLS: list[dict[str, object]] = [
    {"name": "read", "description": "", "default_on": True},
    {"name": "write", "description": "", "default_on": True},
    {"name": "edit", "description": "", "default_on": True},
    {"name": "bash", "description": "", "default_on": True},
    {"name": "agent", "description": "", "default_on": True},
    {"name": "task_stop", "description": "", "default_on": True},
    {"name": "web_fetch", "description": "", "default_on": True},
    {"name": "web_search", "description": "", "default_on": True},
    {"name": "skill_manage", "description": "", "default_on": True},
    {"name": "skill_view", "description": "", "default_on": True},
    {"name": "memory", "description": "", "default_on": True},
    {"name": "send_message", "description": "", "default_on": False},
    {"name": "cron", "description": "", "default_on": False},
]

# node-level features: every entry available=True (no per-agent allowlist), in
# FEATURE_REGISTRY declaration order, with full i18n keys (Gateway-owned text).
GOLDEN_NODE_FEATURES: list[dict[str, object]] = [
    {
        "key": "memory_curation",
        "label_i18n": "feature.memory_curation.label",
        "help_i18n": "feature.memory_curation.help",
        "default_on": True,
        "available": True,
        "requires_tool": "memory",
    },
    {
        "key": "skill_creation",
        "label_i18n": "feature.skill_creation.label",
        "help_i18n": "feature.skill_creation.help",
        "default_on": True,
        "available": True,
        "requires_tool": "skill_manage",
    },
    {
        "key": "cron_scheduling",
        "label_i18n": "feature.cron_scheduling.label",
        "help_i18n": "feature.cron_scheduling.help",
        "default_on": False,
        "available": True,
        "requires_tool": "cron",
    },
    {
        "key": "heartbeat",
        "label_i18n": "feature.heartbeat.label",
        "help_i18n": "feature.heartbeat.help",
        "default_on": False,
        "available": True,
        "requires_tool": None,
    },
]

# agent-level features: available depends on tool_allowlist. With allowlist
# {"memory", "cron"}: memory_curation/cron_scheduling available, skill_creation
# unavailable (skill_manage not in allowlist), heartbeat available (no tool).
GOLDEN_AGENT_FEATURES_ALLOWLIST = ("memory", "cron")
GOLDEN_AGENT_FEATURES: list[dict[str, object]] = [
    {
        "key": "memory_curation",
        "label_i18n": "feature.memory_curation.label",
        "help_i18n": "feature.memory_curation.help",
        "default_on": True,
        "available": True,
        "requires_tool": "memory",
    },
    {
        "key": "skill_creation",
        "label_i18n": "feature.skill_creation.label",
        "help_i18n": "feature.skill_creation.help",
        "default_on": True,
        "available": False,
        "requires_tool": "skill_manage",
    },
    {
        "key": "cron_scheduling",
        "label_i18n": "feature.cron_scheduling.label",
        "help_i18n": "feature.cron_scheduling.help",
        "default_on": False,
        "available": True,
        "requires_tool": "cron",
    },
    {
        "key": "heartbeat",
        "label_i18n": "feature.heartbeat.label",
        "help_i18n": "feature.heartbeat.help",
        "default_on": False,
        "available": True,
        "requires_tool": None,
    },
]

# User-level skills (global + compat) are advertised on every PA agent regardless
# of workspace.
GOLDEN_USER_LEVEL_SKILLS: list[dict[str, str]] = [
    {"name": "compat-claude-skill", "description": "Compat Claude"},
    {"name": "compat-codex-skill", "description": "Compat Codex"},
    {"name": "global-pa-skill", "description": "Global PA"},
]

# Node-level skills: user-level (global/compat) skills only — the node-level payload
# has no per-agent workspace, so only the shared user-level roots contribute.
GOLDEN_NODE_SKILLS: list[dict[str, str]] = list(GOLDEN_USER_LEVEL_SKILLS)

# Agent-level skills: the controlled workspace's two seeded skills PLUS the shared
# user-level skills (workspace + global + compat roots, deduped+sorted by name).
GOLDEN_AGENT_SKILLS: list[dict[str, str]] = sorted(
    [
        {"name": "alpha-skill", "description": "Alpha skill for baseline"},
        {"name": "beta-skill", "description": "Beta skill for baseline"},
        *GOLDEN_USER_LEVEL_SKILLS,
    ],
    key=lambda s: s["name"],
)

GOLDEN_FLAGS = {
    "relay": True,
    "send_message": True,
    "config_sync": True,
    "channel_bootstrap": True,
    "agent_config_fingerprint_schema": "agent-config-v2",
}


def _sorted_skills(skills: list[dict[str, str]]) -> list[dict[str, str]]:
    # Absolute SKILL.md prefixes vary by host, so location has a separate structural
    # assertion while stable protocol fields remain exact.
    return sorted(
        ({"name": s["name"], "description": s["description"]} for s in skills),
        key=lambda s: s["name"],
    )


def _assert_skills_carry_location(skills: list[dict[str, str]]) -> None:
    # feat-430: every discovered skill exposes its SKILL.md path ending in SKILL.md.
    for skill in skills:
        location = skill.get("location")
        assert isinstance(location, str) and location.endswith(
            f"{skill['name']}/SKILL.md"
        ), f"skill {skill['name']!r} missing a valid location: {location!r}"


# ---------------------------------------------------------------------------
# Protocol assertions
# ---------------------------------------------------------------------------


def test_node_capabilities_payload_matches_contract(controlled_caps) -> None:
    """node.capabilities returns the current wire contract."""
    ur, kernel, _workspace = controlled_caps
    payload = ur.build_node_capabilities_payload(kernel)

    assert list(payload["models"]) == GOLDEN_MODELS
    assert payload["platform_default_model"] == GOLDEN_PLATFORM_DEFAULT_MODEL
    assert list(payload["tools"]) == GOLDEN_TOOLS
    assert list(payload["features"]) == GOLDEN_NODE_FEATURES
    assert _sorted_skills(list(payload["skills"])) == GOLDEN_NODE_SKILLS
    _assert_skills_carry_location(list(payload["skills"]))
    assert payload["relay"] == GOLDEN_FLAGS["relay"]
    assert payload["send_message"] == GOLDEN_FLAGS["send_message"]
    assert payload["config_sync"] == GOLDEN_FLAGS["config_sync"]
    assert "default_system_prompt" not in payload


def test_agent_capabilities_payload_matches_contract(controlled_caps) -> None:
    """agent.capabilities.resolve returns the current wire contract.

    Exercises per-workspace skill discovery (workspace-seeded skills only, global
    roots empty) AND per-allowlist feature availability — the two R-CFG invariants.
    """
    ur, kernel, workspace = controlled_caps
    payload = ur.build_agent_capabilities_payload(
        kernel,
        workspace_root=str(workspace),
        tool_allowlist=GOLDEN_AGENT_FEATURES_ALLOWLIST,
    )

    assert list(payload["models"]) == GOLDEN_MODELS
    assert payload["platform_default_model"] == GOLDEN_PLATFORM_DEFAULT_MODEL
    assert list(payload["tools"]) == GOLDEN_TOOLS
    assert list(payload["features"]) == GOLDEN_AGENT_FEATURES
    assert _sorted_skills(list(payload["skills"])) == GOLDEN_AGENT_SKILLS
    _assert_skills_carry_location(list(payload["skills"]))


def test_node_register_flags_payload_matches_contract(controlled_caps) -> None:
    """node.register capability flags return the current wire contract.

    node.register carries only the boolean flags (no models/skills/tools), per
    ReporterCapabilities.register_flags_payload.
    """
    ur, kernel, _workspace = controlled_caps
    caps = ur.build_runtime_capabilities(kernel)
    flags = caps.register_flags_payload()
    assert flags == GOLDEN_FLAGS
