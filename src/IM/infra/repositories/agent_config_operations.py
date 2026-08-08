"""Durable IM-side records for recoverable Gateway Agent configuration operations."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3

from IM.infra._timestamps import utc_now


class AgentConfigOperationPendingError(ValueError):
    """Raised when an agent already has an uncommitted configuration operation."""


@dataclass(frozen=True, slots=True)
class AgentConfigOperation:
    """One durable create/apply/compensation operation coordinated with a Gateway."""

    operation_id: str
    root_operation_id: str | None
    agent_id: str
    owner_id: str
    node_id: str
    operation_kind: str
    status: str
    candidate: dict[str, object]
    previous_candidate: dict[str, object] | None
    candidate_fingerprint: str
    expected_previous_fingerprint: str | None
    expected_profile_version: int | None
    gateway_result: dict[str, object] | None
    error_code: str | None
    error_message: str | None


class AgentConfigOperationRepository:
    """Persist the IM half of the recoverable Gateway configuration protocol."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        *,
        operation_id: str,
        agent_id: str,
        owner_id: str,
        node_id: str,
        operation_kind: str,
        candidate: dict[str, object],
        previous_candidate: dict[str, object] | None,
        candidate_fingerprint: str,
        expected_previous_fingerprint: str | None,
        expected_profile_version: int | None,
        root_operation_id: str | None = None,
    ) -> AgentConfigOperation:
        """Create a pending record, rejecting a second active operation per agent."""
        now = utc_now()
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO agent_config_operations(
                        operation_id, root_operation_id, agent_id, owner_id, node_id,
                        operation_kind, status, candidate_json, candidate_fingerprint,
                        previous_candidate_json,
                        expected_previous_fingerprint, expected_profile_version,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation_id,
                        root_operation_id,
                        agent_id,
                        owner_id,
                        node_id,
                        operation_kind,
                        _encode_object(candidate),
                        candidate_fingerprint,
                        _encode_object(previous_candidate)
                        if previous_candidate is not None
                        else None,
                        expected_previous_fingerprint,
                        expected_profile_version,
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            active = self._get_active(agent_id=agent_id)
            if active is not None:
                raise AgentConfigOperationPendingError("config_apply_pending") from exc
            raise
        operation = self.get(operation_id=operation_id)
        assert operation is not None
        return operation

    def get(self, *, operation_id: str) -> AgentConfigOperation | None:
        """Return an operation by stable id."""
        row = self._connection.execute(
            """
            SELECT operation_id, root_operation_id, agent_id, owner_id, node_id,
                   operation_kind, status, candidate_json, candidate_fingerprint,
                   previous_candidate_json,
                   expected_previous_fingerprint, expected_profile_version,
                   gateway_result_json, error_code, error_message
            FROM agent_config_operations
            WHERE operation_id = ?
            """,
            (operation_id,),
        ).fetchone()
        return self._row_to_operation(row) if row is not None else None

    def get_active(
        self, *, agent_id: str, owner_id: str
    ) -> AgentConfigOperation | None:
        """Return the current pending or Gateway-applied operation for one agent."""
        return self._get_active(agent_id=agent_id, owner_id=owner_id)

    def _get_active(
        self, *, agent_id: str, owner_id: str | None = None
    ) -> AgentConfigOperation | None:
        """Return an active operation, optionally constrained to its owner.

        The active-operation index is global to ``agent_id``. The create path
        uses the unconstrained form only to translate that collision into the
        owner-safe pending response; it never exposes another owner's record.
        """
        owner_clause = "AND owner_id = ?" if owner_id is not None else ""
        parameters: tuple[str, ...] = (
            (agent_id, owner_id) if owner_id is not None else (agent_id,)
        )
        row = self._connection.execute(
            f"""
            SELECT operation_id, root_operation_id, agent_id, owner_id, node_id,
                   operation_kind, status, candidate_json, candidate_fingerprint,
                   previous_candidate_json,
                   expected_previous_fingerprint, expected_profile_version,
                   gateway_result_json, error_code, error_message
            FROM agent_config_operations
            WHERE agent_id = ? {owner_clause}
              AND status IN ('pending', 'gateway_applied')
            ORDER BY rowid DESC
            LIMIT 1
            """,
            parameters,
        ).fetchone()
        return self._row_to_operation(row) if row is not None else None

    def mark_gateway_applied(
        self, *, operation_id: str, result: dict[str, object]
    ) -> AgentConfigOperation:
        """Persist the canonical terminal applied result before IM profile commit."""
        self._update(
            operation_id=operation_id,
            status="gateway_applied",
            gateway_result=result,
            error_code=None,
            error_message=None,
        )
        operation = self.get(operation_id=operation_id)
        assert operation is not None
        return operation

    def mark_rejected(
        self,
        *,
        operation_id: str,
        error_code: str,
        error_message: str | None,
        result: dict[str, object] | None = None,
    ) -> None:
        """Persist a terminal rejected outcome."""
        self._update(
            operation_id=operation_id,
            status="rejected",
            gateway_result=result,
            error_code=error_code,
            error_message=error_message,
        )

    def mark_committed(self, *, operation_id: str) -> None:
        """Mark an applied operation fully committed in IM."""
        self._update(
            operation_id=operation_id,
            status="committed",
            gateway_result=None,
            error_code=None,
            error_message=None,
            preserve_result=True,
        )

    def replace_with_compensation(
        self,
        *,
        source_operation_id: str,
        compensation_operation_id: str,
        candidate: dict[str, object],
        candidate_fingerprint: str,
        expected_previous_fingerprint: str,
    ) -> AgentConfigOperation:
        """Atomically retire a CAS-lost apply and enqueue its old-profile compensation."""
        source = self.get(operation_id=source_operation_id)
        if source is None:
            raise ValueError("source operation not found")
        now = utc_now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE agent_config_operations
                SET status = 'compensating', error_code = 'profile_version_conflict',
                    updated_at = ?
                WHERE operation_id = ?
                """,
                (now, source_operation_id),
            )
            self._connection.execute(
                """
                INSERT INTO agent_config_operations(
                    operation_id, root_operation_id, agent_id, owner_id, node_id,
                    operation_kind, status, candidate_json, candidate_fingerprint,
                    previous_candidate_json,
                    expected_previous_fingerprint, expected_profile_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'compensation', 'pending', ?, ?, NULL, ?, NULL, ?, ?)
                """,
                (
                    compensation_operation_id,
                    source_operation_id,
                    source.agent_id,
                    source.owner_id,
                    source.node_id,
                    _encode_object(candidate),
                    candidate_fingerprint,
                    expected_previous_fingerprint,
                    now,
                    now,
                ),
            )
        compensation = self.get(operation_id=compensation_operation_id)
        assert compensation is not None
        return compensation

    def finish_compensation(self, *, operation_id: str) -> None:
        """Commit compensation and close its source operation as rejected."""
        operation = self.get(operation_id=operation_id)
        if operation is None or operation.operation_kind != "compensation":
            raise ValueError("compensation operation not found")
        now = utc_now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE agent_config_operations
                SET status = 'committed', updated_at = ?
                WHERE operation_id = ?
                """,
                (now, operation_id),
            )
            if operation.root_operation_id is not None:
                self._connection.execute(
                    """
                    UPDATE agent_config_operations
                    SET status = 'rejected', error_code = 'profile_version_conflict',
                        updated_at = ?
                    WHERE operation_id = ?
                    """,
                    (now, operation.root_operation_id),
                )

    def _update(
        self,
        *,
        operation_id: str,
        status: str,
        gateway_result: dict[str, object] | None,
        error_code: str | None,
        error_message: str | None,
        preserve_result: bool = False,
    ) -> None:
        result_json = (
            None
            if preserve_result
            else _encode_object(gateway_result)
            if gateway_result is not None
            else None
        )
        result_assignment = (
            "gateway_result_json = gateway_result_json"
            if preserve_result
            else "gateway_result_json = ?"
        )
        params: list[object] = [status]
        if not preserve_result:
            params.append(result_json)
        params.extend([error_code, error_message, utc_now(), operation_id])
        with self._connection:
            self._connection.execute(
                f"""
                UPDATE agent_config_operations
                SET status = ?, {result_assignment}, error_code = ?, error_message = ?,
                    updated_at = ?
                WHERE operation_id = ?
                """,  # noqa: S608 - assignment is selected from local constants above.
                params,
            )

    @staticmethod
    def _row_to_operation(row: sqlite3.Row) -> AgentConfigOperation:
        return AgentConfigOperation(
            operation_id=str(row["operation_id"]),
            root_operation_id=row["root_operation_id"],
            agent_id=str(row["agent_id"]),
            owner_id=str(row["owner_id"]),
            node_id=str(row["node_id"]),
            operation_kind=str(row["operation_kind"]),
            status=str(row["status"]),
            candidate=_decode_object(row["candidate_json"]) or {},
            previous_candidate=_decode_object(row["previous_candidate_json"]),
            candidate_fingerprint=str(row["candidate_fingerprint"]),
            expected_previous_fingerprint=row["expected_previous_fingerprint"],
            expected_profile_version=(
                int(row["expected_profile_version"])
                if row["expected_profile_version"] is not None
                else None
            ),
            gateway_result=_decode_object(row["gateway_result_json"]),
            error_code=row["error_code"],
            error_message=row["error_message"],
        )


def _encode_object(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _decode_object(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None
