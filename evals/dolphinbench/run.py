#!/usr/bin/env python3
"""Resumable DolphinBench evaluation runner for Nano Personal Assistant.

Supports both fast contiguous history slices (for rapid pipeline & memory
validation) and full 3,400-session persona runs, using DolphinBench's official
dataset authenticator, simulated MCP application servers, and mechanical +
LLM-judge tool-trace graders.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any
from zoneinfo import ZoneInfo

import yaml


PERSONA_TIMEZONES = {
    "morgan": "America/Los_Angeles",
    "alex": "America/New_York",
    "riley": "America/Chicago",
}


def parse_iso_ms(raw: str, tz_name: str = "America/Los_Angeles") -> int:
    if len(raw) == 10:
        year, month, day = (int(x) for x in raw.split("-"))
        dt = datetime(year, month, day, 9, 0, 0, tzinfo=ZoneInfo(tz_name))
        return int(dt.timestamp() * 1000)
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def next_nightly_slot_ms(last_iso: str, tz_name: str = "America/Los_Angeles") -> int:
    """Compute the next 03:05 local slot in the persona's home timezone after the final ingested message."""
    tz = ZoneInfo(tz_name)
    if len(last_iso) == 10:
        year, month, day = (int(x) for x in last_iso.split("-"))
        dt = datetime(year, month, day, 9, 0, 0, tzinfo=tz)
    else:
        dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00")).astimezone(tz)
    next_date = (dt + timedelta(days=1)).date()
    next_slot = datetime(
        next_date.year, next_date.month, next_date.day, 3, 5, 0, tzinfo=tz
    )
    return int(next_slot.timestamp() * 1000)


def atomic_write_json(path: Path, data: Any) -> None:
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    for attempt in range(3):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))


class ServiceBridge:
    """JSON-lines RPC client over the long-lived `evals/dolphinbench/service.ts` worker."""

    def __init__(self, repo_root: Path, env: dict[str, str]) -> None:
        self._proc = subprocess.Popen(
            ["pnpm", "exec", "tsx", str(repo_root / "evals/dolphinbench/service.ts")],
            cwd=str(repo_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
            env=env,
        )
        self._next_id = 1

    def call(self, method: str, params: dict[str, Any]) -> Any:
        assert self._proc.stdin is not None and self._proc.stdout is not None
        req_id = self._next_id
        self._next_id += 1
        self._proc.stdin.write(
            json.dumps({"id": req_id, "method": method, "params": params}) + "\n"
        )
        self._proc.stdin.flush()
        while True:
            line = self._proc.stdout.readline()
            if not line:
                rc = self._proc.poll()
                raise RuntimeError(
                    f"DolphinBench service exited unexpectedly (code={rc}) during {method}"
                )
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                sys.stderr.write(f"[service] {line}\n")
                continue
            if resp.get("id") != req_id:
                continue
            if not resp.get("ok"):
                raise RuntimeError(f"Service {method} failed:\n{resp.get('error')}")
            return resp["result"]

    def close(self) -> None:
        if self._proc.poll() is not None:
            return
        try:
            self.call("close", {})
        except Exception:
            pass
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()


def parse_range(spec: str | None, total: int) -> tuple[int, int]:
    if not spec:
        return 1, total
    lo_s, sep, hi_s = spec.partition(":")
    if not sep:
        raise ValueError(
            "--session-range must have format START:END (1-based inclusive)"
        )
    lo = int(lo_s) if lo_s else 1
    hi = int(hi_s) if hi_s else total
    if lo < 1 or hi > total or lo > hi:
        raise ValueError(f"Invalid --session-range {spec} for 1..{total}")
    return lo, hi


def build_apps_spec(
    dolphin_root: Path,
    run_dir: Path,
    persona: str,
    phase: str,
    item_id: str,
    spec: dict[str, Any],
    persona_release: dict[str, Any],
) -> dict[str, Any]:
    """Mirror DolphinBench `Runner._apps` verbatim (including `repair_server.py`)."""
    workspace = (
        run_dir / "apps" / persona / ("ingestion" if phase == "ingestion" else item_id)
    )
    workspace.mkdir(parents=True, exist_ok=True)
    state = workspace / "state.json"
    baseline = dolphin_root / "mock_mcp/state" / f"{persona}_baseline.json"
    if phase == "tests" or not state.exists():
        value = spec.get("mock_state")
        if value is None:
            value = json.loads(baseline.read_text(encoding="utf-8"))
        atomic_write_json(state, value)
    log = workspace / "calls.jsonl"
    log.write_text("", encoding="utf-8")
    tool_config = workspace / "tools.json"
    scope = spec.get("tools") if phase == "tests" else None
    if scope is None:
        tool_config.unlink(missing_ok=True)
    else:
        atomic_write_json(
            tool_config,
            {"active_tools": [t if isinstance(t, str) else t["name"] for t in scope]},
        )
    entrypoint = dolphin_root / "mock_mcp/server.py"
    manifest_path = dolphin_root / "mock_mcp/manifests" / f"{persona}.yaml"
    extra_env: dict[str, str] = {}
    runtime = persona_release.get("runtime") if phase == "tests" else None
    if runtime is not None:
        entry = runtime["tests"][item_id]
        atomic_write_json(tool_config, entry["tool_config"])
        directory_path = workspace / "directory.json"
        atomic_write_json(directory_path, runtime["workspaces"][entry["workspace"]])
        manifest_path = workspace / "manifest.yaml"
        manifest_path.write_text(
            yaml.safe_dump(runtime["manifest"], sort_keys=False), encoding="utf-8"
        )
        entrypoint = dolphin_root / "mock_mcp/repair_server.py"
        extra_env["DOLPHINBENCH_WORKSPACE_DIRECTORY"] = str(directory_path)
    return {
        "command": sys.executable,
        "args": [str(entrypoint)],
        "env": {
            "PYTHONPATH": str(dolphin_root),
            "DOLPHINBENCH_PERSONA": persona,
            "DOLPHINBENCH_MOCK_MANIFEST": str(manifest_path),
            "DOLPHINBENCH_STATE_PATH": str(state),
            "DOLPHINBENCH_LOG_PATH": str(log),
            "DOLPHINBENCH_TOOL_CONFIG_PATH": str(tool_config),
            "DOLPHINBENCH_RUN_ID": run_dir.name,
            **extra_env,
        },
    }


def select_tests_for_window(
    persona_release: dict[str, Any],
    lo: int,
    hi: int,
    explicit_ids: list[str] | None,
) -> list[dict[str, Any]]:
    tests = persona_release["tests"]
    if explicit_ids:
        wanted = {tid.zfill(3) for tid in explicit_ids}
        selected = [t for t in tests if str(t["id"]).zfill(3) in wanted]
        if len(selected) != len(wanted):
            found = {str(t["id"]).zfill(3) for t in selected}
            raise ValueError(f"Unknown test IDs: {sorted(wanted - found)}")
        return selected
    if lo == 1 and hi == len(persona_release["sessions"]):
        return tests
    facts = persona_release["facts"]
    covered: list[dict[str, Any]] = []
    for test in tests:
        lbf = test.get("load_bearing_facts") or []
        if not lbf:
            continue
        ok = True
        for fid in lbf:
            fact = facts[fid]
            sids = [
                int(s)
                for s in (fact.get("source_session_ids") or [])
                + (fact.get("related_history_session_ids") or [])
            ]
            if not sids or min(sids) < lo or max(sids) > hi:
                ok = False
                break
        if ok:
            covered.append(test)
    return covered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dolphinbench",
        default=os.environ.get("DOLPHINBENCH_ROOT")
        or str(Path.home() / ".cache/nano-evals/dolphinbench"),
        help="Path to the pinned DolphinBench checkout.",
    )
    parser.add_argument(
        "--persona", choices=("morgan", "alex", "riley"), default="morgan"
    )
    parser.add_argument(
        "--session-range",
        default=None,
        help="Optional 1-based inclusive slice START:END (e.g. 1:10 or 3280:3400). Omit for full persona.",
    )
    parser.add_argument(
        "--tests",
        default=None,
        help="Comma-separated test IDs (e.g. 001,019,177). Defaults to all solvable tests in the slice.",
    )
    parser.add_argument(
        "--arms",
        default="product",
        help="Comma-separated test arms: product,search-only,memory-only.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output run directory (resumable; supports external drives).",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:4000")
    parser.add_argument(
        "--api",
        choices=("anthropic-messages", "openai-completions"),
        default="anthropic-messages",
    )
    parser.add_argument("--model", default="codexOAuth:gpt-6.2-sol")
    parser.add_argument("--context-window", type=int, default=475000)
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument(
        "--judge-endpoint", default="http://127.0.0.1:4000/v1/chat/completions"
    )
    parser.add_argument("--judge-model", default="codexOAuth:gpt-6.2-sol@high")
    parser.add_argument("--max-turn-calls", type=int, default=48)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--turn-timeout-ms", type=int, default=420000)
    parser.add_argument(
        "--test-workers",
        type=int,
        default=4,
        help="Parallel isolated test workers after ingestion freeze (default: 4).",
    )
    parser.add_argument(
        "--ingestion-state-dir",
        default=None,
        help="Optional local APFS state directory for live ingestion SQLite/DSH files when --output is on NTFS/exFAT.",
    )
    parser.add_argument(
        "--phase",
        choices=("all", "ingest", "test"),
        default="all",
        help="Execution phase: 'ingest' only prepares & seals memory; 'test' only runs tests against sealed memory; 'all' runs both.",
    )
    parser.add_argument(
        "--max-turn-retries",
        type=int,
        default=3,
        help="Max retries on transient turn/bridge/judge failure (default: 3).",
    )
    parser.add_argument(
        "--dream-min-interval-days",
        type=int,
        default=1,
        help="Minimum calendar days between automatic 03:00 Dreaming runs (default: 1 = every active night).",
    )
    parser.add_argument("--save-raw-requests", action="store_true")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print slice & test plan with zero model calls.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    dolphin_root = Path(args.dolphinbench).resolve()
    if not (dolphin_root / "manifest.json").is_file():
        raise SystemExit(f"DolphinBench checkout not found at {dolphin_root}")

    # Configure DolphinBench judge environment BEFORE importing graders.llm_judge.
    os.environ["DOLPHINBENCH_JUDGE_BACKEND"] = "openai"
    os.environ["DOLPHINBENCH_JUDGE_ENDPOINT"] = args.judge_endpoint
    os.environ["DOLPHINBENCH_JUDGE_MODEL"] = args.judge_model
    os.environ["DOLPHINBENCH_JUDGE_KEY_ENV"] = "NANO_DOLPHINBENCH_API_KEY"
    os.environ.setdefault("NANO_DOLPHINBENCH_API_KEY", "nano-local-proxy")

    sys.path.insert(0, str(dolphin_root))
    from graders.mechanical import grade_tool_trace, load_tool_calls  # type: ignore
    from harness.submission import read_release  # type: ignore

    releases = read_release(dolphin_root)
    persona_release = releases[args.persona]
    all_sessions = persona_release["sessions"]
    lo, hi = parse_range(args.session_range, len(all_sessions))
    selected_sessions = all_sessions[lo - 1 : hi]
    explicit_tests = (
        [x.strip() for x in args.tests.split(",") if x.strip()] if args.tests else None
    )
    selected_tests = select_tests_for_window(persona_release, lo, hi, explicit_tests)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for arm in arms:
        if arm not in ("product", "search-only", "memory-only"):
            raise ValueError(f"Unsupported arm: {arm}")

    active_days = sorted({s["narrative_date"][:10] for s in selected_sessions})
    out_dir = Path(args.output).resolve()
    plan = {
        "benchmark": "dolphinbench",
        "dolphinbenchCommit": subprocess.check_output(
            ["git", "-C", str(dolphin_root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "nanoCommit": subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "persona": args.persona,
        "timeZone": PERSONA_TIMEZONES[args.persona],
        "sessionRange": [lo, hi],
        "sessionCount": len(selected_sessions),
        "activeCalendarDays": len(active_days),
        "dateSpan": [
            selected_sessions[0]["narrative_date"],
            selected_sessions[-1]["narrative_date"],
        ],
        "testIds": [str(t["id"]).zfill(3) for t in selected_tests],
        "testCount": len(selected_tests),
        "arms": arms,
        "candidate": {
            "baseURL": args.base_url,
            "api": args.api,
            "model": args.model,
            "contextWindow": args.context_window,
            "reasoningEffort": args.reasoning_effort,
            "dreamingSchedule": (
                "03:00-local-natural-day"
                if args.dream_min_interval_days <= 1
                else f"03:00-local-every-{args.dream_min_interval_days}-days"
            ),
        },
        "judge": {
            "backend": "openai",
            "endpoint": args.judge_endpoint,
            "model": args.judge_model,
        },
    }
    plan_hash = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()

    if args.plan_only:
        print(
            json.dumps(
                {**plan, "planSha256": plan_hash, "modelCallsStarted": 0},
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        if saved.get("planSha256") != plan_hash:
            raise SystemExit(
                "Run configuration differs from existing manifest.json; choose a new --output directory."
            )
    else:
        atomic_write_json(manifest_path, {**plan, "planSha256": plan_hash})

    limits = {
        "timeoutMs": args.turn_timeout_ms,
        "maxModelCalls": args.max_turn_calls,
        "maxOutputTokens": args.max_output_tokens,
    }

    def _tool_names(raw: Any) -> list[str]:
        if isinstance(raw, dict):
            return [str(k) for k in raw.keys()]
        if isinstance(raw, list):
            return [t if isinstance(t, str) else str(t["name"]) for t in raw]
        return []

    from mock_mcp import (  # type: ignore
        repair_calendar,
        repair_engineering,
        repair_growth,
        repair_operations,
        repair_records,
        repair_server,
        repair_travel,
    )

    repair_classes = (
        repair_server.CandidateSlack,
        repair_calendar.CandidateCalendar,
        repair_records.CandidateRecords,
        repair_travel.CandidateTravel,
        repair_engineering.CandidateEngineering,
        repair_operations.CandidateOperations,
        repair_growth.CandidateGrowth,
    )
    repair_tool_names = {
        attr
        for cls in repair_classes
        for attr in dir(cls)
        if not attr.startswith("_") and callable(getattr(cls, attr, None))
    }

    manifest_doc = yaml.safe_load(
        (dolphin_root / "mock_mcp/manifests" / f"{args.persona}.yaml").read_text(
            encoding="utf-8"
        )
    )
    mcp_tool_names = sorted(
        {
            *_tool_names(manifest_doc.get("tools")),
            *_tool_names(
                ((persona_release.get("runtime") or {}).get("manifest") or {}).get(
                    "tools"
                )
            ),
            *repair_tool_names,
        }
    )

    init_payload = {
        "baseURL": args.base_url,
        "api": args.api,
        "apiKeyEnv": "NANO_DOLPHINBENCH_API_KEY",
        "model": args.model,
        "contextWindow": args.context_window,
        "reasoningEffort": args.reasoning_effort,
        "timeZone": PERSONA_TIMEZONES[args.persona],
        "mcpToolNames": mcp_tool_names,
        "saveRawRequests": args.save_raw_requests,
        "dreamMinIntervalDays": args.dream_min_interval_days,
    }

    bridge = ServiceBridge(repo_root, dict(os.environ))
    extra_bridges: list[ServiceBridge] = []
    bridge_lock = threading.Lock()
    log_lock = threading.Lock()
    worker_local = threading.local()

    def get_worker_bridge() -> ServiceBridge:
        wb = getattr(worker_local, "bridge", None)
        if wb is None:
            wb = ServiceBridge(repo_root, dict(os.environ))
            wb.call("init", init_payload)
            with bridge_lock:
                extra_bridges.append(wb)
            worker_local.bridge = wb
        return wb

    try:
        bridge.call("init", init_payload)

        tz_name = PERSONA_TIMEZONES[args.persona]
        sealed_dir = out_dir / "sealed" / args.persona
        checkpoint_path = sealed_dir / "prepared.json"
        records_dir = out_dir / "ingestion" / args.persona / "sessions"
        records_dir.mkdir(parents=True, exist_ok=True)

        if not checkpoint_path.exists():
            if args.phase == "test":
                raise RuntimeError(
                    f"Cannot run --phase test before sealed checkpoint exists: {checkpoint_path}"
                )
            state_dir = (
                Path(args.ingestion_state_dir).resolve()
                if args.ingestion_state_dir
                else (out_dir / "ingestion" / args.persona / "state")
            )
            first_ts = parse_iso_ms(selected_sessions[0]["narrative_date"], tz_name)
            existing_recs = sorted(
                records_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json")
            )
            if existing_recs:
                last_done = json.loads(existing_recs[-1].read_text(encoding="utf-8"))
                resume_ts = max(first_ts, parse_iso_ms(last_done["date"], tz_name))
            else:
                resume_ts = first_ts
            bridge.call(
                "openIngestion",
                {
                    "stateDir": str(state_dir),
                    "startTimeMs": resume_ts,
                    "limits": limits,
                },
            )

            sessions_since_recycle = 0
            for idx, spec in enumerate(selected_sessions):
                sid = str(spec["id"]).zfill(6)
                rec_path = records_dir / f"{sid}.json"
                if rec_path.exists():
                    continue
                if sessions_since_recycle >= 250:
                    cur_ts = parse_iso_ms(spec["narrative_date"], tz_name)
                    sys.stderr.write(
                        f"[recycle:{args.persona}] recycling runtime process at session={sid}...\n"
                    )
                    sys.stderr.flush()
                    bridge.close()
                    bridge = ServiceBridge(repo_root, dict(os.environ))
                    bridge.call("init", init_payload)
                    bridge.call(
                        "openIngestion",
                        {
                            "stateDir": str(state_dir),
                            "startTimeMs": cur_ts,
                            "limits": limits,
                        },
                    )
                    sessions_since_recycle = 0
                msg = spec["messages"][0].strip()
                date_str = spec["narrative_date"]
                dated_msg = f"[{date_str}] {msg}"
                apps = build_apps_spec(
                    dolphin_root,
                    out_dir,
                    args.persona,
                    "ingestion",
                    sid,
                    spec,
                    persona_release,
                )
                state_json_path = Path(apps["env"]["DOLPHINBENCH_STATE_PATH"])
                state_backup = (
                    state_json_path.read_bytes() if state_json_path.exists() else None
                )

                last_err: Exception | None = None
                record: dict[str, Any] | None = None
                app_calls: list[dict[str, Any]] = []
                for attempt in range(max(1, args.max_turn_retries)):
                    if attempt > 0:
                        delay = min(60, 5 * (3 ** (attempt - 1)))
                        sys.stderr.write(
                            f"  [retry {attempt}/{args.max_turn_retries - 1}] session={sid} after {delay}s ({last_err})\n"
                        )
                        sys.stderr.flush()
                        time.sleep(delay)
                        if state_backup is not None:
                            state_json_path.write_bytes(state_backup)
                        Path(apps["env"]["DOLPHINBENCH_LOG_PATH"]).write_text(
                            "", encoding="utf-8"
                        )
                        bridge.close()
                        bridge = ServiceBridge(repo_root, dict(os.environ))
                        bridge.call("init", init_payload)
                        bridge.call(
                            "openIngestion",
                            {
                                "stateDir": str(state_dir),
                                "startTimeMs": parse_iso_ms(date_str, tz_name),
                                "limits": limits,
                            },
                        )
                        sessions_since_recycle = 0

                    t0 = time.monotonic()
                    sys.stderr.write(
                        f"[ingest:{args.persona} {idx + 1}/{len(selected_sessions)}] session={sid} date={date_str} ...\n"
                    )
                    sys.stderr.flush()
                    try:
                        res = bridge.call(
                            "ingestSession",
                            {
                                "sessionId": sid,
                                "windowIndex": idx,
                                "date": date_str,
                                "timestampMs": parse_iso_ms(date_str, tz_name),
                                "datedMessage": dated_msg,
                                "apps": apps,
                                "limits": limits,
                            },
                        )
                        app_calls = load_tool_calls(
                            Path(apps["env"]["DOLPHINBENCH_LOG_PATH"])
                        )
                        record = {
                            "sessionId": sid,
                            "windowIndex": idx,
                            "date": date_str,
                            "datedMessage": dated_msg,
                            "wallMs": round((time.monotonic() - t0) * 1000, 1),
                            "attempt": attempt + 1,
                            **res,
                            "appCalls": [
                                {k: c[k] for k in ("tool", "args", "result") if k in c}
                                for c in app_calls
                            ],
                        }
                        if res["status"] != "completed":
                            raise RuntimeError(
                                f"Ingestion session {sid} returned status={res['status']} (terminalKind={res.get('terminalKind')})"
                            )
                        last_err = None
                        break
                    except Exception as exc:
                        last_err = exc

                if last_err is not None or record is None:
                    if record is not None:
                        atomic_write_json(records_dir / f"{sid}.failed.json", record)
                    raise RuntimeError(
                        f"Ingestion session {sid} failed after retries: {last_err}"
                    ) from last_err

                atomic_write_json(rec_path, record)
                sessions_since_recycle += 1
                dream_n = len(record.get("dreamingRunsBeforeSession") or [])
                sys.stderr.write(
                    f"  -> [{args.persona}:{sid}] status={record['status']} calls={record['turnUsage']['modelCalls']} "
                    f"app_calls={len(app_calls)} dream_runs={dream_n} ({record['wallMs']:.0f}ms)\n"
                )
                sys.stderr.flush()

            final_night = next_nightly_slot_ms(
                selected_sessions[-1]["narrative_date"], tz_name
            )
            sys.stderr.write(
                f"[freeze:{args.persona}] advancing to final 03:05 slot ({final_night}) and sealing memory...\n"
            )
            sys.stderr.flush()
            freeze_res = bridge.call(
                "freezeIngestion",
                {
                    "persona": args.persona,
                    "sealedDir": str(sealed_dir),
                    "finalNightMs": final_night,
                },
            )
            atomic_write_json(sealed_dir / "freeze-receipt.json", freeze_res)
        else:
            sys.stderr.write(
                f"[ingest:{args.persona}] reusing existing sealed checkpoint at {checkpoint_path}\n"
            )

        # Aggregate ingestion summary
        ingest_records = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(records_dir.glob("*.json"))
        ]
        freeze_receipt = json.loads(
            (sealed_dir / "freeze-receipt.json").read_text(encoding="utf-8")
        )
        total_dream_runs = sum(
            len(r.get("dreamingRunsBeforeSession") or []) for r in ingest_records
        ) + len(freeze_receipt.get("finalDreamRuns") or [])
        ingest_summary = {
            "sessionsCompleted": len(ingest_records),
            "foregroundModelCalls": sum(
                r["turnUsage"]["modelCalls"] for r in ingest_records
            ),
            "foregroundInputTokens": sum(
                r["turnUsage"]["inputTokens"] for r in ingest_records
            ),
            "foregroundOutputTokens": sum(
                r["turnUsage"]["outputTokens"] for r in ingest_records
            ),
            "foregroundCachedTokens": sum(
                r["turnUsage"]["cachedTokens"] for r in ingest_records
            ),
            "dreamingCyclesTriggered": total_dream_runs,
            "appToolCalls": sum(len(r.get("appCalls") or []) for r in ingest_records),
        }

        if args.phase == "ingest":
            ingest_report = {
                "plan": plan,
                "planSha256": plan_hash,
                "phase": "ingest",
                "ingestion": ingest_summary,
                "sealedMemoryDir": str(sealed_dir / "workspace/.nanoassistant/memory"),
            }
            atomic_write_json(out_dir / f"ingest-{args.persona}.json", ingest_report)
            print(json.dumps(ingest_report, indent=2, ensure_ascii=False))
            return

        # Close ingestion bridge before launching parallel test workers if >1 worker requested
        pending_jobs: list[tuple[str, int, dict[str, Any], Path]] = []
        for arm in arms:
            arm_dir = out_dir / "tests" / arm / args.persona
            arm_dir.mkdir(parents=True, exist_ok=True)
            for idx, spec in enumerate(selected_tests):
                tid = str(spec["id"]).zfill(3)
                res_path = arm_dir / f"{tid}.json"
                if not res_path.exists():
                    pending_jobs.append((arm, idx, spec, res_path))

        def execute_one_job(job: tuple[str, int, dict[str, Any], Path]) -> None:
            arm, idx, spec, res_path = job
            tid = str(spec["id"]).zfill(3)
            arm_dir = res_path.parent
            date_str = spec["narrative_anchor_date"]
            dated_msg = f"[{date_str}] {spec['test'].strip()}"

            last_err: Exception | None = None
            for attempt in range(max(1, args.max_turn_retries)):
                if attempt > 0:
                    delay = min(45, 5 * (3 ** (attempt - 1)))
                    with log_lock:
                        sys.stderr.write(
                            f"  [retry {attempt}/{args.max_turn_retries - 1}] test {arm}:{tid} after {delay}s ({last_err})\n"
                        )
                        sys.stderr.flush()
                    time.sleep(delay)
                    old_wb = getattr(worker_local, "bridge", None)
                    if old_wb is not None:
                        old_wb.close()
                        setattr(worker_local, "bridge", None)

                apps = build_apps_spec(
                    dolphin_root,
                    out_dir / "test_apps" / arm,
                    args.persona,
                    "tests",
                    tid,
                    spec,
                    persona_release,
                )
                with log_lock:
                    sys.stderr.write(
                        f"[test:{args.persona}:{arm} {idx + 1}/{len(selected_tests)}] id={tid} ...\n"
                    )
                    sys.stderr.flush()
                t0 = time.monotonic()
                try:
                    wb = (
                        bridge
                        if max(1, args.test_workers) == 1
                        else get_worker_bridge()
                    )
                    exec_res = wb.call(
                        "runTest",
                        {
                            "checkpointPath": str(checkpoint_path),
                            "testDir": str(arm_dir / f"work_{tid}"),
                            "testId": tid,
                            "arm": arm,
                            "date": date_str,
                            "timestampMs": parse_iso_ms(date_str, tz_name),
                            "datedMessage": dated_msg,
                            "apps": apps,
                            "limits": limits,
                        },
                    )
                    if exec_res["status"] != "completed":
                        raise RuntimeError(
                            f"Test {arm}:{tid} returned status={exec_res['status']}"
                        )
                    raw_calls = load_tool_calls(
                        Path(apps["env"]["DOLPHINBENCH_LOG_PATH"])
                    )
                    clean_calls = [
                        {k: c[k] for k in ("tool", "args", "result") if k in c}
                        for c in raw_calls
                    ]
                    grade_cfg = copy.deepcopy(spec["grade"]["config"])
                    grade_cfg["raise_on_judge_error"] = True
                    grade_res = grade_tool_trace(
                        clean_calls, grade_cfg, test_message=spec["test"]
                    )
                    row = {
                        "testId": tid,
                        "arm": arm,
                        "date": date_str,
                        "prompt": spec["test"],
                        "loadBearingFacts": spec.get("load_bearing_facts"),
                        "expectedToolCalls": spec.get("expected_tool_calls"),
                        "status": exec_res["status"],
                        "reply": exec_res["reply"],
                        "usage": exec_res["usage"],
                        "wallMs": round((time.monotonic() - t0) * 1000, 1),
                        "attempt": attempt + 1,
                        "appCalls": clean_calls,
                        "grade": {
                            "passed": bool(grade_res["passed"]),
                            "score": float(grade_res["score"]),
                            "passedChecks": grade_res.get("passed_checks"),
                            "totalChecks": grade_res.get("total_checks"),
                            "details": grade_res.get("details"),
                        },
                    }
                    atomic_write_json(res_path, row)
                    # Remove per-test 726KB mutable state copy after grading; calls.jsonl & row JSON retain full evidence.
                    Path(apps["env"]["DOLPHINBENCH_STATE_PATH"]).unlink(missing_ok=True)
                    work_tmp = arm_dir / f"work_{tid}"
                    if work_tmp.exists():
                        shutil.rmtree(work_tmp, ignore_errors=True)
                    verdict = "PASS" if row["grade"]["passed"] else "FAIL"
                    with log_lock:
                        sys.stderr.write(
                            f"  -> [{args.persona}:{arm}:{tid}] {verdict} ({row['grade']['passedChecks']}/{row['grade']['totalChecks']} checks) "
                            f"app_calls={[c.get('tool') for c in clean_calls]} ({row['wallMs']:.0f}ms)\n"
                        )
                        sys.stderr.flush()
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    work_tmp = arm_dir / f"work_{tid}"
                    if work_tmp.exists():
                        shutil.rmtree(work_tmp, ignore_errors=True)

            if last_err is not None:
                raise RuntimeError(
                    f"Test {args.persona}:{arm}:{tid} failed after retries: {last_err}"
                ) from last_err

        workers = max(1, min(args.test_workers, len(pending_jobs) or 1))
        if pending_jobs:
            if workers == 1:
                for job in pending_jobs:
                    execute_one_job(job)
            else:
                sys.stderr.write(
                    f"[tests] running {len(pending_jobs)} test task(s) with {workers} parallel workers...\n"
                )
                sys.stderr.flush()
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [
                        pool.submit(execute_one_job, job) for job in pending_jobs
                    ]
                    for fut in as_completed(futures):
                        fut.result()

        arm_summaries: dict[str, Any] = {}
        for arm in arms:
            arm_dir = out_dir / "tests" / arm / args.persona
            results = [
                json.loads(
                    (arm_dir / f"{str(spec['id']).zfill(3)}.json").read_text(
                        encoding="utf-8"
                    )
                )
                for spec in selected_tests
            ]
            passed = sum(1 for r in results if r["grade"]["passed"])
            arm_summaries[arm] = {
                "planned": len(selected_tests),
                "completed": sum(1 for r in results if r["status"] == "completed"),
                "passed": passed,
                "accuracy": round(passed / len(selected_tests), 4)
                if selected_tests
                else None,
                "modelCalls": sum(r["usage"]["modelCalls"] for r in results),
                "inputTokens": sum(r["usage"]["inputTokens"] for r in results),
                "outputTokens": sum(r["usage"]["outputTokens"] for r in results),
                "cachedTokens": sum(r["usage"]["cachedTokens"] for r in results),
                "medianWallMs": sorted(r["wallMs"] for r in results)[len(results) // 2]
                if results
                else None,
                "perTest": [
                    {
                        "testId": r["testId"],
                        "passed": r["grade"]["passed"],
                        "checks": f"{r['grade']['passedChecks']}/{r['grade']['totalChecks']}",
                        "toolsCalled": [c.get("tool") for c in r["appCalls"]],
                        "modelCalls": r["usage"]["modelCalls"],
                    }
                    for r in results
                ],
            }

        report = {
            "plan": plan,
            "planSha256": plan_hash,
            "ingestion": ingest_summary,
            "arms": arm_summaries,
            "sealedMemoryDir": str(sealed_dir / "workspace/.nanoassistant/memory"),
        }
        atomic_write_json(out_dir / "report.json", report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        for wb in extra_bridges:
            wb.close()
        bridge.close()


if __name__ == "__main__":
    main()
