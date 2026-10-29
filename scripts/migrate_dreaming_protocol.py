#!/usr/bin/env python3
"""Offline upgrade of an existing document Dreaming domain to protocol 2.

Pass the exact nano_dreaming per-record directory, stopped node config and a new
backup directory outside all source directories. This never runs at startup.
"""

import argparse
import base64
import json
from pathlib import Path
import shutil

import yaml

try:
    from scripts.migrate_role_memory import (
        atomic_write,
        digest,
        private_tree,
        save_manifest,
    )
except ModuleNotFoundError:
    from migrate_role_memory import atomic_write, digest, private_tree, save_manifest


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def migrate(config_path, domain_path, backup_path, writers_stopped=False):
    """Preserve files/receipts and activation boundaries; retire old model plans."""
    if not writers_stopped:
        raise ValueError("Stop and verify writers before migration")
    config_path, domain_path, backup_path = map(
        lambda p: Path(p).resolve(), (config_path, domain_path, backup_path)
    )
    identity = {"config": str(config_path), "domain": str(domain_path)}
    manifest_path = backup_path / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["identity"] != identity:
            raise ValueError("Migration paths differ from the saved manifest")
        if manifest["completed"]:
            return manifest
    else:
        config = yaml.safe_load(config_path.read_text())
        roots = [
            Path(a["workspace_root"]).resolve() / ".nanoassistant"
            for a in config["agents"]
        ]
        if any(
            backup_path == root or root in backup_path.parents
            for root in [domain_path, *roots]
        ):
            raise ValueError("Backup must be outside source directories")
        if backup_path.exists():
            raise ValueError("Backup directory exists without a manifest")
        owners = {}
        documents = {}
        for path in (domain_path / "owners").glob("*.json"):
            doc = json.loads(path.read_text())
            owner = doc["record"]
            if doc["version"] != 1 or owner.get("protocol") == 2:
                raise ValueError("Expected an unmigrated version-1 domain")
            if not isinstance(owner.get("activationAt"), int) or not isinstance(
                owner.get("streams"), dict
            ):
                raise ValueError(
                    "Missing documented activation boundary; do not infer history"
                )
            agent_id = base64.urlsafe_b64decode(
                path.stem + "=" * (-len(path.stem) % 4)
            ).decode()
            owners[agent_id] = owner
            documents[path] = doc
        if not owners:
            raise ValueError("No existing owner records found")
        for path in (domain_path / "runs").glob("*.json"):
            doc = json.loads(path.read_text())
            run = doc["record"]
            owner = owners.get(run["agentId"])
            if owner is None:
                raise ValueError("Run has no matching owner")
            if run["state"] == "completed":
                receipts = {
                    item["operationId"]: item for item in run.get("receipts", [])
                }
                if any(
                    not receipts.get(op["operationId"], {}).get("saved")
                    for op in run.get("plan", [])
                ):
                    raise ValueError(
                        "Completed run lacks saved file receipts; reconcile before migration"
                    )
                for part in run["batch"]["ranges"]:
                    stream = owner["streams"].get(part["sessionId"])
                    if stream is not None:
                        stream["cursor"] = max(stream["cursor"], part["through"])
            elif run["state"] in ("prepared", "running", "applying"):
                run["state"] = (
                    "partial"
                    if any(r.get("saved") for r in run.get("receipts", []))
                    else "failed"
                )
            run["planRetired"] = True
            run["error"] = (
                "Old input protocol retired during offline upgrade; saved receipts retained."
            )
            documents[path] = doc
        for owner in owners.values():
            owner["protocol"] = 2
            owner["integrated"] = {}
            for stream in owner["streams"].values():
                stream.pop("continuation", None)
            owner.pop("retryAt", None)
            owner["failures"] = 0
        for agent in config["agents"]:
            settings = (agent.get("knowledge") or {}).get("dreaming") or {}
            settings.pop("maxRunMs", None)
            settings.pop("maxSteps", None)
        documents[config_path] = config
        # Prepare a complete rollback copy and every intended replacement before publishing.
        backup_path.mkdir(parents=True, mode=0o700)
        shutil.copytree(domain_path, backup_path / "domain")
        shutil.copy2(config_path, backup_path / "node-config.original")
        for index, root in enumerate(roots):
            for name in ("memory", "maintenance"):
                source = root / name
                if source.exists():
                    shutil.copytree(
                        source,
                        backup_path / "workspaces" / str(index) / name,
                        symlinks=True,
                    )
        replacements = []
        for index, (path, document) in enumerate(documents.items()):
            data = (
                yaml.safe_dump(document, allow_unicode=True, sort_keys=False).encode()
                if path == config_path
                else encode(document)
            )
            planned = backup_path / "planned" / str(index)
            atomic_write(planned, data)
            replacements.append(
                {
                    "path": str(path),
                    "before": digest(path),
                    "after": digest(planned),
                    "planned": str(planned),
                }
            )
        private_tree(backup_path)
        manifest = {
            "identity": identity,
            "workspaces": [str(r) for r in roots],
            "replacements": replacements,
            "completed": False,
        }
        save_manifest(manifest_path, manifest)
    for item in manifest["replacements"]:
        target, planned = Path(item["path"]), Path(item["planned"])
        if digest(planned) != item["after"] or digest(target) not in (
            item["before"],
            item["after"],
        ):
            raise ValueError(
                "Source or planned replacement changed; preserve and inspect the copies"
            )
        if digest(target) != item["after"]:
            atomic_write(target, planned.read_bytes())
    manifest["completed"] = True
    save_manifest(manifest_path, manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            migrate(args.config, args.domain, args.backup, args.writers_stopped),
            ensure_ascii=False,
            indent=2,
        )
    )
