"""CLI entry for the personal assistant Node Gateway."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

from personal_assistant.config.local_store import default_local_config_path
from personal_assistant.gateway import im_bootstrap, process_lifecycle

__all__ = ["main"]


def _check_im_reachable(url: str) -> bool:
    """Return whether the configured IM endpoint responds promptly."""
    try:
        httpx.get(url, timeout=1.0, trust_env=False)
        return True
    except Exception:  # noqa: BLE001
        return False


def _print_gateway_started(result: process_lifecycle.BackgroundLaunchResult) -> None:
    """Print the result of a successful foreground or background launch."""
    print(f"Gateway started (pid={result.pid})")
    if result.im_service_url is not None:
        reachable = _check_im_reachable(result.im_service_url)
        status = (
            "connected" if reachable else "unavailable (running offline, will retry)"
        )
        print(f"IM service:      {result.im_service_url}  [{status}]")
    print(f"Log:             {result.log_path}")


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the gateway process entry."""
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(
        description="Run personal assistant gateway runtime"
    )
    parser.add_argument(
        "--config",
        help="Path to local gateway config (defaults to ~/.nanoassistant/config.yaml)",
    )
    parser.add_argument(
        "--im-service-url",
        help="Override the upstream IM service base URL for this launch",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the gateway attached to the current terminal for debugging and smoke tests",
    )
    parser.add_argument(
        "--auto-bind",
        action="store_true",
        help=(
            "Automatically confirm the IM node binding instead of opening a browser URL. "
            "Equivalent to setting NANO_MULTIAGENT_AUTO_BIND=1. "
            "Intended for worktree e2e scripts where no human can click the bind URL."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    for command, help_text in (
        ("stop", "Stop the current background gateway for one config"),
        (
            "restart",
            "Stop then start the background gateway (equivalent to stop + start)",
        ),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--config",
            help="Path to local gateway config (defaults to ~/.nanoassistant/config.yaml)",
        )
        command_parser.add_argument(
            "--im-service-url",
            help="Override the upstream IM service base URL for this launch",
        )
    args = parser.parse_args(argv)
    command = args.command or "start"
    resolved_config_path = (
        str(Path(args.config).expanduser())
        if args.config
        else str(default_local_config_path())
    )
    if getattr(args, "auto_bind", False):
        os.environ["NANO_MULTIAGENT_AUTO_BIND"] = "1"
    try:
        if command == "stop":
            print(process_lifecycle.stop_gateway(config_path=resolved_config_path))
            return 0
        if command == "restart":
            result = process_lifecycle.restart_gateway(
                config_path=resolved_config_path,
                im_service_url_override=args.im_service_url,
            )
            _print_gateway_started(result)
            return 0
        if args.foreground:
            return process_lifecycle.run_gateway(
                config_path=resolved_config_path,
                im_service_url_override=args.im_service_url,
            )
        result = process_lifecycle.launch_gateway_in_background(
            config_path=resolved_config_path,
            im_service_url_override=args.im_service_url,
        )
        _print_gateway_started(result)
        return 0
    except im_bootstrap.GatewayStartupError as exc:
        im_bootstrap.emit_gateway_feedback("ERROR", exc.summary, exc.next_step)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
