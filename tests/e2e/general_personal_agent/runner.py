"""Real IM execution with resumable, evidence-backed specialist checkpoints."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlparse

from tests.e2e.critical_paths._im_client import IMClient
from .catalog import ASSETS, digest, write_json
from .evidence import capture, get, metrics


class CheckpointRequired(Exception):
    """An actual fault, browser interaction, or timing fixture is still required."""


def request(client, method, path, payload):
    """Use the authenticated public interface and preserve its real response."""
    response = client._http.request(
        method, path, headers=client._auth_headers, json=payload
    )
    response.raise_for_status()
    return response.json()


def validate_manifest(path: Path) -> dict:
    """Require the daily profile's isolated local node and PA binding."""
    manifest = json.loads(path.read_text())
    address = urlparse(manifest["im_url"])
    if address.hostname not in {"127.0.0.1", "localhost", "::1"} or address.port in {
        None,
        8011,
        5173,
    }:
        raise ValueError("evaluation requires a loopback isolated high-port IM")
    if (
        not manifest["node_id"].startswith("wt-")
        or not manifest["personal"]["agent_id"]
    ):
        raise ValueError("evaluation requires a daily worktree manifest")
    return manifest


def verified_files(receipt: dict) -> list[dict]:
    """Require existing files whose exact bytes match the supplied evidence hashes."""
    files = receipt.get("files", [])
    if not files:
        raise ValueError("receipt must reference nonempty evidence files")
    for entry in files:
        path = Path(entry["path"])
        if (
            not path.is_absolute()
            or not path.is_file()
            or digest(path) != entry["sha256"]
        ):
            raise ValueError(f"evidence file missing or changed: {path}")
    return files


class Run:
    """One isolated scenario; continuation resumes after an explicit checkpoint."""

    def __init__(
        self,
        case: dict,
        manifest: Path,
        output: Path,
        username: str,
        password: str,
        timeout: float,
        checkpoint_file: Path | None,
    ):
        self.case, self.output, self.timeout = case, output, timeout
        self.manifest = validate_manifest(manifest)
        self.client = IMClient(self.manifest["im_url"])
        self.client.register_or_login(username, password)
        fixture = json.loads((ASSETS / "fixtures.synthetic.json").read_text())
        request(
            self.client,
            "PATCH",
            "/im/v1/me/timezone",
            {"timezone": fixture["timezone"]},
        )
        self.clients = {"owner": self.client}
        self.agent = self.manifest["personal"]["agent_id"]
        self.checkpoints = (
            json.loads(checkpoint_file.read_text()) if checkpoint_file else {}
        )
        output.mkdir(parents=True, exist_ok=True)
        state_file = output / "state.json"
        if state_file.exists():
            self.state = json.loads(state_file.read_text())
            if (
                self.state["case_id"] != case["id"]
                or self.state["node_id"] != self.manifest["node_id"]
                or self.state["adapter_sha256"] != digest(ASSETS / "adapters.json")
            ):
                raise ValueError("resume must use the same scenario and isolated node")
            for actor in ("colleague", "family", "external"):
                self.clients[actor] = self.actor(actor, password)
        else:
            claim = manifest.parent / ".e2e-pa-evaluation-claim.json"
            if claim.exists():
                raise ValueError(
                    "node already used by an evaluation; use a fresh daily stack"
                )
            if self.client.list_timeline(self.manifest["personal"]["conversation_id"]):
                raise ValueError(
                    "PA is not fresh: existing private timeline would contaminate baseline"
                )
            self.state = {
                "case_id": case["id"],
                "node_id": self.manifest["node_id"],
                "run_id": uuid.uuid4().hex,
                "next_step": 0,
                "receipts": [],
                "adapter_sha256": digest(ASSETS / "adapters.json"),
                "source_sha256": digest(ASSETS / "scenarios.yaml"),
                "started_at": time.time(),
                "actors": {"owner": self.client.user_id},
                "chats": {"owner_pa": self.manifest["personal"]["conversation_id"]},
            }
            write_json(
                claim, {"run_id": self.state["run_id"], "output": str(output.resolve())}
            )
            for actor in ("colleague", "family", "external"):
                self.clients[actor] = self.actor(actor, password)
                self.state["actors"][actor] = self.clients[actor].user_id
            for name, actors, with_pa in (
                ("work_group", ["owner", "colleague", "external"], False),
                ("family_chat", ["owner", "family"], False),
                ("shared_group", ["owner", "colleague", "external", "family"], True),
            ):
                participants = [
                    {"type": "user", "id": self.state["actors"][a]} for a in actors
                ]
                if with_pa:
                    participants.append({"type": "agent", "id": self.agent})
                row = request(
                    self.client,
                    "POST",
                    "/im/v1/conversations",
                    {
                        "title": f"PA eval {case['id']} {name}",
                        "type": "group",
                        "participants": participants,
                    },
                )
                self.state["chats"][name] = row["id"]
            # Exclude template conversations; the fixture's declared scope is exact.
            sources = get(self.client, "/im/v1/personal-agent/sources")
            excluded = [
                row["id"]
                for row in sources["items"]
                if row["id"] not in self.state["chats"].values()
            ]
            request(
                self.client,
                "PATCH",
                "/im/v1/personal-agent/policy",
                {
                    "expected_revision": sources["policy"]["revision"],
                    "excluded_conversation_ids": excluded,
                },
            )
            if any(step["op"] == "observe" for step in case["steps"]):
                self.client.update_agent_config(
                    self.agent,
                    features={"heartbeat": True},
                    heartbeat_json='{"every":"10m"}',
                )
            self.state["config"] = self.client.get_agent_config(self.agent)
            self.state["manifest"] = self.manifest
            write_json(self.output / "rubric.json", self.case)
            self.save()

    def actor(self, name: str, password: str):
        client = IMClient(self.manifest["im_url"])
        client.register_or_login(
            f"paeval-{self.state['run_id'][:10]}-{name}",
            password,
            display_name="林先生" if name in {"colleague", "family"} else name,
        )
        request(client, "POST", "/im/v1/company/join", {})
        request(
            self.client,
            "POST",
            f"/im/v1/company/members/{client.user_id}/approve",
            {},
        )
        return client

    def save(self):
        write_json(self.output / "state.json", self.state)

    def idle(self, work: dict) -> bool:
        if work.get("main_execution") != "idle":
            return False
        for child in work.get("other_executions", []):
            sid = quote(child["session_id"], safe="")
            view = get(
                self.client,
                f"/im/v1/agents/{self.agent}/work/sessions/{sid}/turns",
                limit=1,
            )
            if any(
                turn.get("status") in {"running", "waiting_permission"}
                for turn in view.get("turns", [])
            ):
                return False
        return True

    def settle_observation(self) -> dict:
        deadline, stable, revision = time.monotonic() + self.timeout, None, None
        while time.monotonic() < deadline:
            work = get(self.client, f"/im/v1/agents/{self.agent}/work")
            if work.get("revision") != revision:
                stable, revision = None, work.get("revision")
            if self.idle(work):
                stable = time.monotonic() if stable is None else stable
                if time.monotonic() - stable >= 5:
                    return {"at": time.time(), "work": work}
            else:
                stable = None
            time.sleep(1)
        raise TimeoutError(f"observed PA work did not settle within {self.timeout}s")

    def settle(self, before: dict, conversation: str, sent_id: str):
        deadline, stable = time.monotonic() + self.timeout, None
        last_revision = None
        while time.monotonic() < deadline:
            work = get(self.client, f"/im/v1/agents/{self.agent}/work")
            replies = [
                m
                for m in self.client.agent_messages(conversation, self.agent)
                if m["id"] not in before["messages"]
            ]
            idle = self.idle(work) and work.get("revision", 0) > before["revision"]
            if work.get("revision") != last_revision:
                stable = None
                last_revision = work.get("revision")
            if idle and replies:
                stable = stable or time.monotonic()
                if time.monotonic() - stable >= 5:
                    return {"reply_ids": [m["id"] for m in replies], "sent_id": sent_id}
            else:
                stable = None
            time.sleep(1)
        raise TimeoutError(
            f"no settled real PA reply within {self.timeout}s for {sent_id}"
        )

    def step(self, step: dict, index: int):
        op = step["op"]
        if op == "send":
            client = self.clients[step["actor"]]
            chat = self.state["chats"][step["chat"]]
            text = step["text"].format(**self.state["actors"], **self.state["chats"])
            before = {
                "messages": {m["id"] for m in self.client.list_messages(chat)},
                "revision": get(self.client, f"/im/v1/agents/{self.agent}/work").get(
                    "revision", 0
                ),
            }
            mid = client.send_message(
                chat,
                text,
                idempotency_key=f"{self.state['run_id']}-{index}",
                mentions=[self.agent]
                if step["chat"] == "shared_group" and step["actor"] == "owner"
                else None,
            )
            receipt = {
                "op": op,
                "actor": client.user_id,
                "conversation_id": chat,
                "message_id": mid,
                "text": text,
            }
            if (
                step["settle"]
                and step["actor"] == "owner"
                and step["chat"] in {"owner_pa", "shared_group"}
            ):
                receipt["settled"] = self.settle(before, chat, mid)
            return receipt
        if op == "observe":
            # Wall-clock observation does not manufacture a heartbeat or model turn.
            deadline = time.monotonic() + step["seconds"]
            samples = []
            while time.monotonic() < deadline:
                samples.append(
                    {
                        "at": time.time(),
                        "work": get(self.client, f"/im/v1/agents/{self.agent}/work"),
                    }
                )
                time.sleep(min(10, max(0, deadline - time.monotonic())))
            return {"op": op, "samples": samples, "settled": self.settle_observation()}
        if op == "checkpoint":
            receipt = self.checkpoints.get(step["key"])
            if not receipt:
                raise CheckpointRequired(f"{step['key']}: {step['instruction']}")
            if (
                receipt.get("run_id") != self.state["run_id"]
                or receipt.get("case_id") != self.case["id"]
            ):
                raise ValueError("checkpoint receipt belongs to a different case/run")
            if not receipt.get("performed_by") or not receipt.get("action"):
                raise ValueError(
                    "checkpoint must identify external operator and actual action"
                )
            verified_files(receipt)
            return {"op": op, "key": step["key"], "external_receipt": receipt}
        if op == "disable_memory":
            config = self.client.get_agent_config(self.agent)
            return self.client.update_agent_config(
                self.agent,
                features={"memory_curation": False},
                tool_allowlist=[
                    tool
                    for tool in config.get("tool_allowlist", [])
                    if tool != "memory"
                ],
            )
        if op == "exclude_source":
            source = get(self.client, "/im/v1/personal-agent/sources")
            return request(
                self.client,
                "PATCH",
                "/im/v1/personal-agent/policy",
                {
                    "expected_revision": source["policy"]["revision"],
                    "excluded_conversation_ids": list(
                        set(source["policy"]["excluded_conversation_ids"])
                        | {self.state["chats"][step["chat"]]}
                    ),
                },
            )
        raise ValueError(op)

    def execute(self) -> dict:
        result = {
            "case_id": self.case["id"],
            "run_id": self.state["run_id"],
            "status": "not_run",
            "diagnostic": "evidence_needs_review",
            "evidence_needs_review": True,
            "parts": {
                "im": {"status": "not_run", "diagnostic": "evidence_needs_review"},
                **{
                    f"live_{x}": {
                        "status": "blocked",
                        "diagnostic": "external connection/receipt not supplied",
                    }
                    for x in self.case["external"]
                },
            },
            "completed_steps": self.state["next_step"],
        }
        try:
            for index in range(self.state["next_step"], len(self.case["steps"])):
                self.state["receipts"].append(
                    {
                        "step": index,
                        "at": time.time(),
                        "result": self.step(self.case["steps"][index], index),
                    }
                )
                snapshot = capture(self.client, self.agent, self.state["chats"])
                write_json(self.output / f"step-{index:02d}.json", snapshot)
                self.state["next_step"] = index + 1
                self.save()
            result["execution_complete"] = True
        except CheckpointRequired as error:
            result.update(diagnostic=str(error), execution_complete=False)
        except Exception as error:
            result.update(
                status="failed",
                diagnostic=f"{type(error).__name__}: {error}",
                execution_complete=False,
            )
            result["parts"]["im"] = {
                "status": "failed",
                "diagnostic": result["diagnostic"],
            }
        finally:
            result["completed_steps"] = self.state["next_step"]
            try:
                snapshot = capture(self.client, self.agent, self.state["chats"])
                write_json(self.output / "evidence.json", snapshot)
                result["metrics"] = metrics(
                    snapshot, time.time() - self.state["started_at"]
                )
                result["evidence"] = {
                    "path": str((self.output / "evidence.json").resolve()),
                    "sha256": digest(self.output / "evidence.json"),
                }
                if snapshot["errors"]:
                    result["diagnostic"] += "; incomplete child evidence"
            except Exception as error:
                result["collection_error"] = str(error)
            write_json(self.output / "result.json", result)
            (self.output / "actual-results.jsonl").write_text(
                json.dumps(result, ensure_ascii=False) + "\n"
            )
            for client in self.clients.values():
                client.close()
        return result
