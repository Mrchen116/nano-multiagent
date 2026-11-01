"""Upgrade existing document-memory state using synthetic offline files."""

import json
from unittest.mock import patch

import pytest
import yaml

from scripts import migrate_dreaming_protocol as migration


def fixture(tmp_path):
    workspace = tmp_path / "subject"
    memory = workspace / ".nanoassistant/memory"
    memory.mkdir(parents=True)
    (memory / "MEMORY.md").write_text("Existing document must survive.\n")
    domain = tmp_path / "state/nano_dreaming"
    (domain / "owners").mkdir(parents=True)
    (domain / "runs").mkdir()
    owner = {
        "activationAt": 1234,
        "streams": {
            "root": {"baseline": 20, "cursor": 40, "continuation": {"offset": 10}}
        },
        "seen": ["original"],
        "rotation": 0,
        "failures": 0,
    }
    (domain / "owners/YQ.json").write_text(json.dumps({"version": 1, "record": owner}))
    for run_id, state, through in [
        ("complete", "completed", 60),
        ("partial", "partial", 90),
    ]:
        run = {
            "id": run_id,
            "agentId": "a",
            "state": state,
            "batch": {"ranges": [{"sessionId": "root", "through": through}]},
            "plan": [{"operationId": run_id}],
            "receipts": [
                {"operationId": run_id, "saved": True, "versionRecorded": False}
            ],
        }
        (domain / f"runs/{run_id}.json").write_text(
            json.dumps({"version": 1, "record": run})
        )
    config = tmp_path / "node.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "agents": [
                    {
                        "agent_id": "a",
                        "workspace_root": str(workspace),
                        "knowledge": {
                            "dreaming": {
                                "maxRunMs": 600000,
                                "maxSteps": 24,
                                "maxInputTokens": 2000,
                            }
                        },
                        "features": {"dreaming": False},
                    }
                ]
            }
        )
    )
    return config, domain, tmp_path / "backup", memory


def test_upgrade_preserves_activation_receipts_documents_and_new_progress(tmp_path):
    config, domain, backup, memory = fixture(tmp_path)
    before = (memory / "MEMORY.md").read_bytes()
    migration.migrate(config, domain, backup, True)
    path = domain / "owners/YQ.json"
    doc = json.loads(path.read_text())
    owner = doc["record"]
    assert owner["protocol"] == 2 and owner["integrated"] == {}
    assert owner["activationAt"] == 1234
    assert owner["streams"]["root"] == {"baseline": 20, "cursor": 60}
    assert (memory / "MEMORY.md").read_bytes() == before
    assert (backup / "workspaces/0/memory/MEMORY.md").read_bytes() == before
    run = json.loads((domain / "runs/partial.json").read_text())["record"]
    assert run["planRetired"] and run["receipts"][0]["saved"]
    agent = yaml.safe_load(config.read_text())["agents"][0]
    assert agent["knowledge"]["dreaming"] == {"maxInputTokens": 2000}
    assert agent["features"]["dreaming"] is False
    owner["streams"]["root"]["cursor"] = 100
    owner["integrated"] = {"child": "new-version"}
    path.write_text(json.dumps(doc))
    migration.migrate(config, domain, backup, True)
    assert json.loads(path.read_text())["record"] == owner


def test_reentry_after_one_published_record(tmp_path):
    config, domain, backup, _ = fixture(tmp_path)
    real = migration.atomic_write
    fired = False

    def interrupt(path, data):
        nonlocal fired
        real(path, data)
        if path == domain / "owners/YQ.json" and not fired:
            fired = True
            raise OSError("simulated interruption")

    with patch.object(migration, "atomic_write", interrupt), pytest.raises(OSError):
        migration.migrate(config, domain, backup, True)
    assert not json.loads((backup / "manifest.json").read_text())["completed"]
    assert migration.migrate(config, domain, backup, True)["completed"]
    assert (
        json.loads((domain / "owners/YQ.json").read_text())["record"]["streams"][
            "root"
        ]["cursor"]
        == 60
    )


def test_requires_stopped_writers_and_known_activation(tmp_path):
    config, domain, backup, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match="Stop"):
        migration.migrate(config, domain, backup)
    path = domain / "owners/YQ.json"
    doc = json.loads(path.read_text())
    del doc["record"]["activationAt"]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="activation"):
        migration.migrate(config, domain, backup, True)
    assert not backup.exists()
