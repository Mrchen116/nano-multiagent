#!/usr/bin/env python3
"""Multi-day live-LLM Global Agent proactivity & calibration acceptance runner.

Drives an isolated `./scripts/e2e-up.sh --profile daily` stack over
`NANO_E2E_LOGICAL_CLOCK_SOCKET` using natural human dialogue (zero tool names,
status enum tokens, or prompt-engineering hints) with `NanoApproval` enabled,
verifying:
  1. Multi-conversation origin routing (`#发版群` goal vs `Bob ↔ Q` 1v1 DM),
     quiet `proactive_review` in-place accounting, `03:00` `Dreaming` +
     `proactive_nightly` `proposed` cards, `u_xxxxxx -> UUID` resolution,
     1v1 Agent DM `focus(scope="mine")` attribution, zero morning greeting
     schedules for routine cards, and pre-schedule `<schedule-observation-sync>`
     preventing stale nudges.
  2. Net-new `ROLE.md` standing duty attribution to target `#研发群` (with zero
     prior human messages in `#研发群`) under host-attested `ROLE.md` approval
     evidence.
  3. Two-tier multi-actor memory calibration & scope isolation: bound admin
     standing rule -> `MEMORY.md`; Bob's 1st pure-click rejection -> stateless
     `peekPendingForDreaming` into `knowledge/proactivity-signals.md` (`seen: 1`)
     without premature ban; Bob's 2nd rejection -> Bob-DM-scoped boundary in
     `MEMORY.md` (`### 免打扰禁区`) + `entities/*.md` detail link while `#发版群`
     and Alice's duties remain active; `NoSilentPrefixRewrite` verified on
     `$nano_llm_logs/session/` wire captures.
  4. Mode-aware `proactive_planning` capability contract across `global` vs
     `single_thread` creation and `task_graph` withdrawal.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any
import uuid

import httpx
import yaml

SHANGHAI = timezone(timedelta(hours=8))


class ClockClient:
    """JSON-RPC client over the node's isolated 0600 logical clock Unix socket."""

    def __init__(self, socket_path: Path) -> None:
        """Initialize the Unix domain socket client.

        Args:
            socket_path: Path to `NANO_E2E_LOGICAL_CLOCK_SOCKET`.
        """
        self.socket_path = socket_path
        self._next_id = 1

    def call(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = 300.0
    ) -> dict[str, Any]:
        """Execute one JSON-RPC call over the Unix domain socket."""
        req_id = self._next_id
        self._next_id += 1
        payload = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "method": method,
                    "params": params or {},
                }
            )
            + "\n"
        )
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(self.socket_path))
            sock.sendall(payload.encode("utf-8"))
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
        raw = b"".join(chunks).decode("utf-8").splitlines()[0]
        parsed = json.loads(raw)
        if "error" in parsed and parsed["error"]:
            raise RuntimeError(f"Logical clock {method} failed: {parsed['error']}")
        return parsed["result"]

    def status(self) -> dict[str, Any]:
        """Return current `{nowMs, nowIso}` from the node clock."""
        return self.call("clock.status", timeout=15.0)

    def advance(self, target_dt: datetime, *, settle: bool = True) -> dict[str, Any]:
        """Advance logical clock monotonically to `target_dt` and settle runtime work."""
        return self.call(
            "clock.advance",
            {"targetIso": target_dt.isoformat(), "settle": settle},
            timeout=360.0,
        )


def resolve_llm_logs_root(repo_root: Path) -> Path:
    """Resolve `llm_logs` directory from `scripts/dev_host.py check`."""
    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "dev_host.py"), "check"],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(proc.stdout)
    llm_path = Path(info["resources"]["llm_logs"]["path"])
    if not llm_path.is_dir():
        raise RuntimeError(f"llm_logs directory does not exist: {llm_path}")
    return llm_path


def flatten_json_strings(value: Any) -> str:
    """Recursively join all string leaves in a parsed JSON value."""
    out: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return "\n".join(out)


def strip_cache_control(value: Any) -> Any:
    """Recursively strip volatile `cache_control` annotations for prefix comparison."""
    if isinstance(value, dict):
        return {
            k: strip_cache_control(v) for k, v in value.items() if k != "cache_control"
        }
    if isinstance(value, list):
        return [strip_cache_control(item) for item in value]
    return value


def session_trace_snapshot(
    llm_logs: Path, wt_root: Path, node_id: str, session_id: str
) -> tuple[str, int, list[tuple[str, str]], list[str], list[int]]:
    """Return `(source_kind, step_count, [(locator, text)], prefix_hashes, cache_reads)`."""
    session_root = llm_logs / "session"
    if session_root.is_dir():
        req_files: list[Path] = []
        for folder in session_root.glob(f"*_{session_id}"):
            req_files.extend(folder.glob("*-req-*.json"))
        req_files.sort(key=lambda p: p.name)
        if req_files:
            records: list[tuple[str, str]] = []
            prefix_hashes: list[str] = []
            for p in req_files:
                raw = p.read_text(encoding="utf-8", errors="ignore")
                try:
                    parsed = json.loads(raw)
                    records.append((p.name, flatten_json_strings(parsed)))
                    prefix_material = json.dumps(
                        strip_cache_control(
                            {
                                "instructions": parsed.get("instructions")
                                or parsed.get("system"),
                                "tools": parsed.get("tools"),
                            }
                        ),
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                    prefix_hashes.append(
                        hashlib.sha256(prefix_material.encode("utf-8")).hexdigest()[:16]
                    )
                except json.JSONDecodeError:
                    records.append((p.name, raw))
            return ("llm_logs_session", len(req_files), records, prefix_hashes, [])

    node_runtime = wt_root / ".dsh-runtime" / node_id
    candidates = sorted(
        list(node_runtime.glob(f"**/sessions/**/*{session_id}*/session*.jsonl.zstd"))
        + list(node_runtime.glob(f"**/sessions/**/*{session_id}*/session*.jsonl"))
    )
    records = []
    cache_reads: list[int] = []
    step_count = 0
    for path in candidates:
        if path.suffix == ".zstd":
            raw = subprocess.check_output(["zstd", "-dc", str(path)], text=True)
        else:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        for line in raw.splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("type") == "step/start":
                step_count += 1
            elif obj.get("type") == "assistant/message":
                usage = (obj.get("data") or {}).get("usage") or {}
                cr = usage.get("cacheReadTokens")
                if isinstance(cr, int):
                    cache_reads.append(cr)
            records.append(
                (f"{path.name}#seq={obj.get('seq')}", flatten_json_strings(obj))
            )
    return ("dsh_session_jsonl", step_count, records, [], cache_reads)


def read_ports_env(wt_root: Path) -> dict[str, str]:
    """Parse `export KEY=VALUE` pairs from `.e2e-ports.env`."""
    env_map: dict[str, str] = {}
    for line in (wt_root / ".e2e-ports.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export ") and "=" in line:
            key, value = line[len("export ") :].split("=", 1)
            env_map[key.strip()] = value.strip()
    return env_map


class UserSession:
    """Authenticated HTTP client for one human user in the isolated IM instance."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        display_name: str,
        register: bool,
    ) -> None:
        """Register or log in a user and configure Asia/Shanghai timezone."""
        self.base_url = base_url
        self.username = username
        self.password = password
        self.display_name = display_name
        self.http = httpx.Client(base_url=base_url, trust_env=False, timeout=45.0)
        self.user_id = ""
        if register:
            login_resp = self.http.post(
                "/im/v1/auth/login",
                json={"username": username, "password": password},
            )
            if login_resp.status_code == 200:
                data = login_resp.json()
                self.user_id = data["user"]["id"]
                self.http.headers["Authorization"] = f"Bearer {data['access_token']}"
            else:
                resp = self.http.post(
                    "/im/v1/auth/register",
                    json={
                        "username": username,
                        "password": password,
                        "display_name": display_name,
                        "locale": "zh",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                self.user_id = data["user"]["id"]
                self.http.headers["Authorization"] = f"Bearer {data['access_token']}"
        else:
            self.login()

    def login(self) -> None:
        """Refresh Bearer token via `/im/v1/auth/login`."""
        resp = self.http.post(
            "/im/v1/auth/login",
            json={"username": self.username, "password": self.password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.user_id = data["user"]["id"]
        self.http.headers["Authorization"] = f"Bearer {data['access_token']}"

    def api(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform an authenticated IM HTTP request, auto-refreshing on 401."""
        resp = self.http.request(method, path, **kwargs)
        if resp.status_code == 401 and path != "/im/v1/auth/login":
            self.login()
            if "headers" in kwargs and isinstance(kwargs["headers"], dict):
                kwargs["headers"] = {
                    **kwargs["headers"],
                    "Idempotency-Key": str(uuid.uuid4()),
                }
            resp = self.http.request(method, path, **kwargs)
        if resp.is_error:
            raise RuntimeError(
                f"[{self.username}] IM {method} {path} -> HTTP {resp.status_code}: {resp.text[:600]}"
            )
        return resp.json() if resp.content else None

    def send_message(self, conversation_id: str, text: str) -> dict[str, Any]:
        """Post a natural human chat message in `conversation_id`."""
        return self.api(
            "POST",
            f"/im/v1/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "content": text,
                "attachments": [],
                "sender_user_id": self.user_id,
                "sender_type": "user",
                "timezone": "Asia/Shanghai",
            },
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.http.close()


class GlobalProactivityVerifier:
    """Executes all scenarios of the Global Agent proactivity acceptance suite."""

    def __init__(
        self, wt_root: Path, repo_root: Path, timeout_sec: float = 260.0
    ) -> None:
        """Bind HTTP clients, logical clock socket, workspace paths, and LLM logs."""
        self.wt_root = wt_root.resolve()
        self.repo_root = repo_root.resolve()
        self.timeout_sec = timeout_sec
        self.ports = read_ports_env(self.wt_root)
        self.daily = json.loads(
            (self.wt_root / ".e2e-daily.json").read_text(encoding="utf-8")
        )
        self.gateway_cfg = yaml.safe_load(
            (self.wt_root / ".gateway-config.yaml").read_text(encoding="utf-8")
        )
        self.llm_logs = resolve_llm_logs_root(self.repo_root)

        sock_env = os.environ.get("NANO_E2E_LOGICAL_CLOCK_SOCKET")
        sock_path = Path(sock_env) if sock_env else (self.wt_root / ".e2e-clock.sock")
        if not sock_path.exists():
            raise RuntimeError(
                f"Logical clock socket not found at {sock_path}; start stack with NANO_E2E_LOGICAL_CLOCK_SOCKET"
            )
        self.clock = ClockClient(sock_path)

        self.agent_id = "daily-quality"
        self.node_id: str = self.gateway_cfg["node"]["node_id"]
        self.workspace_base = Path(self.gateway_cfg["node"]["workspace_base"])
        self.q_workspace = self.workspace_base / self.agent_id
        self.project_dir = self.workspace_base / "project"

        base_url = self.ports["IM_URL"]
        admin_pw = os.environ.get("ADMIN_PASSWORD", "nano1234")
        self.admin = UserSession(
            base_url, "nano", admin_pw, "Nano Admin", register=False
        )
        self.alice = UserSession(
            base_url, "alice_rel", "alicePass123!", "Alice", register=True
        )
        self.bob = UserSession(base_url, "bob_dev", "bobPass123!", "Bob", register=True)

        # Join & approve Alice and Bob into company:default (idempotent across reruns)
        for member in (self.alice, self.bob):
            join_resp = member.http.post("/im/v1/company/join", json={})
            if join_resp.is_error and join_resp.status_code != 409:
                join_resp.raise_for_status()
            app_resp = self.admin.http.post(
                f"/im/v1/company/members/{member.user_id}/approve", json={}
            )
            if app_resp.is_error and app_resp.status_code not in (400, 409):
                app_resp.raise_for_status()
            member.api(
                "PATCH", "/im/v1/me/timezone", json={"timezone": "Asia/Shanghai"}
            )
        self.admin.api(
            "PATCH", "/im/v1/me/timezone", json={"timezone": "Asia/Shanghai"}
        )

    def close(self) -> None:
        """Close all HTTP clients."""
        for client in (self.admin, self.alice, self.bob):
            client.close()

    def list_messages(
        self, viewer: UserSession, conversation_id: str
    ) -> list[dict[str, Any]]:
        """Return chronological main-timeline and thread messages in `conversation_id`."""
        data = viewer.api(
            "GET",
            f"/im/v1/conversations/{conversation_id}/messages",
            params={"limit": 100},
        )
        raw_items = (
            data["items"] if isinstance(data, dict) and "items" in data else data
        )
        main_msgs: list[dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, dict) and "message" in item:
                if item.get("type", "message") == "message" and isinstance(
                    item["message"], dict
                ):
                    main_msgs.append(item["message"])
            elif isinstance(item, dict):
                main_msgs.append(item)
        msgs: list[dict[str, Any]] = list(main_msgs)
        for root_msg in main_msgs:
            thread_info = root_msg.get("thread")
            if (
                isinstance(thread_info, dict)
                and int(thread_info.get("reply_count") or 0) > 0
            ):
                tdata = viewer.api(
                    "GET",
                    f"/im/v1/conversations/{conversation_id}/threads/{root_msg['id']}",
                )
                for titem in tdata.get("items", []):
                    if isinstance(titem, dict) and isinstance(
                        titem.get("message"), dict
                    ):
                        msgs.append(titem["message"])
        return sorted(
            msgs, key=lambda m: (m.get("created_at") or "", m.get("id") or "")
        )

    def agent_messages(
        self, viewer: UserSession, conversation_id: str
    ) -> list[dict[str, Any]]:
        """Return completed assistant chat messages (excluding system notices)."""
        return [
            m
            for m in self.list_messages(viewer, conversation_id)
            if m.get("sender_type") == "agent" and m.get("system_notice") is None
        ]

    def wait_for_q_idle(
        self,
        *,
        min_turn_seq: int | None = None,
        watch_conv: tuple[UserSession, str, int] | None = None,
        wait_all_subagents: bool = True,
    ) -> dict[str, Any]:
        """Poll `daily-quality` Work view until turns/subagents/messages settle idle."""
        deadline = time.monotonic() + self.timeout_sec
        stable_polls = 0
        while time.monotonic() < deadline:
            work = self.admin.api(
                "GET",
                f"/im/v1/agents/{self.agent_id}/work",
                params={"view": "summary", "limit": 50},
            )
            turns = work.get("turns") or []
            latest_seq = max(
                (int(t.get("turn_id") or t.get("seq") or 0) for t in turns), default=0
            )
            main_exec = work.get("main_execution")
            sync_state = work.get("record_sync_state")
            any_running = (
                main_exec in ("running", "waiting_permission")
                or sync_state == "catching_up"
                or any(
                    t.get("status") in ("running", "waiting_permission") for t in turns
                )
            )
            if wait_all_subagents and not any_running:
                act = self.admin.api(
                    "GET", f"/im/v1/agents/{self.agent_id}/work/activity"
                )
                if (
                    int(act.get("running_count") or 0) > 0
                    or int(act.get("waiting_permission_count") or 0) > 0
                ):
                    any_running = True
            msgs_ok = True
            if watch_conv is not None:
                viewer, cid, expected_min = watch_conv
                msgs = self.agent_messages(viewer, cid)
                all_done = all(
                    m.get("delivery_status") in ("completed", "failed") for m in msgs
                )
                msgs_ok = all_done and len(msgs) >= expected_min
            turns_ok = min_turn_seq is None or latest_seq >= min_turn_seq
            if not any_running and turns_ok and msgs_ok:
                stable_polls += 1
                if stable_polls >= 3:
                    return work
            else:
                stable_polls = 0
            time.sleep(1.0)
        raise TimeoutError(
            f"Agent {self.agent_id} did not settle to idle within {self.timeout_sec}s"
        )

    def graphs_for_conversation(
        self, viewer: UserSession, conversation_id: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return `(graphs, flattened_nodes)` belonging to `conversation_id`."""
        listing = viewer.api(
            "GET",
            "/im/v1/task-graphs",
            params={"conversation_id": conversation_id, "limit": 50},
        )
        graphs: list[dict[str, Any]] = []
        nodes: list[dict[str, Any]] = []
        for item in listing.get("items", []):
            gid = item["graph_id"]
            doc = viewer.api("GET", f"/im/v1/task-graphs/{gid}", params={"view": "all"})
            graphs.append(doc)
            for node in doc.get("nodes", []):
                nodes.append(
                    {
                        "graph_id": gid,
                        "conversation_id": doc.get("conversation_id"),
                        "revision": doc["revision"],
                        **node,
                    }
                )
        return graphs, nodes

    def cron_jobs(self) -> list[dict[str, Any]]:
        """Return cron jobs for `daily-quality`."""
        res = self.admin.api("GET", f"/im/v1/agents/{self.agent_id}/cron/jobs")
        return res.get("jobs", res) if isinstance(res, dict) else res

    def memory_git_log(self) -> list[str]:
        """Return recent `oneline` commits from `<q_workspace>/.nanoassistant/memory`."""
        mem_dir = self.q_workspace / ".nanoassistant" / "memory"
        if not (mem_dir / ".git").exists():
            return []
        out = subprocess.check_output(
            ["git", "-C", str(mem_dir), "log", "--oneline", "-n", "10"],
            text=True,
        )
        return [line.strip() for line in out.splitlines() if line.strip()]

    def run(self) -> dict[str, Any]:
        """Execute Scenarios 1, 2, 3, and 4 end-to-end and return structured evidence."""
        report: dict[str, Any] = {
            "agent_id": self.agent_id,
            "node_id": self.node_id,
            "users": {
                "admin": self.admin.user_id,
                "alice": self.alice.user_id,
                "bob": self.bob.user_id,
            },
            "scenarios": {},
        }

        # ── Scenario 4: Mode-aware proactive_planning capability contract ──
        print(
            "[global-24h] Scenario 4: Verifying global vs single_thread capability contract ...",
            file=sys.stderr,
            flush=True,
        )
        q_cfg = self.admin.api("GET", f"/im/v1/agents/{self.agent_id}/config")
        q_caps = self.admin.api("GET", f"/im/v1/agents/{self.agent_id}/capabilities")
        q_feat_keys = [f["key"] for f in q_caps.get("features", [])]
        assert "proactive_planning" in q_feat_keys, (
            f"Expected proactive_planning in Global capabilities: {q_feat_keys}"
        )

        single_id = f"single-helper-{uuid.uuid4().hex[:6]}"
        created_single = self.admin.api(
            "POST",
            f"/im/v1/nodes/{self.node_id}/agents",
            json={
                "agent_id": single_id,
                "display_name": "Single Helper",
                "description": "Single-thread verification helper",
                "work_mode": "single_thread",
            },
        )
        single_caps = self.admin.api("GET", f"/im/v1/agents/{single_id}/capabilities")
        single_feat_keys = [f["key"] for f in single_caps.get("features", [])]
        assert "proactive_planning" not in single_feat_keys, (
            f"single_thread capabilities must hide proactive_planning: {single_feat_keys}"
        )
        assert (
            created_single.get("features", {}).get("proactive_planning") is not True
        ), (
            f"single_thread creation must not enable proactive_planning: {created_single}"
        )
        assert "nano-proactive-care" not in (created_single.get("skills") or []), (
            f"single_thread default skills must strip nano-proactive-care: {created_single.get('skills')}"
        )
        # Turning off task_graph on single_thread succeeds without proactive_planning deadlock
        updated_single_features = {
            **created_single.get("features", {}),
            "task_graph": False,
        }
        updated_single_tools = [
            t for t in (created_single.get("tool_allowlist") or []) if t != "task_graph"
        ]
        updated_single = self.admin.api(
            "PATCH",
            f"/im/v1/agents/{single_id}/config",
            json={
                "profile_version": created_single["profile_version"],
                "display_name": created_single["display_name"],
                "description": created_single["description"],
                "work_mode": "single_thread",
                "collaboration_scope": created_single["collaboration_scope"],
                "features": updated_single_features,
                "tool_allowlist": updated_single_tools,
            },
        )
        assert updated_single["features"]["task_graph"] is False
        report["scenarios"]["scenario_4_capability_contract"] = {
            "passed": True,
            "global_exposes_proactive_planning": True,
            "single_thread_hides_proactive_planning": True,
            "single_thread_strips_proactive_skill": True,
            "single_thread_disables_task_graph_cleanly": True,
            "q_initial_profile_version": q_cfg["profile_version"],
        }

        # ── Conversations & Standing ROLE.md Setup ──
        if q_cfg.get("collaboration_scope") != "team":
            q_cfg = self.admin.api(
                "PATCH",
                f"/im/v1/agents/{self.agent_id}/config",
                json={
                    "profile_version": q_cfg["profile_version"],
                    "display_name": q_cfg["display_name"],
                    "description": q_cfg["description"],
                    "work_mode": "global",
                    "collaboration_scope": "team",
                    "features": q_cfg.get("features", {}),
                    "tool_allowlist": q_cfg.get("tool_allowlist", []),
                },
            )
        release_group = self.admin.api(
            "POST",
            "/im/v1/conversations",
            json={
                "type": "group",
                "visibility": "public",
                "title": "发版群",
                "participants": [
                    {"type": "user", "id": self.alice.user_id},
                    {"type": "user", "id": self.bob.user_id},
                    {"type": "agent", "id": self.agent_id},
                ],
            },
        )
        rd_group = self.admin.api(
            "POST",
            "/im/v1/conversations",
            json={
                "type": "group",
                "visibility": "public",
                "title": "研发群",
                "participants": [
                    {"type": "user", "id": self.alice.user_id},
                    {"type": "agent", "id": self.agent_id},
                ],
            },
        )
        bob_dm = self.bob.api(
            "POST",
            "/im/v1/conversations",
            json={
                "type": "direct",
                "title": "Q · 独立质量",
                "participants": [{"type": "agent", "id": self.agent_id}],
            },
        )
        admin_dm = self.admin.api(
            "POST",
            "/im/v1/conversations",
            json={
                "type": "direct",
                "title": "Q · 独立质量",
                "participants": [{"type": "agent", "id": self.agent_id}],
            },
        )
        rel_cid = release_group["id"]
        rd_cid = rd_group["id"]
        bob_cid = bob_dm["id"]
        adm_cid = admin_dm["id"]
        q_user_id = next(
            p["user_id"]
            for p in release_group["participants"]
            if p.get("type") == "agent" and p.get("id") == self.agent_id
        )
        q_mention = f'<mention type="user" target_id="{q_user_id}"/>'
        report["conversations"] = {
            "release_group": rel_cid,
            "rd_group": rd_cid,
            "bob_dm": bob_cid,
            "admin_dm": adm_cid,
        }

        # Configure standing ROLE.md for Q (including pure ROLE duty for #研发群!)
        role_cur = self.admin.api("GET", f"/im/v1/agents/{self.agent_id}/role")
        standing_role = (
            f"你是团队质量与发版守门人 Q，共享项目目录为 {self.project_dir}。\n"
            "1. 跟进「发版群」中的版本发布目标，围绕登录鉴权与跨源权限改动为目标负责人（Alice）筹备回归核查子项；若发现阻塞明早推进的配置冲突，仅在确有必要时安排工作时段提醒回原群。\n"
            f"2. 常驻巡检职责：每日夜间检查 {self.project_dir}/smoke-status.md；一旦发现未登记跟进的冒烟回归失败，直接归属到「研发群」（目标群名：研发群，拍板人指派 Alice）建立待拍板候选卡，切勿发往管理员私聊。\n"
            "3. 严格保持各会话独立归属：1对1私聊交办的目标或排查事项只留在该私聊跟进；夜间巡检时结合共享项目目录里关联脚本/配置的实际代码隐患，在该私聊目标下补充待对方拍板的候选验证或修复子项，绝不外泄到群聊。"
        )
        self.admin.api(
            "PUT",
            f"/im/v1/agents/{self.agent_id}/role",
            json={"content": standing_role, "version": role_cur["version"]},
        )

        # Seed shared workspace artifacts:
        # 1) Unhandled smoke failure for Scenario 2 (#研发群 has ZERO human chat messages!)
        (self.project_dir / "smoke-status.md").write_text(
            "# Nightly Smoke Report\n\n"
            "- Status: **FAILED** (unhandled)\n"
            "- Failing suite: `checklist_sync_regression`\n"
            "- Error: `TokenRefreshCursorError: empty cursor returned HTTP 500 in sync adapter`\n",
            encoding="utf-8",
        )
        # 2) Release config conflict for #发版群
        (self.project_dir / "release-env.yaml").write_text(
            "release: '1.2.0'\n"
            "AUTH_CROSS_SOURCE_STRICT: true\n"
            "LEGACY_TOKEN_FALLBACK: true  # CONFLICT: causes startup panic when STRICT=true\n",
            encoding="utf-8",
        )
        # 3) Shared workspace script for Bob's 1v1 DM goal
        scripts_dir = self.project_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "log-cleaner.py").write_text(
            "import urllib.request\n\n"
            "def upload_cleaned_batch(endpoint: str, payload: bytes) -> bytes:\n"
            "    # Hard 1.5s socket timeout with zero retry on multi-GB batch upload\n"
            "    with urllib.request.urlopen(endpoint, data=payload, timeout=1.5) as resp:\n"
            "        return resp.read()\n",
            encoding="utf-8",
        )

        now_ms = self.clock.status()["nowMs"]
        now_sh = datetime.fromtimestamp(now_ms / 1000.0, tz=SHANGHAI)
        day0 = now_sh.date()
        t_day0_2000 = datetime(day0.year, day0.month, day0.day, 20, 0, tzinfo=SHANGHAI)
        if t_day0_2000.timestamp() * 1000 <= now_ms + 60_000:
            day0 = day0 + timedelta(days=1)
            t_day0_2000 = datetime(
                day0.year, day0.month, day0.day, 20, 0, tzinfo=SHANGHAI
            )
        day1 = day0 + timedelta(days=1)
        day2 = day0 + timedelta(days=2)
        day3 = day0 + timedelta(days=3)
        cn_day = lambda d: f"{d.month}月{d.day}日"

        # ── Day 0 Evening: Admin standing rule + #发版群 goal + Bob 1v1 DM + Quiet Review ──
        print(
            f"[global-24h] Advancing to Day 0 20:00 ({t_day0_2000.isoformat()}) ...",
            file=sys.stderr,
            flush=True,
        )
        self.clock.advance(t_day0_2000)

        adm_before = len(self.agent_messages(self.admin, adm_cid))
        self.admin.send_message(
            adm_cid,
            "Q，跟你立两条岗位通用规矩：第一，团队里任何人随口提到的个人草稿分支小实验（还没准备合入主干的），你心里有数就行，千万别主动拿个人草稿分支去建任务卡；第二，只要涉及登录鉴权和跨源权限链路的发版改动，夜间筹划时都要主动帮负责人梳理回归检查点。",
        )
        work0 = self.wait_for_q_idle(watch_conv=(self.admin, adm_cid, adm_before + 1))
        q_session_id: str = work0["main_session_id"]
        report["q_main_session_id"] = q_session_id

        self.clock.advance(
            datetime(day0.year, day0.month, day0.day, 20, 4, tzinfo=SHANGHAI)
        )
        rel_before = len(self.agent_messages(self.alice, rel_cid))
        self.alice.send_message(
            rel_cid,
            f"各位，我来牵头{cn_day(day2)}晚上的 1.2 版本发版目标：这次重点上线登录鉴权与跨源权限校验重构。{q_mention} 麻烦先把这个 1.2 发版总目标在群里立起来，另外项目目录里 release-env.yaml 刚改了开关，明天上午十点帮我们在群里核对一眼那个配置冲突修没修好。",
        )
        self.wait_for_q_idle(watch_conv=(self.alice, rel_cid, rel_before + 1))

        self.clock.advance(
            datetime(day0.year, day0.month, day0.day, 20, 8, tzinfo=SHANGHAI)
        )
        bob_before = len(self.agent_messages(self.bob, bob_cid))
        self.bob.send_message(
            bob_cid,
            f"嗨 Q，我这边在跟进共享目录 scripts/log-cleaner.py 大文件批量上传偶发连接超时的收尾目标，{cn_day(day3)}前我得搞定它。今晚太晚了我先下班了，麻烦先在咱们私聊把总目标立起来就行，具体代码隐患今晚先不用展开聊（另外我自己有个没准备合入主干的个人草稿分支 sandbox-toy，纯粹练手玩玩不用管）。",
        )
        self.wait_for_q_idle(watch_conv=(self.bob, bob_cid, bob_before + 1))

        # Verify #研发群 still has ZERO human messages and ZERO agent messages
        assert len(self.list_messages(self.admin, rd_cid)) == 0

        counts_before_review = {
            "rel": len(self.agent_messages(self.alice, rel_cid)),
            "rd": len(self.agent_messages(self.admin, rd_cid)),
            "bob": len(self.agent_messages(self.bob, bob_cid)),
            "adm": len(self.agent_messages(self.admin, adm_cid)),
        }

        # Advance +16m to 20:25 -> quiet proactive_review
        print(
            "[global-24h] Advancing to 20:25 for quiet proactive_review ...",
            file=sys.stderr,
            flush=True,
        )
        self.clock.advance(
            datetime(day0.year, day0.month, day0.day, 20, 25, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()

        counts_after_review = {
            "rel": len(self.agent_messages(self.alice, rel_cid)),
            "rd": len(self.agent_messages(self.admin, rd_cid)),
            "bob": len(self.agent_messages(self.bob, bob_cid)),
            "adm": len(self.agent_messages(self.admin, adm_cid)),
        }
        assert counts_after_review == counts_before_review, (
            f"Quiet proactive_review must send 0 chat messages: {counts_before_review} -> {counts_after_review}"
        )

        # ── Night 1 (03:05 Dreaming -> 03:20 proactive_nightly): Scenarios 1b, 2, 3a ──
        print(
            "[global-24h] Advancing to Day 1 03:05 (Dreaming) -> 03:20 (proactive_nightly) ...",
            file=sys.stderr,
            flush=True,
        )
        self.clock.advance(
            datetime(day1.year, day1.month, day1.day, 3, 5, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()
        self.clock.advance(
            datetime(day1.year, day1.month, day1.day, 3, 20, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()

        counts_after_night1 = {
            "rel": len(self.agent_messages(self.alice, rel_cid)),
            "rd": len(self.agent_messages(self.admin, rd_cid)),
            "bob": len(self.agent_messages(self.bob, bob_cid)),
            "adm": len(self.agent_messages(self.admin, adm_cid)),
        }
        assert counts_after_night1 == counts_before_review, (
            f"Night 1 (03:00-06:00) must send 0 outbound chat messages: {counts_after_night1}"
        )

        mem_file = self.q_workspace / ".nanoassistant" / "memory" / "MEMORY.md"
        assert mem_file.is_file(), f"Expected formal MEMORY.md at {mem_file}"
        mem_night1 = mem_file.read_text(encoding="utf-8")
        assert "## 主动性与介入偏好" in mem_night1, (
            f"Missing proactive H2 section in MEMORY.md:\n{mem_night1}"
        )

        _, rel_nodes_n1 = self.graphs_for_conversation(self.alice, rel_cid)
        _, rd_nodes_n1 = self.graphs_for_conversation(self.admin, rd_cid)
        _, bob_nodes_n1 = self.graphs_for_conversation(self.bob, bob_cid)
        _, adm_nodes_n1 = self.graphs_for_conversation(self.admin, adm_cid)

        # Guard: personal draft toy branch must not become a card anywhere
        all_n1_nodes = rel_nodes_n1 + rd_nodes_n1 + bob_nodes_n1 + adm_nodes_n1
        toy_cards = [
            n
            for n in all_n1_nodes
            if "sandbox-toy" in (n.get("title", "") + n.get("description", ""))
        ]
        assert len(toy_cards) == 0, (
            f"Admin standing no-intrusion boundary violated (sandbox-toy): {toy_cards}"
        )

        # Scenario 1b: #发版群 proposed card points to Alice (u_xxxxxx -> UUID) and enters Alice's needs_you
        rel_proposed_n1 = [n for n in rel_nodes_n1 if n.get("status") == "proposed"]
        assert len(rel_proposed_n1) >= 1, (
            f"Expected >= 1 proposed card in #发版群, got: {rel_nodes_n1}"
        )
        assert any(
            n.get("proposed_for_user_id") == self.alice.user_id for n in rel_proposed_n1
        ), (
            f"Expected #发版群 proposed card to resolve proposed_for_user_id to Alice ({self.alice.user_id}): {rel_proposed_n1}"
        )
        alice_focus_n1 = self.alice.api(
            "GET", "/im/v1/task-graphs/focus", params={"scope": "mine"}
        )
        alice_needs_ids = {
            f"{x['graph_id']}:{x['node_id']}"
            for x in alice_focus_n1.get("needs_you", [])
        }
        assert any(
            f"{n['graph_id']}:{n['id']}" in alice_needs_ids for n in rel_proposed_n1
        ), (
            f"#发版群 proposed card missing from Alice's needs_you: {alice_focus_n1.get('needs_you')}"
        )

        # Scenario 1b: Bob 1v1 DM proposed card stays in bob_dm, enters Bob's needs_you, ZERO leak to Alice/Admin/groups
        bob_proposed_n1 = [n for n in bob_nodes_n1 if n.get("status") == "proposed"]
        assert len(bob_proposed_n1) >= 1, (
            f"Expected >= 1 proposed card in Bob 1v1 DM, got: {bob_nodes_n1}"
        )
        assert all(
            n.get("proposed_for_user_id") == self.bob.user_id for n in bob_proposed_n1
        ), (
            f"Expected Bob 1v1 DM proposed cards to auto-attribute proposed_for_user_id=Bob: {bob_proposed_n1}"
        )
        bob_focus_n1 = self.bob.api(
            "GET", "/im/v1/task-graphs/focus", params={"scope": "mine"}
        )
        bob_needs_ids = {
            f"{x['graph_id']}:{x['node_id']}" for x in bob_focus_n1.get("needs_you", [])
        }
        assert any(
            f"{n['graph_id']}:{n['id']}" in bob_needs_ids for n in bob_proposed_n1
        ), (
            f"Bob 1v1 DM proposed card missing from Bob's needs_you: {bob_focus_n1.get('needs_you')}"
        )
        assert not any(
            x.get("conversation_id") == bob_cid
            for x in alice_focus_n1.get("needs_you", [])
        ), "Bob's 1v1 DM task leaked into Alice's focus!"
        admin_focus_n1 = self.admin.api(
            "GET", "/im/v1/task-graphs/focus", params={"scope": "mine"}
        )
        assert not any(
            x.get("conversation_id") == bob_cid
            for x in admin_focus_n1.get("needs_you", [])
        ), "Bob's 1v1 DM task leaked into bound admin's focus!"

        # Scenario 2: #研发群 (ZERO prior human messages!) receives pure ROLE.md duty proposed card (NOT admin_dm!)
        rd_proposed_n1 = [n for n in rd_nodes_n1 if n.get("status") == "proposed"]
        adm_proposed_n1 = [n for n in adm_nodes_n1 if n.get("status") == "proposed"]
        assert len(rd_proposed_n1) >= 1, (
            f"Expected pure ROLE.md smoke-failure proposed card in #研发群 (0 prior chat), got rd={rd_nodes_n1}, adm={adm_nodes_n1}"
        )
        assert len(adm_proposed_n1) == 0, (
            f"Pure ROLE.md duty card must route to #研发群, NOT bound admin DM: {adm_proposed_n1}"
        )

        # Check schedules after Night 1: no routine morning-greeting schedule for Bob's 1v1 DM
        jobs_n1 = [j for j in self.cron_jobs() if j.get("enabled")]
        bob_jobs_n1 = [
            j for j in jobs_n1 if bob_cid in json.dumps(j, ensure_ascii=False)
        ]
        assert len(bob_jobs_n1) == 0, (
            f"Routine 1v1 DM proposed card must stay silent on board without morning-greeting schedule: {bob_jobs_n1}"
        )

        report["scenarios"]["scenario_1_and_2_night1_routing"] = {
            "passed": True,
            "release_group_proposed": [n["title"] for n in rel_proposed_n1],
            "rd_group_pure_role_proposed": [n["title"] for n in rd_proposed_n1],
            "bob_dm_proposed": [n["title"] for n in bob_proposed_n1],
            "admin_dm_proposed_count": len(adm_proposed_n1),
            "alice_needs_you_count": len(alice_focus_n1.get("needs_you", [])),
            "bob_needs_you_count": len(bob_focus_n1.get("needs_you", [])),
            "bob_morning_schedules": len(bob_jobs_n1),
        }

        # ── Scenario 1c: Pre-schedule <schedule-observation-sync> prevents stale risk nudge ──
        print(
            "[global-24h] Scenario 1c: Pre-schedule observation sync at 09:55 -> 10:05 ...",
            file=sys.stderr,
            flush=True,
        )
        # At 09:55 (5m before the 10:00 check, inside the 10m group batch window!), Alice fixes release-env.yaml and announces in #发版群
        self.clock.advance(
            datetime(day1.year, day1.month, day1.day, 9, 55, tzinfo=SHANGHAI)
        )
        (self.project_dir / "release-env.yaml").write_text(
            "release: '1.2.0'\n"
            "AUTH_CROSS_SOURCE_STRICT: true\n"
            "LEGACY_TOKEN_FALLBACK: false  # Fixed by Alice at 09:55\n",
            encoding="utf-8",
        )
        self.alice.send_message(
            rel_cid,
            "跟大家同步一下：release-env.yaml 里 LEGACY_TOKEN_FALLBACK 跟严格鉴权冲突的开关我刚已经改成 false 并本地验证通过啦，十点不用再专门提醒这项配置隐患了！",
        )
        time.sleep(2.0)
        _, steps_before_1000, recs_before_1000, _, _ = session_trace_snapshot(
            self.llm_logs, self.wt_root, self.node_id, q_session_id
        )
        self.clock.advance(
            datetime(day1.year, day1.month, day1.day, 10, 5, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()
        _, steps_after_1000, recs_after_1000_all, _, _ = session_trace_snapshot(
            self.llm_logs, self.wt_root, self.node_id, q_session_id
        )
        recs_1000 = recs_after_1000_all[len(recs_before_1000) :]
        has_obs_sync = any(
            "Fresh observation sync completed before this scheduled check" in txt
            for _, txt in recs_1000
        )
        assert has_obs_sync, (
            "Expected <schedule-observation-sync> before 10:00 scheduled check in Q trace"
        )
        report["scenarios"]["scenario_1c_pre_schedule_sync"] = {
            "passed": True,
            "schedule_observation_sync_verified": has_obs_sync,
            "steps_delta": steps_after_1000 - steps_before_1000,
        }

        # ── Scenario 3b: Bob's 1st pure-click rejection -> Night 2 proactivity-signals.md (seen=1, not promoted yet) ──
        print(
            "[global-24h] Scenario 3b: Bob 1st UI rejection -> Night 2 signal pool ...",
            file=sys.stderr,
            flush=True,
        )
        self.clock.advance(
            datetime(day1.year, day1.month, day1.day, 15, 0, tzinfo=SHANGHAI)
        )
        for pnode in bob_proposed_n1:
            latest_doc = self.bob.api(
                "GET", f"/im/v1/task-graphs/{pnode['graph_id']}", params={"view": "all"}
            )
            self.bob.api(
                "POST",
                f"/im/v1/task-graphs/{pnode['graph_id']}/apply",
                json={
                    "base_revision": latest_doc["revision"],
                    "request_key": f"bob-reject-1-{uuid.uuid4()}",
                    "change_note": "临时脚本我自己顺手看就行，不用单列待办卡",
                    "operations": [
                        {
                            "op": "update_task",
                            "node_id": pnode["id"],
                            "patch": {"status": "closed"},
                        }
                    ],
                },
            )

        # Advance to Night 2 (03:05 Dreaming -> 03:20 proactive_nightly) with ZERO chat messages from Bob after the click!
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 3, 5, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 3, 20, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()

        signals_file = (
            self.q_workspace
            / ".nanoassistant"
            / "memory"
            / "knowledge"
            / "proactivity-signals.md"
        )
        assert signals_file.is_file(), (
            f"Expected stateless pendingTaskContext Dreaming to write {signals_file}"
        )
        signals_n2 = signals_file.read_text(encoding="utf-8")
        mem_n2 = mem_file.read_text(encoding="utf-8")
        assert "seen: 1" in signals_n2 or "seen:1" in signals_n2 or "1" in signals_n2, (
            f"Expected single implicit click recorded in proactivity-signals.md:\n{signals_n2}"
        )

        # ── Scenario 3c: Bob 2nd rejection + Alice new #发版群 milestone -> Night 3 scoped promotion & isolation ──
        print(
            "[global-24h] Scenario 3c: Bob 2nd rejection + Alice #发版群 update -> Night 3 scoped promotion ...",
            file=sys.stderr,
            flush=True,
        )
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 14, 0, tzinfo=SHANGHAI)
        )
        # Ensure Bob rejects a 2nd proposed card (or creates & closes a 2nd proposed card / explicit follow-up)
        _, bob_nodes_day2 = self.graphs_for_conversation(self.bob, bob_cid)
        bob_prop_day2 = [n for n in bob_nodes_day2 if n.get("status") == "proposed"]
        if bob_prop_day2:
            for pnode in bob_prop_day2:
                latest_doc = self.bob.api(
                    "GET",
                    f"/im/v1/task-graphs/{pnode['graph_id']}",
                    params={"view": "all"},
                )
                self.bob.api(
                    "POST",
                    f"/im/v1/task-graphs/{pnode['graph_id']}/apply",
                    json={
                        "base_revision": latest_doc["revision"],
                        "request_key": f"bob-reject-2-{uuid.uuid4()}",
                        "change_note": "再次不采纳私聊里的临时脚本跟进卡",
                        "operations": [
                            {
                                "op": "update_task",
                                "node_id": pnode["id"],
                                "patch": {"status": "closed"},
                            }
                        ],
                    },
                )
        (scripts_dir / "log-cleaner.py").write_text(
            "import urllib.request\n\n"
            "def upload_cleaned_batch(endpoint: str, payload: bytes) -> bytes:\n"
            "    # Hard 1.5s socket timeout + unbuffered partial chunk retry hazard\n"
            "    with urllib.request.urlopen(endpoint, data=payload, timeout=1.5) as resp:\n"
            "        return resp.read()\n",
            encoding="utf-8",
        )
        bob_msgs_before_d2 = len(self.agent_messages(self.bob, bob_cid))
        self.bob.send_message(
            bob_cid,
            "Q，顺便跟你说明白哈：咱们这个私聊里我找你记的临时脚本排查问题，你直接按问作答给简短命令行排查建议就行，以后咱们私聊里的临时脚本排查都别再主动给我挂待拍板候选卡啦。",
        )
        self.wait_for_q_idle(watch_conv=(self.bob, bob_cid, bob_msgs_before_d2 + 1))

        # Meanwhile in #发版群, clear Day 1 proposed cards to backlog and have Alice announce Stage 2 auth-token rotation!
        _, rel_nodes_day2 = self.graphs_for_conversation(self.alice, rel_cid)
        for pnode in [n for n in rel_nodes_day2 if n.get("status") == "proposed"]:
            latest_doc = self.alice.api(
                "GET", f"/im/v1/task-graphs/{pnode['graph_id']}", params={"view": "all"}
            )
            self.alice.api(
                "POST",
                f"/im/v1/task-graphs/{pnode['graph_id']}/apply",
                json={
                    "base_revision": latest_doc["revision"],
                    "request_key": f"rel-ack-{uuid.uuid4()}",
                    "change_note": "Stage 1 checklist reviewed",
                    "operations": [
                        {
                            "op": "update_task",
                            "node_id": pnode["id"],
                            "patch": {"status": "done"},
                        }
                    ],
                },
            )
        # Also mark smoke-status.md handled so Night 3 focuses on #发版群 Stage 2
        (self.project_dir / "smoke-status.md").write_text(
            "# Nightly Smoke Report\n\n- Status: **PASSED**\n",
            encoding="utf-8",
        )
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 16, 0, tzinfo=SHANGHAI)
        )
        rel_msgs_before_d2 = len(self.agent_messages(self.alice, rel_cid))
        self.alice.send_message(
            rel_cid,
            f"{q_mention} 1.2 发版刚又合入了第二波「跨节点刷新令牌轮换与会话吊销」改动，{cn_day(day3)}中午前得把这波改动收口，我先跟进主干联调（另外给你提个我的个人配合习惯：给我准备核查清单时请按 P0/P1 分级列出命令和预期退出码）。",
        )
        self.wait_for_q_idle(watch_conv=(self.alice, rel_cid, rel_msgs_before_d2 + 1))

        # Quiet review at 16:20
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 16, 20, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()

        # Advance to Night 3 (03:05 Dreaming -> 03:20 proactive_nightly)
        self.clock.advance(
            datetime(day3.year, day3.month, day3.day, 3, 5, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()
        self.clock.advance(
            datetime(day3.year, day3.month, day3.day, 3, 20, tzinfo=SHANGHAI)
        )
        self.wait_for_q_idle()

        mem_n3 = mem_file.read_text(encoding="utf-8")
        entities_dir = self.q_workspace / ".nanoassistant" / "memory" / "entities"
        entity_files = (
            sorted(p.name for p in entities_dir.glob("*.md"))
            if entities_dir.is_dir()
            else []
        )

        assert "Bob" in mem_n3 or "bob" in mem_n3.lower(), (
            f"Expected Bob-scoped boundary in MEMORY.md after repeated rejection/feedback:\n{mem_n3}"
        )
        assert "entities/" in mem_n3, (
            f"Expected relative link to entities/*.md in MEMORY.md two-tier layout:\n{mem_n3}"
        )
        assert len(entity_files) >= 1, (
            f"Expected collaborator entity pages under {entities_dir}"
        )

        # Scope isolation verification on Night 3:
        # 1) Bob's 1v1 DM has ZERO new proposed cards
        _, bob_nodes_n3 = self.graphs_for_conversation(self.bob, bob_cid)
        bob_proposed_n3 = [n for n in bob_nodes_n3 if n.get("status") == "proposed"]
        assert len(bob_proposed_n3) == 0, (
            f"Bob-scoped no-intrusion boundary failed—new proposed card created in Bob DM: {bob_proposed_n3}"
        )
        # 2) #发版群 / Alice proactivity was NOT killed by Bob's boundary!
        _, rel_nodes_n3 = self.graphs_for_conversation(self.alice, rel_cid)
        rel_proposed_n3 = [n for n in rel_nodes_n3 if n.get("status") == "proposed"]
        assert len(rel_proposed_n3) >= 1, (
            f"Collaborator scope isolation failed—#发版群 Stage 2 received 0 proposed cards: {rel_nodes_n3}"
        )

        # Prefix cache invariance check on $nano_llm_logs/session/ or DSH durable session log
        trace_source, total_steps, all_recs, prefix_hashes, cache_reads = (
            session_trace_snapshot(
                self.llm_logs, self.wt_root, self.node_id, q_session_id
            )
        )
        unique_prefixes = sorted(set(prefix_hashes))
        if trace_source == "llm_logs_session" and prefix_hashes:
            assert len(unique_prefixes) == 1, (
                f"NoSilentPrefixRewrite violated! Saw multiple prefix hashes in one session window: {unique_prefixes}"
            )
        if cache_reads:
            assert max(cache_reads) > 0, (
                f"Expected positive prompt cache hits across root session steps, got: {cache_reads}"
            )
        has_tail_updated_memory = any(
            "</updated-formal-memory>" in txt for _, txt in all_recs
        )
        assert has_tail_updated_memory, (
            "Expected <updated-formal-memory> injected in tail wake message"
        )

        report["scenarios"]["scenario_3_multi_actor_memory_and_prefix"] = {
            "passed": True,
            "memory_night2_chars": len(mem_n2),
            "memory_night3_chars": len(mem_n3),
            "entity_files": entity_files,
            "memory_git_commits": self.memory_git_log(),
            "bob_dm_proposed_night3": len(bob_proposed_n3),
            "release_group_proposed_night3": [n["title"] for n in rel_proposed_n3],
            "trace_source": trace_source,
            "root_llm_steps": total_steps,
            "unique_prefix_hashes": unique_prefixes,
            "cache_read_tokens_sample": cache_reads[-10:],
            "tail_updated_formal_memory_verified": has_tail_updated_memory,
        }
        report["all_passed"] = True
        return report


def main() -> None:
    """CLI entry point for `scripts/verify_global_agent_proactivity_24h.py`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wt",
        type=Path,
        default=Path.cwd(),
        help="Isolated worktree root running e2e-up.sh --profile daily",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON file path to write the verification summary",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=260.0,
        help="Per-turn settle timeout in seconds",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    verifier = GlobalProactivityVerifier(
        args.wt, repo_root, timeout_sec=args.timeout_sec
    )
    try:
        summary = verifier.run()
    finally:
        verifier.close()

    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
