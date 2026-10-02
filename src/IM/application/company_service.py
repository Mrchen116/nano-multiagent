"""Company admission, explicit local bootstrap and durable revocation."""

import json
from pathlib import Path

from IM.infra.db import connect
from IM.infra.repositories.users import UserRepository


class CompanyError(ValueError):
    """A membership transition cannot be applied to this human account."""


class CompanyService:
    """Own atomic membership changes; transport owners close sockets after commit."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def list_members(self, *, cursor: str = "") -> dict:
        """Return a bounded page of humans and the machines affected by suspension."""
        connection = connect(self.db_path)
        try:
            rows = connection.execute(
                """SELECT u.id,u.username,u.display_name,u.membership_status,u.is_company_admin,
                   (SELECT count(*) FROM nodes n WHERE n.owner_id=u.id) AS node_count,
                   (SELECT count(*) FROM agent_profiles a WHERE a.owner_id=u.id AND a.is_stale=0) AS agent_count
                   FROM users u WHERE u.password_hash IS NOT NULL AND u.password_hash!='' AND u.id>?
                   ORDER BY u.id LIMIT 51""",
                (cursor,),
            ).fetchall()
            return {
                "members": [
                    {**dict(row), "is_company_admin": bool(row["is_company_admin"])}
                    for row in rows[:50]
                ],
                "next_cursor": rows[49]["id"] if len(rows) > 50 else None,
            }
        finally:
            connection.close()

    def transition(self, *, actor_id: str, user_id: str, action: str):
        """Approve pending humans or suspend active members without deleting history."""
        connection = connect(self.db_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            users = UserRepository(connection)
            actor = users.get_user(user_id=actor_id)
            target = users.get_user(user_id=user_id)
            if (
                actor is None
                or actor.membership_status != "active"
                or not actor.is_company_admin
            ):
                raise PermissionError("company administrator required")
            if target is None or not target.password_hash:
                raise LookupError("member not found")
            if action == "approve":
                if target.membership_status == "suspended":
                    raise CompanyError("suspended member cannot be approved")
                next_status = "active"
                connection.execute(
                    "UPDATE users SET membership_status='active' WHERE id=?", (user_id,)
                )
            elif action == "suspend":
                if target.membership_status == "pending":
                    raise CompanyError("only active members can be suspended")
                if target.membership_status == "active" and target.is_company_admin:
                    count = connection.execute(
                        "SELECT count(*) FROM users WHERE membership_status='active' AND is_company_admin=1"
                    ).fetchone()[0]
                    if count <= 1:
                        raise CompanyError(
                            "cannot suspend the last active administrator"
                        )
                next_status = "suspended"
                if target.membership_status != next_status:
                    connection.execute(
                        "UPDATE users SET membership_status='suspended',auth_epoch=auth_epoch+1 WHERE id=?",
                        (user_id,),
                    )
                connection.execute(
                    "UPDATE auth_sessions SET revoked=1 WHERE user_id=?", (user_id,)
                )
                if target.membership_status != next_status:
                    connection.execute(
                        "UPDATE node_binding_state SET node_epoch=node_epoch+1,runtime_token_hash=NULL WHERE owner_id=?",
                        (user_id,),
                    )
                connection.execute(
                    "DELETE FROM auth_ws_tickets WHERE session_id IN (SELECT session_id FROM auth_sessions WHERE user_id=?)",
                    (user_id,),
                )
            else:
                raise CompanyError("unknown membership action")
            if target.membership_status != next_status:
                connection.execute(
                    "INSERT INTO company_member_events(actor_id,user_id,action) VALUES(?,?,?)",
                    (actor_id, user_id, action),
                )
            connection.commit()
            return users.get_user(user_id=user_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, *, admin_id: str, active_ids: list[str]) -> None:
        """Select existing humans once, locally; retries must use the exact same list."""
        connection = connect(self.db_path)
        members = sorted(set([admin_id, *active_ids]))
        encoded = json.dumps(members, separators=(",", ":"))
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT admin_id,active_ids FROM company_initialization WHERE singleton=1"
            ).fetchone()
            if existing:
                if (
                    existing["admin_id"] != admin_id
                    or existing["active_ids"] != encoded
                ):
                    raise CompanyError(
                        "company already initialized with a different member list"
                    )
                return
            for user_id in members:
                row = connection.execute(
                    "SELECT password_hash FROM users WHERE id=?", (user_id,)
                ).fetchone()
                if row is None or not row["password_hash"]:
                    raise CompanyError(
                        "initial members must be existing human accounts"
                    )
            for user_id in members:
                connection.execute(
                    "UPDATE users SET membership_status='active',is_company_admin=? WHERE id=?",
                    (int(user_id == admin_id), user_id),
                )
                connection.execute(
                    "INSERT INTO company_member_events(actor_id,user_id,action) VALUES('local_operator',?,'initialize')",
                    (user_id,),
                )
            connection.execute(
                "INSERT INTO company_initialization VALUES(1,?,?)", (admin_id, encoded)
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
