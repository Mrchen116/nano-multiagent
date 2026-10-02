"""``python -m IM.cli`` entrypoint dispatch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="IM.cli", description="IM service operator CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_admin = sub.add_parser(
        "init_admin", help="Seed the first admin user on a fresh database"
    )
    init_admin.add_argument("--username", required=True)
    init_admin.add_argument("--password", required=True)
    init_admin.add_argument("--display-name", required=True)
    init_admin.add_argument(
        "--db-path",
        default=None,
        help="Path to the IM sqlite file; defaults to $IM_DB_PATH or data/im_service.sqlite3",
    )
    init_admin.add_argument("--locale", default="en")

    company = sub.add_parser(
        "initialize_company",
        help="Locally select existing active members and the first administrator",
    )
    company.add_argument("--db-path", required=True)
    company.add_argument("--admin-id", required=True)
    company.add_argument("--active-id", action="append", default=[])

    args = parser.parse_args(argv)
    if args.command == "initialize_company":
        from IM.application.company_service import CompanyService
        from IM.infra.db import connect, initialize_schema

        path = Path(args.db_path)
        connection = connect(path)
        initialize_schema(connection)
        connection.close()
        try:
            CompanyService(path).initialize(
                admin_id=args.admin_id, active_ids=args.active_id
            )
        except ValueError as exc:
            print(f"initialize_company failed: {exc}", file=sys.stderr)
            return 2
        print("Company initialization complete")
        return 0

    if args.command == "init_admin":
        from IM.cli.init_admin import run_init_admin

        return run_init_admin(
            username=args.username,
            password=args.password,
            display_name=args.display_name,
            db_path=Path(args.db_path) if args.db_path else None,
            locale=args.locale,
        )

    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover - argparse already exits


if __name__ == "__main__":
    sys.exit(main())
