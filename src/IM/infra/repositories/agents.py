"""SQLite repositories for IM users, conversations, and messages."""

import json
import sqlite3

from IM.domain.models import (
    AgentProfile,
)


from IM.infra._timestamps import utc_now


class AgentProfileVersionConflictError(ValueError):
    """Raise when agent profile optimistic locking detects a stale version."""


class AgentProfileRepository:
    """Persist and query agent configuration profiles."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_profiles(self) -> list[AgentProfile]:
        """List agent profiles in stable creation order."""
        rows = self._connection.execute(
            """
            SELECT agent_id, owner_id, node_id, display_name, description, skills_json,
                   tool_allowlist_json, group_reply_policy, default_model, workspace_root, workspace_is_default, profile_version,
                   is_stale, features_json, custom_prompt, heartbeat_json
            FROM agent_profiles
            ORDER BY created_at, rowid
            """
        ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def list_runtime_selectable_profiles(self) -> list[AgentProfile]:
        """List profiles that are actually selectable in the current IM runtime.

        A profile is selectable when it is bound to a node and its ownership matches
        the current runtime state for that node. Fresh canonical runtimes advertise
        agents before any bind exists, so ownerless node/profile pairs must still be
        visible. Once a node is bound, only same-owner profiles (or freshly advertised
        blank-owner rows waiting to be reassigned) should remain selectable.
        """
        rows = self._connection.execute(
            """
            SELECT ap.agent_id, ap.owner_id, ap.node_id, ap.display_name, ap.description, ap.skills_json,
                   ap.tool_allowlist_json, ap.group_reply_policy, ap.default_model, ap.workspace_root, ap.workspace_is_default, ap.profile_version,
                   ap.is_stale, ap.features_json, ap.custom_prompt, ap.heartbeat_json
            FROM agent_profiles ap
            JOIN nodes n ON n.node_id = ap.node_id
            WHERE ap.node_id IS NOT NULL
              AND ap.node_id != ''
              AND ap.is_stale = 0
              AND (
                    (COALESCE(n.owner_id, '') = '' AND ap.owner_id = '')
                 OR (COALESCE(n.owner_id, '') != '' AND (ap.owner_id = '' OR ap.owner_id = n.owner_id))
              )
            ORDER BY ap.created_at, ap.rowid
            """
        ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def list_runtime_selectable_profiles_for_owner(
        self, *, owner_id: str
    ) -> list[AgentProfile]:
        """Owner-scoped runtime-selectable profile list (cross-tenant safe).

        Filters to either:
        - profiles owned by the caller (``ap.owner_id = owner_id``), OR
        - ownerless profiles advertised by ownerless runtimes (fresh nodes pre-bind),
          so any authenticated user can discover and bind them.

        A profile owned by another tenant is never returned, regardless of node state.
        """
        rows = self._connection.execute(
            """
            SELECT ap.agent_id, ap.owner_id, ap.node_id, ap.display_name, ap.description, ap.skills_json,
                   ap.tool_allowlist_json, ap.group_reply_policy, ap.default_model, ap.workspace_root, ap.workspace_is_default, ap.profile_version,
                   ap.is_stale, ap.features_json, ap.custom_prompt, ap.heartbeat_json
            FROM agent_profiles ap
            JOIN nodes n ON n.node_id = ap.node_id
            WHERE ap.node_id IS NOT NULL
              AND ap.node_id != ''
              AND ap.is_stale = 0
              AND (
                    (ap.owner_id = ? AND COALESCE(n.owner_id, '') IN ('', ?))
                 OR (ap.owner_id = '' AND COALESCE(n.owner_id, '') = '')
              )
            ORDER BY ap.created_at, ap.rowid
            """,
            (owner_id, owner_id),
        ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_profile_for_owner(
        self, *, agent_id: str, owner_id: str
    ) -> AgentProfile | None:
        """Return the profile when owned by ``owner_id`` or ownerless (fresh, pre-bind); else None."""
        profile = self.get_profile(agent_id=agent_id)
        if profile is None:
            return None
        if profile.owner_id == owner_id or profile.owner_id == "":
            return profile
        return None

    def get_updated_at(self, *, agent_id: str) -> str | None:
        """Return the last update timestamp for one agent profile."""
        row = self._connection.execute(
            "SELECT updated_at FROM agent_profiles WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        value = row["updated_at"]
        return str(value) if value is not None else None

    def get_profile(self, *, agent_id: str) -> AgentProfile | None:
        """Return one agent profile, or None when it does not exist."""
        row = self._connection.execute(
            """
            SELECT agent_id, owner_id, node_id, display_name, description, skills_json,
                   tool_allowlist_json, group_reply_policy, default_model, workspace_root, workspace_is_default, profile_version,
                   is_stale, features_json, custom_prompt, heartbeat_json
            FROM agent_profiles
            WHERE agent_id = ?
            """,
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def upsert_profile(
        self,
        *,
        agent_id: str,
        owner_id: str,
        display_name: str,
        description: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        workspace_root: str | None,
        workspace_is_default: bool | None = None,
        node_id: str | None = None,
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
    ) -> "AgentProfile":
        """Create or replace one seed profile without optimistic locking."""
        created_at = utc_now()
        skills_json = _encode_json_list(skills)
        tool_allowlist_json = _encode_json_list(tool_allowlist)
        # feat-379-M2: persist per-agent feature flags and custom prompt.
        # feat-379-M6 (ISSUE-2): when features/custom_prompt are None (omitted by caller),
        # keep whatever is already in the DB so Gateway re-registration on restart does not
        # wipe user edits.  The ON CONFLICT clause uses COALESCE to fall back to the
        # existing row value when the incoming JSON is the empty-object sentinel '{}' / NULL.
        features_json = (
            json.dumps(features, ensure_ascii=False) if features is not None else None
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO agent_profiles(
                    agent_id, owner_id, node_id, display_name, description,
                    skills_json, tool_allowlist_json, group_reply_policy,
                    default_model, workspace_root, workspace_is_default, profile_version, created_at, updated_at,
                    features_json, custom_prompt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, '{}'), ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    node_id = excluded.node_id,
                    display_name = excluded.display_name,
                    description = excluded.description,
                    skills_json = excluded.skills_json,
                    tool_allowlist_json = excluded.tool_allowlist_json,
                    group_reply_policy = excluded.group_reply_policy,
                    default_model = excluded.default_model,
                    workspace_root = excluded.workspace_root,
                    workspace_is_default = CASE
                        WHEN agent_profiles.workspace_is_default IS NULL
                        THEN excluded.workspace_is_default
                        ELSE agent_profiles.workspace_is_default
                    END,
                    updated_at = excluded.updated_at,
                    is_stale = 0,
                    staled_at = NULL,
                    features_json = CASE
                        WHEN excluded.features_json IS NOT NULL AND excluded.features_json != '{}'
                        THEN excluded.features_json
                        ELSE agent_profiles.features_json
                    END,
                    custom_prompt = CASE
                        WHEN excluded.custom_prompt IS NOT NULL
                        THEN excluded.custom_prompt
                        ELSE agent_profiles.custom_prompt
                    END
                """,
                (
                    agent_id,
                    owner_id,
                    node_id,
                    display_name,
                    description,
                    skills_json,
                    tool_allowlist_json,
                    group_reply_policy,
                    default_model,
                    workspace_root,
                    None if workspace_is_default is None else int(workspace_is_default),
                    1,
                    created_at,
                    created_at,
                    features_json,
                    custom_prompt,
                ),
            )
        profile = self.get_profile(agent_id=agent_id)
        assert profile is not None
        return profile

    def mark_stale_for_node(
        self,
        *,
        node_id: str,
        advertised_agent_ids: list[str],
    ) -> int:
        """Mark as stale any agent profile for this node not in the current advertise list.

        Returns the count of rows newly marked stale. Safe to call repeatedly; rows
        already stale are excluded from the count (is_stale=0 guard).
        Empty advertised_agent_ids marks all profiles for this node as stale.
        """
        now = utc_now()
        if advertised_agent_ids:
            placeholders = ",".join("?" * len(advertised_agent_ids))
            params: list[object] = [now, node_id] + list(advertised_agent_ids)
            cursor = self._connection.execute(
                f"""
                UPDATE agent_profiles
                SET is_stale = 1, staled_at = ?
                WHERE node_id = ?
                  AND is_stale = 0
                  AND agent_id NOT IN ({placeholders})
                """,
                params,
            )
        else:
            cursor = self._connection.execute(
                """
                UPDATE agent_profiles
                SET is_stale = 1, staled_at = ?
                WHERE node_id = ?
                  AND is_stale = 0
                """,
                (now, node_id),
            )
        return cursor.rowcount

    def update_profile(
        self,
        *,
        agent_id: str,
        profile_version: int,
        display_name: str,
        description: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
        heartbeat_json: str | None = None,
    ) -> "AgentProfile":
        """Update a profile with optimistic locking on profile_version.

        workspace_root is intentionally excluded from this method — it is set
        once at agent creation and is immutable afterwards (bugfix-404-M2
        decision 5).  Any call-site passing workspace_root via the service
        layer would silently reset it to the managed default; removing the
        parameter makes that a compile-time error instead.
        """
        current = self.get_profile(agent_id=agent_id)
        if current is None:
            raise ValueError("agent_id not found")
        if current.profile_version != profile_version:
            raise AgentProfileVersionConflictError("profile_version conflict")
        updated_at = utc_now()
        next_version = current.profile_version + 1
        # feat-379-M2: persist per-agent feature flags and custom prompt
        features_json = json.dumps(
            features if features is not None else dict(current.features),
            ensure_ascii=False,
        )
        resolved_custom_prompt = (
            custom_prompt if custom_prompt is not None else current.custom_prompt
        )
        # feat-394: heartbeat_json carries cadence (every/active_hours); None preserves existing.
        # feat-394 M9-E: cron_json removed — cron enable lives in features_json["cron_scheduling"].
        resolved_heartbeat_json = (
            heartbeat_json if heartbeat_json is not None else current.heartbeat_json
        )
        with self._connection:
            self._connection.execute(
                """
                UPDATE agent_profiles
                SET display_name = ?,
                    description = ?,
                    skills_json = ?,
                    tool_allowlist_json = ?,
                    group_reply_policy = ?,
                    default_model = ?,
                    profile_version = ?,
                    updated_at = ?,
                    features_json = ?,
                    custom_prompt = ?,
                    heartbeat_json = ?
                WHERE agent_id = ?
                """,
                (
                    display_name,
                    description,
                    _encode_json_list(skills),
                    _encode_json_list(tool_allowlist),
                    group_reply_policy,
                    default_model,
                    next_version,
                    updated_at,
                    features_json,
                    resolved_custom_prompt,
                    resolved_heartbeat_json,
                    agent_id,
                ),
            )
        updated = self.get_profile(agent_id=agent_id)
        assert updated is not None
        return updated

    def reassign_owner_by_node(self, *, node_id: str, owner_id: str) -> None:
        """Assign all node-local agents to the bound user owner."""
        with self._connection:
            self._connection.execute(
                "UPDATE agent_profiles SET owner_id = ? WHERE node_id = ?",
                (owner_id, node_id),
            )

    def _row_to_profile(self, row: sqlite3.Row) -> "AgentProfile":
        """Convert one storage row to a domain agent profile."""
        keys = row.keys()
        is_stale = bool(row["is_stale"]) if "is_stale" in keys else False
        # feat-379-M2: decode per-agent feature flags (stored as JSON object)
        raw_features = row["features_json"] if "features_json" in keys else None
        if raw_features:
            try:
                decoded_features = json.loads(raw_features)
                features = (
                    {
                        k: bool(v)
                        for k, v in decoded_features.items()
                        if isinstance(k, str)
                    }
                    if isinstance(decoded_features, dict)
                    else {}
                )
            except (ValueError, TypeError):
                features = {}
        else:
            features = {}
        custom_prompt_raw = row["custom_prompt"] if "custom_prompt" in keys else None
        custom_prompt = (
            custom_prompt_raw
            if isinstance(custom_prompt_raw, str) and custom_prompt_raw.strip()
            else None
        )
        # feat-394: heartbeat cadence JSON string (raw, not decoded; forwarded to gateway as-is)
        # feat-394 M9-E: cron_json removed — cron enable lives in features["cron_scheduling"].
        heartbeat_json_raw = row["heartbeat_json"] if "heartbeat_json" in keys else None
        heartbeat_json = (
            heartbeat_json_raw
            if isinstance(heartbeat_json_raw, str) and heartbeat_json_raw.strip()
            else None
        )
        return AgentProfile(
            agent_id=row["agent_id"],
            owner_id=row["owner_id"],
            node_id=row["node_id"],
            display_name=row["display_name"],
            description=row["description"],
            skills=_decode_string_list(row["skills_json"]),
            tool_allowlist=_decode_string_list(row["tool_allowlist_json"]),
            group_reply_policy=row["group_reply_policy"],
            default_model=row["default_model"],
            workspace_root=row["workspace_root"],
            workspace_is_default=(
                bool(row["workspace_is_default"])
                if "workspace_is_default" in keys
                and row["workspace_is_default"] is not None
                else None
            ),
            profile_version=int(row["profile_version"]),
            is_stale=is_stale,
            features=features,
            custom_prompt=custom_prompt,
            heartbeat_json=heartbeat_json,
        )


def _encode_json_list(values: list[str]) -> str:
    """Encode string lists with a stable JSON representation."""
    return json.dumps(
        [str(item) for item in values], ensure_ascii=True, separators=(",", ":")
    )


def _decode_string_list(raw_value: str) -> list[str]:
    """Decode a JSON list into a list of strings."""
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded]
