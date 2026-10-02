"""init_admin: seed the first authenticated user on a fresh IM database.

Operator workflow:
    PYTHONPATH=src python -m IM.cli init_admin --username root --password $PASSWORD --display-name Root

This local bootstrap makes the selected account active and a company administrator.
Public registration always remains pending.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from IM.infra.auth_sessions import AuthSessions
from IM.application.auth_service import (
    AuthService,
    RegistrationError,
    resolve_jwt_secret,
)
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.users import UserRepository


def run_init_admin(
    *,
    username: str,
    password: str,
    display_name: str,
    db_path: Path | None,
    locale: str = "en",
) -> int:
    """Create one admin user and return a shell exit code (0 success, 1 duplicate, 2 other)."""
    resolved_db_path = db_path or Path(
        os.getenv("IM_DB_PATH", "data/im_service.sqlite3")
    )
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = connect(resolved_db_path)
    initialize_schema(connection)
    try:
        service = AuthService(
            users=UserRepository(connection),
            sessions=AuthSessions(connection),
            jwt_secret=resolve_jwt_secret(),
        )
        try:
            pair = service.register(
                username=username,
                password=password,
                display_name=display_name,
                locale=locale,
            )
        except RegistrationError as exc:
            detail = str(exc)
            print(f"init_admin failed: {detail}", file=sys.stderr)
            return 1 if "already exists" in detail else 2
        from IM.application.company_service import CompanyService

        CompanyService(resolved_db_path).initialize(
            admin_id=pair.user.id, active_ids=[]
        )
        print(
            f"init_admin: created user {pair.user.id} (owner_id={pair.user.owner_id})"
        )
        return 0
    finally:
        connection.close()
