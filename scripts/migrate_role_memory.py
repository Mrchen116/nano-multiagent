#!/usr/bin/env python3
"""One-time, offline feat-676 migration; never invoked by Node startup.

Usage: uv run python scripts/migrate_role_memory.py --config /path/node.yaml
       --baselines /path/persisted-cursors.json --migration-id release-id --writers-stopped

Baselines contain {"activationAt": <epoch-ms>, "agents": {"agent-id":
{"streams": {"root-session-id": <persisted-event-seq>}}}}. An explicitly empty
streams object is valid only after the operator confirms there is no prior history.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

import yaml


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    """Capture original bytes, links and permissions, including hidden Git files."""
    entries = {}
    if not root.exists():
        return entries
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        info = path.lstat()
        entry = {"mode": stat.S_IMODE(info.st_mode)}
        if path.is_symlink():
            entry.update(kind="link", target=os.readlink(path))
        elif path.is_dir():
            entry.update(kind="directory")
        elif path.is_file():
            entry.update(kind="file", sha256=digest(path))
        else:
            raise ValueError(f"Unsupported memory entry: {relative}")
        entries[relative] = entry
    return entries


def contents(entries):
    return {
        name: {key: value for key, value in item.items() if key != "mode"}
        for name, item in entries.items()
    }


def private_tree(root):
    os.chmod(root, 0o700)
    for path in root.rglob("*"):
        if not path.is_symlink():
            os.chmod(path, 0o700 if path.is_dir() else 0o600)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".migration-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_manifest(path, manifest):
    atomic_write(
        path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    )


def normalize_agent(agent):
    """Only convert retired choices; all unrelated selections stay byte-for-value."""
    knowledge = dict(agent.get("knowledge") or {})
    features = dict(agent.get("features") or {})
    workspace_config = Path(agent["workspace_root"]) / ".nanoassistant/config.yaml"
    evolution = (
        (yaml.safe_load(workspace_config.read_text()) or {}).get("self_evolution", {})
        if workspace_config.exists()
        else {}
    )
    legacy = dict(knowledge.get("legacyMemory") or {})
    legacy.setdefault(
        "enabled",
        features.get("memory_curation", evolution.get("memory_curation", True)),
    )
    legacy.setdefault(
        "interval",
        knowledge.get("memoryInterval", evolution.get("memory_nudge_interval", 10)),
    )
    knowledge.setdefault("enabled", evolution.get("enabled", True))
    knowledge.setdefault("memoryMode", "document")
    knowledge["legacyMemory"] = legacy
    knowledge.pop("memoryInterval", None)
    for name in ("maxSteps", "maxRunMs"):
        (knowledge.get("dreaming") or {}).pop(name, None)
    features.pop("memory_curation", None)
    features.pop("skill_creation", None)
    features.setdefault("dreaming", True)
    if isinstance(agent.get("skills"), list):
        # Preserve inferred allowlist mode even when its only old member was fixed.
        if agent.get("skills_selection_mode") is None:
            agent["skills_selection_mode"] = (
                "explicit_allowlist" if agent["skills"] else "default_discovery"
            )
        agent["skills"] = [name for name in agent["skills"] if name != "skill-creator"]
    agent["knowledge"], agent["features"] = knowledge, features


def migrate(config_path, baselines, migration_id, writers_stopped=False):
    """Migrate offline copies with manifest-bound reentry and no history guessing."""
    if not writers_stopped:
        raise ValueError(
            "Stop and verify old writers before migration (--writers-stopped)"
        )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", migration_id) or migration_id in (
        ".",
        "..",
    ):
        raise ValueError("Invalid migration ID")
    config_path = Path(config_path).resolve()
    original = config_path.read_bytes()
    config = yaml.safe_load(original)
    agents = config.get("agents", [])
    workspaces = [str(Path(agent["workspace_root"]).resolve()) for agent in agents]
    if len(set(workspaces)) != len(workspaces):
        raise ValueError(
            "Agents share a writable workspace; explicit ownership resolution required"
        )
    activation = baselines.get("activationAt")
    if (
        not isinstance(activation, int)
        or isinstance(activation, bool)
        or activation < 0
    ):
        raise ValueError("Explicit activationAt is required")
    # Validate all baseline inputs before changing any subject.
    for agent in agents:
        baseline = baselines.get("agents", {}).get(agent["agent_id"])
        if not isinstance(baseline, dict) or not isinstance(
            baseline.get("streams"), dict
        ):
            raise ValueError(
                f"Explicit persisted cursors required for {agent['agent_id']}"
            )
        if any(
            not isinstance(seq, int) or isinstance(seq, bool) or seq < 0
            for seq in baseline["streams"].values()
        ):
            raise ValueError("Invalid persistent cursor")
    reports = []
    for agent in agents:
        root = Path(agent["workspace_root"]).resolve() / ".nanoassistant"
        memory, legacy = root / "memory", root / "memory-legacy"
        backup = root / "memory-backups" / migration_id
        manifest_path = backup / "manifest.json"
        state = {
            "activationAt": activation,
            "streams": {
                key: {"baseline": seq, "cursor": seq}
                for key, seq in baselines["agents"][agent["agent_id"]][
                    "streams"
                ].items()
            },
        }
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if (
                manifest["agentId"] != agent["agent_id"]
                or manifest["workspace"] != str(root.parent)
                or manifest["baseline"] != state
            ):
                raise ValueError(
                    "Migration identity or baseline changed; preserve the existing manifest"
                )
        else:
            if legacy.exists() or backup.exists():
                raise ValueError(
                    "Legacy or backup exists without this migration manifest; refusing overwrite"
                )
            manifest = {
                "version": 1,
                "agentId": agent["agent_id"],
                "workspace": str(root.parent),
                "baseline": state,
                "files": snapshot(memory),
                "rootMode": stat.S_IMODE(memory.stat().st_mode)
                if memory.exists()
                else 0o700,
                "configSha256": hashlib.sha256(original).hexdigest(),
                "phase": "backed_up",
            }
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = Path(tempfile.mkdtemp(prefix=".backup-", dir=backup.parent))
            try:
                if memory.exists():
                    shutil.copytree(memory, temporary / "memory", symlinks=True)
                else:
                    (temporary / "memory").mkdir()
                atomic_write(temporary / "node-config.original", original)
                private_tree(temporary)
                if contents(snapshot(temporary / "memory")) != contents(
                    manifest["files"]
                ):
                    raise ValueError(
                        "Backup verification failed; original memory was not moved"
                    )
                save_manifest(temporary / "manifest.json", manifest)
                os.rename(temporary, backup)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        if (
            contents(snapshot(backup / "memory")) != contents(manifest["files"])
            or digest(backup / "node-config.original") != manifest["configSha256"]
        ):
            raise ValueError("Backup changed; refusing migration")
        if manifest["phase"] == "backed_up":
            if legacy.exists():
                if snapshot(legacy) != manifest["files"]:
                    raise ValueError(
                        "Legacy memory changed before relocation was recorded"
                    )
            else:
                if snapshot(memory) != manifest["files"]:
                    raise ValueError(
                        "Memory changed since backup; stop the writer before retrying"
                    )
                if memory.exists():
                    os.rename(memory, legacy)
                else:
                    legacy.mkdir(parents=True, mode=0o700)
            manifest["phase"] = "relocated"
            save_manifest(manifest_path, manifest)
        audience = (
            "owner-facing personal understanding"
            if agent.get("personal_agent")
            else "reusable expertise for this independent specialist"
        )
        entry = f"# Memory\n\nThis library stores {audience}. No prior facts have been imported.\n\nLegacy backup: ../memory-backups/{migration_id}/memory/\nLegacy writable library: ../memory-legacy/\nImport only when the user requests it.\n"
        if not memory.exists():
            memory.mkdir(parents=True, mode=0o700)
        if not any(memory.iterdir()):
            # Reentry also completes a crash between mkdir and the initial file write.
            atomic_write(memory / "MEMORY.md", entry.encode())
        state_path = root / "maintenance/dreaming-state.json"
        if not state_path.exists():
            save_manifest(state_path, state)
        # Existing progress is authoritative and must never be reset on reentry.
        normalize_agent(agent)
        missing = [
            name
            for name in ["read", "write", "edit", "memory_maintenance"]
            if "tool_allowlist" in agent and name not in agent["tool_allowlist"]
        ]
        manifest["missingTools"] = missing
        manifest["phase"] = "prepared"
        save_manifest(manifest_path, manifest)
        reports.append(
            {
                "agentId": agent["agent_id"],
                "manifest": str(manifest_path),
                "missingTools": missing,
            }
        )
    atomic_write(
        config_path,
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode(),
    )
    for report in reports:
        path = Path(report["manifest"])
        manifest = json.loads(path.read_text())
        manifest["phase"] = "completed"
        save_manifest(path, manifest)
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--baselines", required=True)
    parser.add_argument("--migration-id", required=True)
    parser.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            migrate(
                args.config,
                json.loads(Path(args.baselines).read_text()),
                args.migration_id,
                args.writers_stopped,
            ),
            indent=2,
        )
    )
