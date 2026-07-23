"""SQLite repositories for IM users, conversations, and messages."""

import sqlite3

from IM.domain.models import (
    UsageMetric,
)


from IM.infra._timestamps import utc_now


class UsageMetricsRepository:
    """Persist and aggregate token/turn usage metrics for IM board APIs."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def record_usage(
        self,
        *,
        owner_id: str | None,
        conversation_id: str | None,
        agent_id: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        turns: int = 1,
    ) -> None:
        """Persist one usage sample emitted by IM-visible activity."""
        normalized_prompt = max(prompt_tokens, 0)
        normalized_completion = max(completion_tokens, 0)
        normalized_turns = max(turns, 0)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO usage_metrics(
                    owner_id,
                    conversation_id,
                    agent_id,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    turns,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_id,
                    conversation_id,
                    agent_id,
                    normalized_prompt,
                    normalized_completion,
                    normalized_prompt + normalized_completion,
                    normalized_turns,
                    utc_now(),
                ),
            )

    def list_usage_metrics(
        self,
        *,
        owner_id: str | None = None,
        conversation_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[UsageMetric]:
        """Return aggregated usage grouped by owner, conversation, and agent scopes."""
        filters: list[str] = []
        params: list[object] = []
        if owner_id is not None:
            filters.append("owner_id = ?")
            params.append(owner_id)
        if conversation_id is not None:
            filters.append("conversation_id = ?")
            params.append(conversation_id)
        if agent_id is not None:
            filters.append("agent_id = ?")
            params.append(agent_id)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self._connection.execute(
            f"""
            SELECT owner_id, conversation_id, agent_id,
                   SUM(turns) AS turns,
                   SUM(prompt_tokens) AS prompt_tokens,
                   SUM(completion_tokens) AS completion_tokens,
                   SUM(total_tokens) AS total_tokens,
                   MAX(created_at) AS last_used_at
            FROM usage_metrics
            {where_clause}
            GROUP BY owner_id, conversation_id, agent_id
            ORDER BY last_used_at DESC, rowid DESC
            """,
            tuple(params),
        ).fetchall()
        metrics: list[UsageMetric] = []
        for row in rows:
            scope, scope_id = _resolve_usage_scope(
                owner_id=row["owner_id"],
                conversation_id=row["conversation_id"],
                agent_id=row["agent_id"],
            )
            metrics.append(
                UsageMetric(
                    scope=scope,
                    scope_id=scope_id,
                    owner_id=row["owner_id"],
                    conversation_id=row["conversation_id"],
                    agent_id=row["agent_id"],
                    turns=int(row["turns"] or 0),
                    prompt_tokens=int(row["prompt_tokens"] or 0),
                    completion_tokens=int(row["completion_tokens"] or 0),
                    total_tokens=int(row["total_tokens"] or 0),
                    last_used_at=row["last_used_at"],
                )
            )
        return metrics


def _resolve_usage_scope(
    *, owner_id: str | None, conversation_id: str | None, agent_id: str | None
) -> tuple[str, str | None]:
    """Choose the most specific scope label for one aggregated usage row."""
    if agent_id:
        return "agent", agent_id
    if conversation_id:
        return "conversation", conversation_id
    if owner_id:
        return "owner", owner_id
    return "global", None
