#!/usr/bin/env python3
"""Manage this Git worktree's network preview on the Mini."""

import argparse
import hashlib
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys


def main() -> int:
    """Send a committed revision and operate this worktree's isolated preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("up", "update", "status", "password", "down")
    )
    args = parser.parse_args()
    host = os.environ.get("NANO_PREVIEW_HOST", "mini")
    repo = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    ).resolve()
    owner = f"{socket.gethostname()}\0{os.getuid()}\0{repo}"
    instance = "pv-" + hashlib.sha256(os.fsencode(owner)).hexdigest()[:20]
    remote_args = [args.action, instance]
    if args.action in {"up", "update"}:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        if subprocess.check_output(["git", "status", "--porcelain"], cwd=repo):
            print(
                f"Sending committed revision {commit}. Uncommitted edits are local.",
                file=sys.stderr,
            )
        # Concurrent callers can push distinct revisions before obtaining the Mini instance lock.
        subprocess.run(
            [
                "git",
                "push",
                "--",
                f"{host}:.local/share/nano-preview/source.git",
                f"{commit}:refs/nano-preview/{commit}",
            ],
            cwd=repo,
            check=True,
        )
        remote_args.append(commit)

    command = '. "$HOME/.local/share/nano-preview/env" && exec python - ' + shlex.join(
        remote_args
    )
    helper = Path(__file__).with_name("e2e_preview_remote.py")
    with helper.open("rb") as source:
        return subprocess.run(
            ["ssh", "-T", "--", host, command], stdin=source
        ).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"preview: {error}")
