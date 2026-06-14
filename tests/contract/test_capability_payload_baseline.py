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


def _seed_workspace_skills(workspace: Path) -> None:
    """Seed two known skills under <workspace>/.nanoassistant/skills."""
    skills_root = workspace / ".nanoassistant" / "skills"
    for name, desc in (
        ("alpha-skill", "Alpha skill for baseline"),
        ("beta-skill", "Beta skill for baseline"),
    ):
        d = skills_root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {desc}\n---\nbody\n",
            encoding="utf-8",
        )


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

    workspace = tmp_path / "agent-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    _seed_workspace_skills(workspace)

    from personal_assistant.reporter import upstream_reporter as ur

    return ur, workspace


# ---------------------------------------------------------------------------
# Golden: environment-independent payload fields (pinned byte-for-byte)
# ---------------------------------------------------------------------------

# models: conftest _DEFAULT_TEST_PAYLOAD order, deduped preserving order.
GOLDEN_MODELS: list[str] = [
    "kimiCoding:K2.6",
    "volcanoArk:doubao-seed-2-0-code-preview-260215",
    "codex_oauth:gpt-5.5",
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

# Node-level skills with controlled HOME: every compat/global root is empty, so
# the node-level payload (workspace_root=repo_root) carries only whatever lives
# under the repo — which under controlled HOME is empty. Pinned to [].
GOLDEN_NODE_SKILLS: list[dict[str, str]] = []

# Agent-level skills with the controlled workspace's two seeded skills only.
GOLDEN_AGENT_SKILLS: list[dict[str, str]] = [
    {"name": "alpha-skill", "description": "Alpha skill for baseline"},
    {"name": "beta-skill", "description": "Beta skill for baseline"},
]

GOLDEN_FLAGS = {"relay": True, "send_message": True, "config_sync": True}
GOLDEN_DEFAULT_SYSTEM_PROMPT = ""


def _sorted_skills(skills: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(skills, key=lambda s: s["name"])


# ---------------------------------------------------------------------------
# Baseline assertions
# ---------------------------------------------------------------------------


def test_node_capabilities_payload_matches_baseline(controlled_caps) -> None:
    """node.capabilities payload reproduces the recorded baseline (design 风险 2)."""
    ur, _workspace = controlled_caps
    payload = ur.build_node_capabilities_payload()

    assert list(payload["models"]) == GOLDEN_MODELS
    assert payload["platform_default_model"] == GOLDEN_PLATFORM_DEFAULT_MODEL
    assert list(payload["tools"]) == GOLDEN_TOOLS
    assert list(payload["features"]) == GOLDEN_NODE_FEATURES
    assert _sorted_skills(list(payload["skills"])) == GOLDEN_NODE_SKILLS
    assert payload["relay"] == GOLDEN_FLAGS["relay"]
    assert payload["send_message"] == GOLDEN_FLAGS["send_message"]
    assert payload["config_sync"] == GOLDEN_FLAGS["config_sync"]
    assert payload["default_system_prompt"] == GOLDEN_DEFAULT_SYSTEM_PROMPT


def test_agent_capabilities_payload_matches_baseline(controlled_caps) -> None:
    """agent.capabilities.resolve payload reproduces the baseline (design 风险 2).

    Exercises per-workspace skill discovery (workspace-seeded skills only, global
    roots empty) AND per-allowlist feature availability — the two R-CFG invariants.
    """
    ur, workspace = controlled_caps
    payload = ur.build_agent_capabilities_payload(
        workspace_root=str(workspace),
        tool_allowlist=GOLDEN_AGENT_FEATURES_ALLOWLIST,
    )

    assert list(payload["models"]) == GOLDEN_MODELS
    assert payload["platform_default_model"] == GOLDEN_PLATFORM_DEFAULT_MODEL
    assert list(payload["tools"]) == GOLDEN_TOOLS
    assert list(payload["features"]) == GOLDEN_AGENT_FEATURES
    assert _sorted_skills(list(payload["skills"])) == GOLDEN_AGENT_SKILLS


def test_node_register_flags_payload_matches_baseline(controlled_caps) -> None:
    """node.register capability flags reproduce the baseline (design 风险 2).

    node.register carries only the boolean flags (no models/skills/tools), per
    ReporterCapabilities.register_flags_payload.
    """
    ur, _workspace = controlled_caps
    caps = ur.build_runtime_capabilities()
    flags = caps.register_flags_payload()
    assert flags == GOLDEN_FLAGS
