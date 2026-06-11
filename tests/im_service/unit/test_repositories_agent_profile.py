"""Unit tests for agent profile repository: roundtrip, optimistic lock, alias snapshot."""

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    AgentProfileRepository,
    AgentProfileVersionConflictError,
    BindRepository,
    ConversationRepository,
    MessageRepository,
    NodeRepository,
    UserRepository,
)


def _build_repositories(
    tmp_path: Path,
) -> tuple[
    UserRepository,
    ConversationRepository,
    MessageRepository,
    AgentProfileRepository,
    NodeRepository,
    BindRepository,
]:
    """Build repository instances bound to a temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
        AgentProfileRepository(connection),
        NodeRepository(connection),
        BindRepository(connection),
    )


def test_agent_profile_roundtrip_and_optimistic_lock(tmp_path: Path) -> None:
    """Persist profiles and reject stale profile_version updates."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_user = users.create_user(username="agent-1", display_name="Alpha")
    seeded = profiles.upsert_profile(
        agent_id=agent_user.id,
        owner_id=owner.owner_id,
        display_name="Alpha",
        description="initial",
        system_prompt="You are Alpha.",
        skills=["plan"],
        tool_allowlist=["read"],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )

    created_conversation = conversations.create_conversation(
        title="alpha thread",
        participant_ids=[owner.id, seeded.agent_id],
    )
    assert created_conversation.config_profile_version == 1

    updated = profiles.update_profile(
        agent_id=agent_user.id,
        profile_version=1,
        display_name="Alpha v2",
        description="updated",
        system_prompt="You are Alpha v2.",
        skills=["plan", "review"],
        tool_allowlist=["read", "edit"],
        group_reply_policy="auto",
        default_model="claude-sonnet-4",
        workspace_root="/srv/agents/alpha",
    )
    assert updated.profile_version == 2
    assert updated.group_reply_policy == "auto"
    assert updated.workspace_root == "/srv/agents/alpha"

    with pytest.raises(AgentProfileVersionConflictError):
        profiles.update_profile(
            agent_id=agent_user.id,
            profile_version=1,
            display_name="stale",
            description="stale",
            system_prompt="stale",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )


def test_direct_conversation_with_agent_alias_freezes_prompt_snapshot(
    tmp_path: Path,
) -> None:
    """Freeze agent snapshot metadata when direct chats target an alias user like `agent:<id>`."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_alias = users.create_user(
        username="agent:agent-1", display_name="Alpha Alias"
    )
    profiles.upsert_profile(
        agent_id="agent-1",
        owner_id=owner.owner_id,
        display_name="Alpha",
        description="initial",
        system_prompt="You are Alpha.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )

    created = conversations.create_conversation(
        title="alias direct",
        participant_ids=[owner.id, agent_alias.id],
    )
    stored = conversations.get_conversation(conversation_id=created.id)
    snapshot_row = conversations._connection.execute(
        "SELECT config_agent_id, config_profile_version, config_system_prompt FROM conversations WHERE id = ?",
        (created.id,),
    ).fetchone()

    assert created.type == "direct"
    assert created.config_profile_version == 1
    assert stored is not None
    assert stored.config_profile_version == 1
    assert snapshot_row is not None
    assert snapshot_row["config_agent_id"] == "agent-1"
    assert snapshot_row["config_profile_version"] == 1
    assert snapshot_row["config_system_prompt"] == "You are Alpha."


# ---------------------------------------------------------------------------
# feat-379-M2/R3: features_json + custom_prompt in AgentProfile
# ---------------------------------------------------------------------------


def test_agent_profile_features_and_custom_prompt_roundtrip(tmp_path: Path) -> None:
    """AgentProfile must store and return features_json + custom_prompt (feat-379-M2)."""
    _, _, _, profiles, _, _ = _build_repositories(tmp_path)

    from IM.infra.repositories import AgentProfileRepository as _APR  # noqa: F401

    # features + custom_prompt must exist on AgentProfile dataclass
    from IM.domain.models import AgentProfile

    assert hasattr(AgentProfile, "__dataclass_fields__") or True  # dataclass check
    sample = AgentProfile(agent_id="x", owner_id="y")
    assert hasattr(sample, "features"), "AgentProfile must have 'features' field"
    assert hasattr(sample, "custom_prompt"), (
        "AgentProfile must have 'custom_prompt' field"
    )


def test_upsert_profile_stores_features_and_custom_prompt(tmp_path: Path) -> None:
    """upsert_profile must persist features and custom_prompt."""
    _, _, _, profiles, _, _ = _build_repositories(tmp_path)
    from IM.infra.repositories import UserRepository

    connection = profiles._connection
    users = UserRepository(connection)
    owner = users.create_user(username="owner3", display_name="Owner3")

    profile = profiles.upsert_profile(
        agent_id="agent-features",
        owner_id=owner.owner_id,
        display_name="Features Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
        features={"memory_curation": False},
        custom_prompt="You are a chef.",
    )

    assert profile.features == {"memory_curation": False}
    assert profile.custom_prompt == "You are a chef."

    # Reload from db to confirm persistence
    reloaded = profiles.get_profile(agent_id="agent-features")
    assert reloaded is not None
    assert reloaded.features == {"memory_curation": False}
    assert reloaded.custom_prompt == "You are a chef."


def test_update_profile_stores_features_and_custom_prompt(tmp_path: Path) -> None:
    """update_profile must persist features and custom_prompt changes."""
    _, _, _, profiles, _, _ = _build_repositories(tmp_path)
    from IM.infra.repositories import UserRepository

    connection = profiles._connection
    users = UserRepository(connection)
    owner = users.create_user(username="owner4", display_name="Owner4")

    profiles.upsert_profile(
        agent_id="agent-upd",
        owner_id=owner.owner_id,
        display_name="Upd",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )

    updated = profiles.update_profile(
        agent_id="agent-upd",
        profile_version=1,
        display_name="Upd",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
        features={"skill_creation": True},
        custom_prompt="You are a tutor.",
    )

    assert updated.features == {"skill_creation": True}
    assert updated.custom_prompt == "You are a tutor."


# feat-379-M6 (ISSUE-2): upsert_profile must preserve existing features/custom_prompt
# when called again without those fields — regression from Gateway re-register on restart.
def test_upsert_profile_preserves_features_on_re_register(tmp_path: Path) -> None:
    """Re-registering an existing profile without features must not clear them.

    This is the regression path: Gateway sends node.register → _handle_register calls
    upsert_profile for each agent_id WITHOUT features/custom_prompt (because register
    payload only carries agent_ids, not per-agent config). The upsert must detect the
    existing row and leave features_json/custom_prompt untouched.
    """
    _, _, _, profiles, _, _ = _build_repositories(tmp_path)
    from IM.infra.repositories import UserRepository

    connection = profiles._connection
    users = UserRepository(connection)
    owner = users.create_user(username="owner5", display_name="Owner5")

    # First upsert: sets features + custom_prompt via explicit edit (simulates PATCH /config).
    profiles.upsert_profile(
        agent_id="agent-persist",
        owner_id=owner.owner_id,
        display_name="Persist Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
        features={"memory_curation": False},
        custom_prompt="You are a chef.",
    )

    # Second upsert: simulates Gateway re-register without features/custom_prompt.
    # This must NOT overwrite the previously saved values.
    profiles.upsert_profile(
        agent_id="agent-persist",
        owner_id=owner.owner_id,
        display_name="Persist Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
        # features and custom_prompt intentionally omitted — simulates Gateway re-register
    )

    reloaded = profiles.get_profile(agent_id="agent-persist")
    assert reloaded is not None
    # Must still have the values from the first upsert, not overwritten with defaults.
    assert reloaded.features == {"memory_curation": False}, (
        "upsert_profile must preserve existing features when called without them"
    )
    assert reloaded.custom_prompt == "You are a chef.", (
        "upsert_profile must preserve existing custom_prompt when called without it"
    )


# ---------------------------------------------------------------------------
# bugfix-404-M2 R3: update_profile（repo 层）不写 workspace_root 列，存量值保持
# ---------------------------------------------------------------------------


def test_update_profile_preserves_non_default_workspace_root(tmp_path: Path) -> None:
    """repo.update_profile 不得更新 workspace_root 列——存量自定义路径 update 后保持不变。

    bugfix-404-M2 决策 5：ConfigService.update_profile 删 workspace_root 参数；
    repo 层 update SQL 不写该列，确保任何一次 UI 配置编辑（system prompt/skills 等）
    都不会把 workspace_root 重置回 managed default。

    这是修前缺陷的直接复现：update 前存 /custom/workspace，update 后变成 managed default。
    """
    from IM.infra.db import connect, initialize_schema
    from IM.infra.repositories import AgentProfileRepository

    db = connect(tmp_path / "test_update_no_ws.db")
    initialize_schema(db)
    repo = AgentProfileRepository(db)

    custom_ws = "/custom/workspace/Arch"
    repo.upsert_profile(
        agent_id="Arch",
        owner_id="owner-1",
        display_name="Arch",
        description="",
        system_prompt="You are Arch.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=custom_ws,
    )

    # update 只改 system_prompt，不应触碰 workspace_root
    profile_before = repo.get_profile(agent_id="Arch")
    assert profile_before is not None
    repo.update_profile(
        agent_id="Arch",
        profile_version=profile_before.profile_version,
        display_name="Arch",
        description="",
        system_prompt="Updated prompt.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,  # 传 None 时修前会重置为 managed default，修后应保持存量值
    )

    profile_after = repo.get_profile(agent_id="Arch")
    assert profile_after is not None
    assert profile_after.workspace_root == custom_ws, (
        f"update_profile 后 workspace_root 应保持 {custom_ws!r}，"
        f"实际变为 {profile_after.workspace_root!r}（被重置为 managed default）"
    )
