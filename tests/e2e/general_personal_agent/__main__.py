"""CLI: collect, dry-run, run, adjudicate and compare real PA experiments."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .catalog import ASSETS, catalog, digest, select, write_json


def main():
    """Execute the selected evaluation operation without implicit live actions."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("collect", "dry-run"):
        item = sub.add_parser(name)
        item.add_argument("--cases", default="all")
        item.add_argument("--output", type=Path)
    item = sub.add_parser("run")
    item.add_argument("--case", required=True, choices=catalog())
    item.add_argument("--manifest", required=True, type=Path)
    item.add_argument("--output", required=True, type=Path)
    item.add_argument("--label", choices=["baseline", "candidate"], required=True)
    item.add_argument("--username", default="nano")
    item.add_argument("--password-env", default="PA_EVAL_PASSWORD")
    item.add_argument("--timeout", type=float, default=240)
    item.add_argument("--checkpoints", type=Path)
    item = sub.add_parser("adjudicate")
    item.add_argument("--output", required=True, type=Path)
    item.add_argument("--review", required=True, type=Path)
    item = sub.add_parser("compare")
    item.add_argument("runs", type=Path, nargs="+")
    item.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command in {"collect", "dry-run"}:
        cases = catalog()
        rows = [
            {
                **cases[case_id],
                "status": "not_run",
                "diagnostic": "dry_run_no_live_actions",
            }
            for case_id in select(args.cases)
        ]
        result = {
            "format": "nano-pa-plan-v1",
            "cases": rows,
            "source_sha256": digest(ASSETS / "scenarios.yaml"),
            "adapter_sha256": digest(ASSETS / "adapters.json"),
        }
        if args.output:
            write_json(args.output, result)
        print(
            json.dumps(
                {
                    "count": len(rows),
                    "case_ids": [row["id"] for row in rows],
                    "live_actions": 0,
                },
                ensure_ascii=False,
            )
        )
        return
    if args.command == "run":
        from .runner import Run

        password = os.environ.get(args.password_env)
        if not password:
            parser.error(
                f"provide test password in {args.password_env}; never pass production credentials"
            )
        label_file = args.output / "run-label.json"
        if (
            label_file.exists()
            and json.loads(label_file.read_text())["label"] != args.label
        ):
            parser.error("cannot relabel an existing run")
        run = Run(
            catalog()[args.case],
            args.manifest,
            args.output,
            args.username,
            password,
            args.timeout,
            args.checkpoints,
        )
        write_json(args.output / "run-label.json", {"label": args.label})
        result = run.execute()
    elif args.command == "adjudicate":
        from .review import adjudicate

        result = adjudicate(args.output, args.review)
    else:
        from .review import comparison

        result = comparison(args.runs)
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
