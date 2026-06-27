"""Capability payload baseline guard (refactor-406-M2, design 风险 2).

The reporter's IM capability payload (node.register flags + node.capabilities +
agent.capabilities.resolve) is the highest-risk migration surface in M2: the data
source switches from SDK-forwarded registry/resolver/profile internals to the
neutral ``kernel.list_*`` queries with a Gateway projection layer (决策 4).

The migration invariant (design 风险 2) is **byte-for-byte payload identity**:
models / skills / tools / features / defaults / order must not drift one byte.

This module pins the *pre-migration* payload shape as an executable baseline.
It is recorded against:

- the conftest-fixed model registry (deterministic models/default),
- a controlled ``HOME`` so skill discovery roots (``~/.nanoassistant/skills``,
  ``~/.claude/skills``, ``~/.codex/skills``) resolve to controlled empty dirs —
  removing the only environment-dependent input (the operator's real
  ``~/.claude/skills``), and
- a controlled workspace seeded with two known skills.

When R2 reroutes the reporter onto ``kernel.list_*`` + Gateway projection, the
SAME controlled inputs must reproduce the SAME payload here. Red means drift —
stop and fix the projection before proceeding.
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
    """Seed user-level skills the pre-refactor reporter advertises.

    The pre-refactor reporter's PA skill search roots are 4-tier: workspace
    ``<ws>/.nanoassistant/skills`` + global ``~/.nanoassistant/skills`` + compat
    ``~/.claude/skills`` + ``~/.codex/skills``. These global/compat user-level skills
    are part of the advertised capability and must survive the migration (R-CFG-2).
    """
    _write_skill(home / ".nanoassistant" / "skills", "global-pa-skill", "Global PA")
    _write_skill(home / ".claude" / "skills", "compat-claude-skill", "Compat Claude")
    _write_skill(home / ".codex" / "skills", "compat-codex-skill", "Compat Codex")


@pytest.fixture
def controlled_caps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Yield reporter payload builders under a fully controlled environment.

    HOME is redirected to an empty tmp dir so the three skill compat/global roots
    (``~/.nanoassistant/skills``, ``~/.claude/skills``, ``~/.codex/skills``) are
    empty — skill output is then determined solely by the controlled workspace.
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

    # refactor-406-M2: the reporter now projects from a live Kernel's neutral
    # list_* queries (决策 4). Build the real PA kernel so the baseline exercises
    # the actual post-migration data path under the controlled environment.
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

# User-level skills (global + compat) advertised on every PA agent regardless of
# workspace — part of the pre-refactor capability and a migration invariant.
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

GOLDEN_FLAGS = {"relay": True, "send_message": True, "config_sync": True}
GOLDEN_DEFAULT_SYSTEM_PROMPT = ""


def _sorted_skills(skills: list[dict[str, str]]) -> list[dict[str, str]]:
    # feat-430: drop the volatile ``location`` (absolute SKILL.md path varies by host)
    # before the byte-identity golden compare; location presence is asserted separately.
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
# Baseline assertions
# ---------------------------------------------------------------------------


def test_node_capabilities_payload_matches_baseline(controlled_caps) -> None:
    """node.capabilities payload reproduces the recorded baseline (design 风险 2)."""
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
    assert payload["default_system_prompt"] == GOLDEN_DEFAULT_SYSTEM_PROMPT


def test_agent_capabilities_payload_matches_baseline(controlled_caps) -> None:
    """agent.capabilities.resolve payload reproduces the baseline (design 风险 2).

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


def test_node_register_flags_payload_matches_baseline(controlled_caps) -> None:
    """node.register capability flags reproduce the baseline (design 风险 2).

    node.register carries only the boolean flags (no models/skills/tools), per
    ReporterCapabilities.register_flags_payload.
    """
    ur, kernel, _workspace = controlled_caps
    caps = ur.build_runtime_capabilities(kernel)
    flags = caps.register_flags_payload()
    assert flags == GOLDEN_FLAGS
