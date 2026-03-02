import argparse
import json
import os
import sys
from typing import Callable, Sequence, TextIO

from nano_multiagent.sdk.client import ServerClient, ServerClientConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nano-multiagent-cli")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--request-id", default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health")

    create_parser = subparsers.add_parser("create-session")
    create_parser.add_argument("--title", default=None)

    send_parser = subparsers.add_parser("send-message")
    send_parser.add_argument("--session-id", default=None)
    send_parser.add_argument("--text", required=True)

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    client_factory: Callable[[ServerClientConfig], ServerClient] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    out = stdout or sys.stdout

    env_config = ServerClientConfig.from_env()
    config = ServerClientConfig(
        base_url=args.base_url or env_config.base_url,
        token=args.token if args.token is not None else env_config.token,
        request_id=args.request_id if args.request_id is not None else env_config.request_id,
        timeout_seconds=env_config.timeout_seconds,
    )

    factory = client_factory or (lambda cfg: ServerClient(config=cfg))

    try:
        with factory(config) as client:
            if args.command == "health":
                payload = client.health()
            elif args.command == "create-session":
                payload = client.create_session(title=args.title)
            else:
                session_id = args.session_id or os.getenv("NANO_MULTIAGENT_SESSION_ID")
                if not isinstance(session_id, str) or not session_id.strip():
                    raise ValueError("session id is required: use --session-id or NANO_MULTIAGENT_SESSION_ID")
                payload = client.send_message(session_id=session_id, text=args.text)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=out)
        return 1

    print(json.dumps(payload, ensure_ascii=False), file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
