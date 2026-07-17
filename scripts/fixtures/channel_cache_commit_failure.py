#!/usr/bin/env python3
"""Run the real Gateway with one deterministic removal-cache commit failure.

This acceptance-only wrapper patches the injected ``ChannelManifestStore`` seam,
then delegates to the production ``personal_assistant.main`` entrypoint.  All IM,
Gateway, HTTP, SQLite, lifecycle, and frontend code remains production code; only
the first cache commit containing a removal intent fails.  The following retry
uses the unmodified store implementation in the same process.

Set ``NANO_MULTIAGENT_TEST_ALLOW_FAULT_INJECTION=1`` explicitly to acknowledge
that this process is for an isolated worktree test stack.
"""

from __future__ import annotations

import os
import runpy
from typing import Any

if os.environ.get("NANO_MULTIAGENT_TEST_ALLOW_FAULT_INJECTION") != "1":
    raise SystemExit(
        "set NANO_MULTIAGENT_TEST_ALLOW_FAULT_INJECTION=1 in an isolated test stack"
    )

from personal_assistant.gateway.channel_manifest_store import (  # noqa: E402
    ChannelManifestStore,
    ChannelManifestStoreError,
)


_original_commit_manifest = ChannelManifestStore.commit_manifest
_failure_armed = True


def _commit_manifest_with_one_removal_failure(
    self: ChannelManifestStore,
    manifest: Any,
) -> None:
    """Fail only the first removal commit, then restore normal store behavior."""
    global _failure_armed  # noqa: PLW0603

    removals = getattr(manifest, "removals", ())
    if _failure_armed and removals:
        _failure_armed = False
        raise ChannelManifestStoreError(
            "channel manifest cache write failed (deterministic fixture)"
        )
    _original_commit_manifest(self, manifest)


ChannelManifestStore.commit_manifest = _commit_manifest_with_one_removal_failure
runpy.run_module("personal_assistant.main", run_name="__main__")
