#!/usr/bin/env python3
"""Repeatable 5-checkpoint 24h live-LLM proactivity acceptance runner.

Drives an isolated `./scripts/e2e-up.sh --profile daily` stack over
`NANO_E2E_LOGICAL_CLOCK_SOCKET` using natural human dialogue (zero tool names,
status enum tokens, or prompt-engineering hints) and verifies both positive
proactive value and negative restraint boundaries across IM HTTP state,
workspace memory/files, and `$nano_llm_logs/session/` wire captures.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
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
FAMILY_KEYWORDS = ("老人", "血压", "陪诊", "长辈", "父母")


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
        self, method: str, params: dict[str, Any] | None = None, timeout: float = 240.0
    ) -> dict[str, Any]:
        """Execute one JSON-RPC call over the Unix domain socket.

        Args:
            method: RPC method (`clock.status` or `clock.advance`).
            params: Optional JSON object parameters.
            timeout: Socket read timeout in seconds.

        Returns:
            Decoded `result` payload dictionary.
        """
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
            timeout=300.0,
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


def session_req_files(llm_logs: Path, session_id: str) -> list[Path]:
    """Return sorted request JSON files captured for `session_id`."""
    session_root = llm_logs / "session"
    if not session_root.is_dir():
        return []
    files: list[Path] = []
    for folder in session_root.glob(f"*_{session_id}"):
        files.extend(folder.glob("*-req-*.json"))
    return sorted(files, key=lambda p: p.name)


def session_res_files(llm_logs: Path, session_id: str) -> list[Path]:
    """Return sorted response files captured for `session_id`."""
    session_root = llm_logs / "session"
    if not session_root.is_dir():
        return []
    files: list[Path] = []
    for folder in session_root.glob(f"*_{session_id}"):
        files.extend(folder.glob("*-res-*.json"))
        files.extend(folder.glob("*-res-*.txt"))
    return sorted(files, key=lambda p: p.name)


def read_ports_env(wt_root: Path) -> dict[str, str]:
    """Parse `export KEY=VALUE` pairs from `.e2e-ports.env`."""
    env_map: dict[str, str] = {}
    for line in (wt_root / ".e2e-ports.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export ") and "=" in line:
            key, value = line[len("export ") :].split("=", 1)
            env_map[key.strip()] = value.strip()
    return env_map


class ProactivityVerifier:
    """Executes all 5 checkpoints of the 24h PA proactivity acceptance suite."""

    def __init__(
        self, wt_root: Path, repo_root: Path, timeout_sec: float = 240.0
    ) -> None:
        """Bind HTTP client, logical clock socket, workspace paths, and LLM logs."""
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

        self.pa_id: str = self.daily["personal"]["agent_id"]
        self.pa_conv_id: str = self.daily["personal"]["conversation_id"]
        self.group_id: str = self.daily["group"]["id"]
        self.pa_workspace = (
            Path(self.gateway_cfg["node"]["workspace_base"]) / self.pa_id
        )

        self.http = httpx.Client(
            base_url=self.ports["IM_URL"], trust_env=False, timeout=30.0
        )
        login = self.http.post(
            "/im/v1/auth/login",
            json={
                "username": "nano",
                "password": os.environ.get("ADMIN_PASSWORD", "nano1234"),
            },
        )
        login.raise_for_status()
        auth = login.json()
        self.user_id: str = auth["user"]["id"]
        self.http.headers["Authorization"] = f"Bearer {auth['access_token']}"

    def close(self) -> None:
        """Close underlying HTTP client."""
        self.http.close()

    def api(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform an authenticated IM HTTP request and return parsed JSON."""
        resp = self.http.request(method, path, **kwargs)
        if resp.is_error:
            raise RuntimeError(
                f"IM {method} {path} -> HTTP {resp.status_code}: {resp.text[:600]}"
            )
        return resp.json() if resp.content else None

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """Return chronological messages in `conversation_id`."""
        data = self.api(
            "GET",
            f"/im/v1/conversations/{conversation_id}/messages",
            params={"limit": 100},
        )
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        return sorted(
            items, key=lambda m: (m.get("created_at") or "", m.get("id") or "")
        )

    def agent_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """Return completed assistant chat messages (excluding system notices)."""
        return [
            m
            for m in self.list_messages(conversation_id)
            if m.get("sender_type") == "agent" and m.get("system_notice") is None
        ]

    def send_user_message(self, conversation_id: str, text: str) -> dict[str, Any]:
        """Post a natural human message with Asia/Shanghai timezone."""
        return self.api(
            "POST",
            f"/im/v1/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"content": text, "attachments": [], "timezone": "Asia/Shanghai"},
        )

    def wait_for_pa_idle(
        self, *, min_turns: int | None = None, min_agent_msgs: int | None = None
    ) -> dict[str, Any]:
        """Poll PA Work view and DM until turns/messages settle to `idle`."""
        deadline = time.monotonic() + self.timeout_sec
        stable_polls = 0
        while time.monotonic() < deadline:
            work = self.api(
                "GET",
                f"/im/v1/agents/{self.pa_id}/work",
                params={"view": "summary", "limit": 20},
            )
            turns = work.get("turns") or []
            state = work.get("state")
            any_running = state == "running" or any(
                t.get("status") in ("running", "waiting_permission") for t in turns
            )
            msgs = self.agent_messages(self.pa_conv_id)
            all_msg_done = all(
                m.get("delivery_status") in ("completed", "failed") for m in msgs
            )
            turns_ok = min_turns is None or len(turns) >= min_turns
            msgs_ok = min_agent_msgs is None or len(msgs) >= min_agent_msgs
            if not any_running and all_msg_done and turns_ok and msgs_ok:
                stable_polls += 1
                if stable_polls >= 3:
                    return work
            else:
                stable_polls = 0
            time.sleep(1.0)
        raise TimeoutError(
            f"PA {self.pa_id} did not settle to idle within {self.timeout_sec}s"
        )

    def all_graphs_and_nodes(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Fetch every accessible task graph document and flatten all nodes."""
        listing = self.api("GET", "/im/v1/task-graphs", params={"limit": 50})
        graphs: list[dict[str, Any]] = []
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in listing.get("items", []):
            gid = item["graph_id"]
            if gid in seen:
                continue
            seen.add(gid)
            doc = self.api("GET", f"/im/v1/task-graphs/{gid}")
            graphs.append(doc)
            for node in doc.get("nodes", []):
                nodes.append({"graph_id": gid, "revision": doc["revision"], **node})
        return graphs, nodes

    def cron_jobs(self) -> list[dict[str, Any]]:
        """Return active and inactive cron jobs for PA."""
        res = self.api("GET", f"/im/v1/agents/{self.pa_id}/cron/jobs")
        return res.get("jobs", res) if isinstance(res, dict) else res

    def run(self) -> dict[str, Any]:
        """Execute all 5 checkpoints and return a structured verification report."""
        self.api("PATCH", "/im/v1/me/timezone", json={"timezone": "Asia/Shanghai"})
        now_ms = self.clock.status()["nowMs"]
        now_sh = datetime.fromtimestamp(now_ms / 1000.0, tz=SHANGHAI)
        base_date = now_sh.date()
        t_warmup = datetime(
            base_date.year, base_date.month, base_date.day, 21, 30, tzinfo=SHANGHAI
        )
        if t_warmup.timestamp() * 1000 <= now_ms + 60_000:
            base_date = base_date + timedelta(days=1)
            t_warmup = datetime(
                base_date.year, base_date.month, base_date.day, 21, 30, tzinfo=SHANGHAI
            )

        day1 = base_date + timedelta(days=1)
        day2 = base_date + timedelta(days=2)
        day3 = base_date + timedelta(days=3)
        day4 = base_date + timedelta(days=4)
        cn_day = lambda d: f"{d.month}月{d.day}日"

        report: dict[str, Any] = {
            "pa_agent_id": self.pa_id,
            "pa_conversation_id": self.pa_conv_id,
            "group_id": self.group_id,
            "base_date_shanghai": str(base_date),
            "checkpoints": {},
        }

        # Warmup at 21:30: establish natural daily 09:10 morning check-in rhythm.
        self.clock.advance(t_warmup)
        before_msgs = len(self.agent_messages(self.pa_conv_id))
        self.send_user_message(
            self.pa_conv_id,
            "嗨，咱们约定个日常节奏吧：每天早上 9 点 10 分叫我一声，陪我对齐一下当天我自己想重点推进的一两件事；平时晚上睡前我也习惯跟你聊聊当天的进展和想法。",
        )
        work0 = self.wait_for_pa_idle(min_agent_msgs=before_msgs + 1)
        pa_session_id: str = work0["main_session_id"]
        report["pa_main_session_id"] = pa_session_id
        self.clock.advance(
            datetime(
                base_date.year, base_date.month, base_date.day, 21, 50, tzinfo=SHANGHAI
            )
        )
        self.wait_for_pa_idle()

        # ── Checkpoint 1: 23:00 diary + 23:15 quiet accounting + 00:05 reschedule + 00:20 quiet accounting ──
        t_2300 = datetime(
            base_date.year, base_date.month, base_date.day, 23, 0, tzinfo=SHANGHAI
        )
        self.clock.advance(t_2300)
        before_2300 = len(self.agent_messages(self.pa_conv_id))
        self.send_user_message(
            self.pa_conv_id,
            f"睡前跟你记一笔今天的复盘：把 Nano 打磨成熟并推出去这件事，我定下来在{cn_day(day3)}下午六点前把 3 分钟产品演示视频做出来（先敲定三个核心演示镜头，再完成录屏剪辑），到那天上午十一点提醒我看下进度就行。"
            "另外家里老人这两天换季血压有点起伏、周末还得跟家里人商量陪诊安排，这些家里的事你心里留个印象当背景就好，以后千万别主动拿家里的事给我列任务或者出主意。"
            "刚才刷手机还闪过一个念头：以后做个帮独立创作者打理多平台内容的自媒体小助手会不会有戏？还没想好做不做，先睡啦，晚安！",
        )
        self.wait_for_pa_idle(min_agent_msgs=before_2300 + 1)
        msgs_after_2300_reply = len(self.agent_messages(self.pa_conv_id))

        t_2315 = datetime(
            base_date.year, base_date.month, base_date.day, 23, 15, tzinfo=SHANGHAI
        )
        self.clock.advance(t_2315)
        self.wait_for_pa_idle()
        msgs_at_2315 = len(self.agent_messages(self.pa_conv_id))
        graphs_2315, nodes_2315 = self.all_graphs_and_nodes()
        proposed_2315 = [n for n in nodes_2315 if n.get("status") == "proposed"]
        family_2315 = [
            n
            for n in nodes_2315
            if any(
                k in (n.get("title", "") + n.get("description", ""))
                for k in FAMILY_KEYWORDS
            )
        ]
        assert msgs_at_2315 == msgs_after_2300_reply, (
            f"proactive_review at 23:15 sent unexpected chat message ({msgs_at_2315} vs {msgs_after_2300_reply})"
        )
        assert len(proposed_2315) == 0, (
            f"23:15 lightweight review must not create proposed cards: {proposed_2315}"
        )
        assert len(family_2315) == 0, (
            f"Family boundary violated at 23:15: {family_2315}"
        )
        assert len(nodes_2315) >= 1, (
            "23:15 accounting should record the explicit Nano Demo commitment"
        )

        t_0005 = datetime(day1.year, day1.month, day1.day, 0, 5, tzinfo=SHANGHAI)
        self.clock.advance(t_0005)
        before_0005 = len(self.agent_messages(self.pa_conv_id))
        self.send_user_message(
            self.pa_conv_id,
            f"躺下刚扫了眼日程，{cn_day(day3)}下午临时塞了个推不掉的外部评审，3 分钟演示视频改到{cn_day(day4)}下午六点前交卷吧，看进度的提醒也顺延一天，这回真睡了～",
        )
        self.wait_for_pa_idle(min_agent_msgs=before_0005 + 1)
        msgs_after_0005_reply = len(self.agent_messages(self.pa_conv_id))

        t_0020 = datetime(day1.year, day1.month, day1.day, 0, 20, tzinfo=SHANGHAI)
        self.clock.advance(t_0020)
        self.wait_for_pa_idle()
        msgs_at_0020 = len(self.agent_messages(self.pa_conv_id))
        graphs_0020, nodes_0020 = self.all_graphs_and_nodes()
        proposed_0020 = [n for n in nodes_0020 if n.get("status") == "proposed"]
        assert msgs_at_0020 == msgs_after_0005_reply, (
            "00:20 proactive_review must remain silent"
        )
        assert len(proposed_0020) == 0, (
            f"00:20 lightweight review must keep proposed=0: {proposed_0020}"
        )
        assert len(graphs_0020) <= len(graphs_2315) + 1, (
            "00:05 reschedule must update existing Demo goal rather than proliferating graphs"
        )

        report["checkpoints"]["checkpoint_1_quiet_accounting"] = {
            "passed": True,
            "graphs_at_2315": len(graphs_2315),
            "nodes_at_2315": len(nodes_2315),
            "proposed_at_2315": len(proposed_2315),
            "proposed_at_0020": len(proposed_0020),
            "silent_after_2315_and_0020": True,
        }

        # ── Checkpoint 2: 03:05 Dreaming + 03:15 proactive_nightly boundary & substantive prep ──
        msgs_before_night = len(self.agent_messages(self.pa_conv_id))
        t_0305 = datetime(day1.year, day1.month, day1.day, 3, 5, tzinfo=SHANGHAI)
        self.clock.advance(t_0305)
        self.wait_for_pa_idle()
        t_0315 = datetime(day1.year, day1.month, day1.day, 3, 15, tzinfo=SHANGHAI)
        self.clock.advance(t_0315)
        self.wait_for_pa_idle()

        memory_file = self.pa_workspace / ".nanoassistant" / "memory" / "MEMORY.md"
        assert memory_file.is_file(), f"Expected Dreaming to maintain {memory_file}"
        memory_text = memory_file.read_text(encoding="utf-8")
        assert len(memory_text.strip()) > 20, (
            "MEMORY.md should contain consolidated owner context and boundaries"
        )

        msgs_after_night = len(self.agent_messages(self.pa_conv_id))
        assert msgs_after_night == msgs_before_night, (
            "Nightly Dreaming + proactive_nightly must send 0 outbound chat messages during 03:00-06:00"
        )

        _, nodes_night = self.all_graphs_and_nodes()
        proposed_night = [n for n in nodes_night if n.get("status") == "proposed"]
        family_night = [
            n
            for n in nodes_night
            if any(
                k in (n.get("title", "") + n.get("description", ""))
                for k in FAMILY_KEYWORDS
            )
        ]
        assert len(family_night) == 0, (
            f"Family non-proposal boundary violated during nightly pass: {family_night}"
        )
        assert 1 <= len(proposed_night) <= 3, (
            f"Expected 1-3 high-signal proposed cards after nightly planning, got {len(proposed_night)}: {proposed_night}"
        )
        for card in proposed_night:
            prop = card.get("proposal") or {}
            assert prop.get("rationale") and prop.get("on_approve"), (
                f"Proposed card missing rationale/on_approve: {card}"
            )

        reqs_night = session_req_files(self.llm_logs, pa_session_id)
        nightly_reqs = [
            p
            for p in reqs_night
            if "<proactive-nightly-wake"
            in p.read_text(encoding="utf-8", errors="ignore")
        ]
        assert len(nightly_reqs) >= 1, (
            f"Expected <proactive-nightly-wake> in llm_logs for session {pa_session_id}"
        )
        nightly_payload_text = nightly_reqs[-1].read_text(
            encoding="utf-8", errors="ignore"
        )
        has_updated_memory_block = "<updated-formal-memory>" in nightly_payload_text

        report["checkpoints"]["checkpoint_2_dreaming_and_nightly"] = {
            "passed": True,
            "memory_chars": len(memory_text),
            "updated_formal_memory_inlined": has_updated_memory_block,
            "proposed_count": len(proposed_night),
            "proposed_titles": [c["title"] for c in proposed_night],
            "family_cards": len(family_night),
            "night_outbound_messages": msgs_after_night - msgs_before_night,
            "nightly_req_file": nightly_reqs[-1].name,
        }

        # ── Checkpoint 3①: 09:10 Morning combined brief + open alignment ──
        msgs_before_morning = len(self.agent_messages(self.pa_conv_id))
        t_0912 = datetime(day1.year, day1.month, day1.day, 9, 12, tzinfo=SHANGHAI)
        self.clock.advance(t_0912)
        self.wait_for_pa_idle(min_agent_msgs=msgs_before_morning + 1)
        morning_msgs = self.agent_messages(self.pa_conv_id)[msgs_before_morning:]
        assert len(morning_msgs) == 1, (
            f"Expected single combined morning brief message, got {len(morning_msgs)}"
        )
        morning_msg = morning_msgs[0]
        assert len((morning_msg.get("content") or "").strip()) > 30, (
            "Morning brief must contain substantive content"
        )

        report["checkpoints"]["checkpoint_3a_morning_combined_brief"] = {
            "passed": True,
            "morning_message_count": len(morning_msgs),
            "morning_message_id": morning_msg["id"],
            "task_cards_count": len(morning_msg.get("task_cards") or []),
        }

        # ── Checkpoint 4: Pre-schedule observation sync eliminates stale nudge ──
        t_1000 = datetime(day1.year, day1.month, day1.day, 10, 0, tzinfo=SHANGHAI)
        self.clock.advance(t_1000)
        before_1000 = len(self.agent_messages(self.pa_conv_id))
        self.send_user_message(
            self.pa_conv_id,
            "今天上午我先去团队群里把 3 分钟演示视频的三个镜头敲定并录出第一版，你今天中午 12 点半帮我核对一下这项进展就行。",
        )
        self.wait_for_pa_idle(min_agent_msgs=before_1000 + 1)
        self.clock.advance(
            datetime(day1.year, day1.month, day1.day, 10, 15, tzinfo=SHANGHAI)
        )
        self.wait_for_pa_idle()

        # At 12:25 (only 5m before 12:30, inside the 10m group batch window), owner announces completion in the observed group!
        t_1225 = datetime(day1.year, day1.month, day1.day, 12, 25, tzinfo=SHANGHAI)
        self.clock.advance(t_1225)
        self.send_user_message(
            self.group_id,
            "跟大家同步个好消息：Nano 3 分钟演示视频的三个镜头我刚全部拍板定稿，而且第一版录屏初剪也已经录完保存好啦！",
        )
        time.sleep(2.0)
        reqs_before_1230 = len(session_req_files(self.llm_logs, pa_session_id))
        t_1232 = datetime(day1.year, day1.month, day1.day, 12, 32, tzinfo=SHANGHAI)
        self.clock.advance(t_1232)
        self.wait_for_pa_idle()
        reqs_after_1230 = session_req_files(self.llm_logs, pa_session_id)[
            reqs_before_1230:
        ]
        synced_in_logs = any(
            "Fresh observation sync completed before this scheduled check"
            in p.read_text(encoding="utf-8", errors="ignore")
            for p in reqs_after_1230
        )
        assert synced_in_logs, (
            "Expected schedule pre-step observation sync in llm_logs before 12:30 check"
        )

        report["checkpoints"]["checkpoint_4_pre_schedule_observation_sync"] = {
            "passed": True,
            "sync_banner_verified_in_llm_logs": synced_in_logs,
            "scheduled_turn_requests": len(reqs_after_1230),
        }

        # ── Checkpoint 5: Approve proposed card -> single-shot doing_wake with North-Star context -> stays idle ──
        _, nodes_before_approve = self.all_graphs_and_nodes()
        target_proposed = next(
            (n for n in nodes_before_approve if n.get("status") == "proposed"), None
        )
        assert target_proposed is not None, (
            "Expected at least one proposed card remaining to approve in Checkpoint 5"
        )
        ops: list[dict[str, Any]] = []
        assignee = target_proposed.get("assignee")
        if (
            not assignee
            or assignee.get("type") != "agent"
            or assignee.get("id") != self.pa_id
        ):
            ops.append(
                {
                    "op": "set_assignee",
                    "node_id": target_proposed["id"],
                    "assignee": {"type": "agent", "id": self.pa_id},
                }
            )
        ops.append({"op": "approve_task", "node_id": target_proposed["id"]})
        reqs_before_approve = len(session_req_files(self.llm_logs, pa_session_id))
        work_before_approve = self.api(
            "GET",
            f"/im/v1/agents/{self.pa_id}/work",
            params={"view": "summary", "limit": 50},
        )
        turns_before_approve = len(work_before_approve.get("turns") or [])

        self.api(
            "POST",
            f"/im/v1/task-graphs/{target_proposed['graph_id']}/apply",
            json={
                "base_revision": target_proposed["revision"],
                "request_key": f"approve-{uuid.uuid4()}",
                "change_note": "Approve proposed card for execution",
                "operations": ops,
            },
        )
        self.wait_for_pa_idle(min_turns=turns_before_approve + 1)
        reqs_at_idle = len(session_req_files(self.llm_logs, pa_session_id))
        assert reqs_at_idle > reqs_before_approve, (
            "Approving PA-assigned proposed card must trigger single-shot doing_wake"
        )
        approve_turn_reqs = session_req_files(self.llm_logs, pa_session_id)[
            reqs_before_approve:
        ]
        has_task_context = any(
            "Current Task context:" in p.read_text(encoding="utf-8", errors="ignore")
            for p in approve_turn_reqs
        )
        assert has_task_context, (
            "Single-shot doing_wake must inject Current Task context with North-Star metadata"
        )

        # Wait 6s wall-clock to prove zero repeated 256-turn idle continuation loop!
        time.sleep(6.0)
        reqs_after_hold = len(session_req_files(self.llm_logs, pa_session_id))
        assert reqs_after_hold == reqs_at_idle, (
            f"Session spun extra unprompted turns after settling idle ({reqs_after_hold} vs {reqs_at_idle})"
        )

        report["checkpoints"]["checkpoint_5_single_shot_doing_and_idle"] = {
            "passed": True,
            "approved_graph_id": target_proposed["graph_id"],
            "approved_node_id": target_proposed["id"],
            "wake_requests": reqs_at_idle - reqs_before_approve,
            "extra_requests_after_6s_idle": reqs_after_hold - reqs_at_idle,
        }

        # ── Checkpoint 3②: Control Night (no recurring morning cron + casual small talk -> multi-stop 23:15 -> 03:05 -> 03:15 -> 09:30) ──
        for job in self.cron_jobs():
            if job.get("enabled"):
                self.api("DELETE", f"/im/v1/agents/{self.pa_id}/cron/jobs/{job['id']}")
        _, current_nodes = self.all_graphs_and_nodes()
        for pnode in [n for n in current_nodes if n.get("status") == "proposed"]:
            latest_doc = self.api("GET", f"/im/v1/task-graphs/{pnode['graph_id']}")
            self.api(
                "POST",
                f"/im/v1/task-graphs/{pnode['graph_id']}/apply",
                json={
                    "base_revision": latest_doc["revision"],
                    "request_key": f"clean-{uuid.uuid4()}",
                    "change_note": "Clear earlier proposed cards before control night",
                    "operations": [
                        {
                            "op": "update_task",
                            "node_id": pnode["id"],
                            "patch": {"status": "backlog"},
                        }
                    ],
                },
            )
        self.wait_for_pa_idle()

        t_day1_2250 = datetime(day1.year, day1.month, day1.day, 22, 50, tzinfo=SHANGHAI)
        self.clock.advance(t_day1_2250)
        before_casual = len(self.agent_messages(self.pa_conv_id))
        self.send_user_message(
            self.pa_conv_id,
            "今晚没什么正事，刚下楼散了会儿步喝了杯热牛奶，准备早点睡啦，晚安！",
        )
        self.wait_for_pa_idle(min_agent_msgs=before_casual + 1)
        msgs_before_control = len(self.agent_messages(self.pa_conv_id))
        reqs_before_control_night = len(session_req_files(self.llm_logs, pa_session_id))

        # Stop 1: 23:15 (proactive_review)
        self.clock.advance(
            datetime(day1.year, day1.month, day1.day, 23, 15, tzinfo=SHANGHAI)
        )
        self.wait_for_pa_idle()
        # Stop 2: 03:05 (Dreaming + proactive_nightly)
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 3, 5, tzinfo=SHANGHAI)
        )
        self.wait_for_pa_idle()
        # Stop 3: 03:15 (verify proactive_nightly ran in llm_logs and produced 0 proposed cards & 0 morning alarms)
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 3, 15, tzinfo=SHANGHAI)
        )
        self.wait_for_pa_idle()

        control_night_reqs = session_req_files(self.llm_logs, pa_session_id)[
            reqs_before_control_night:
        ]
        control_nightly_ran = any(
            f'<proactive-nightly-wake local_time="{day2.isoformat()}T03:'
            in p.read_text(encoding="utf-8", errors="ignore")
            for p in control_night_reqs
        )
        assert control_nightly_ran, (
            "Control night must actually execute proactive_nightly at 03:05/03:15 rather than skipping it"
        )
        _, nodes_after_control_night = self.all_graphs_and_nodes()
        proposed_control = [
            n for n in nodes_after_control_night if n.get("status") == "proposed"
        ]
        active_jobs_control = [j for j in self.cron_jobs() if j.get("enabled")]
        assert len(proposed_control) == 0, (
            f"Control night with casual small talk must create 0 proposed cards, got {proposed_control}"
        )
        assert len(active_jobs_control) == 0, (
            f"Control night with zero new value must create 0 morning alarms, got {active_jobs_control}"
        )
        assert len(self.agent_messages(self.pa_conv_id)) == msgs_before_control, (
            "Control night must send 0 nighttime messages"
        )

        # Stop 4: 09:30 (verify 0 morning wake & 0 hollow morning brief)
        reqs_at_0315 = len(session_req_files(self.llm_logs, pa_session_id))
        self.clock.advance(
            datetime(day2.year, day2.month, day2.day, 9, 30, tzinfo=SHANGHAI)
        )
        self.wait_for_pa_idle()
        reqs_at_0930 = len(session_req_files(self.llm_logs, pa_session_id))
        assert reqs_at_0930 == reqs_at_0315, (
            f"Control morning must have 0 LLM wakes ({reqs_at_0930} vs {reqs_at_0315})"
        )
        assert len(self.agent_messages(self.pa_conv_id)) == msgs_before_control, (
            "Control morning must send 0 hollow morning briefs"
        )

        report["checkpoints"]["checkpoint_3b_zero_value_control_night"] = {
            "passed": True,
            "proactive_nightly_verified_in_llm_logs": control_nightly_ran,
            "new_proposed_cards": len(proposed_control),
            "active_morning_schedules": len(active_jobs_control),
            "morning_wakes_between_0315_and_0930": reqs_at_0930 - reqs_at_0315,
            "hollow_morning_messages": len(self.agent_messages(self.pa_conv_id))
            - msgs_before_control,
        }
        report["all_passed"] = True
        return report


def main() -> None:
    """CLI entry point for `scripts/verify_pa_proactivity_24h.py`."""
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
        default=240.0,
        help="Per-turn settle timeout in seconds",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    verifier = ProactivityVerifier(args.wt, repo_root, timeout_sec=args.timeout_sec)
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
