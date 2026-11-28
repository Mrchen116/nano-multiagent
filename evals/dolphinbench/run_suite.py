#!/usr/bin/env python3
"""Full-suite DolphinBench orchestrator for Nano PA with bounded global concurrency.

Coordinates all requested personas (default: morgan, alex, riley = 13,539 sessions +
600 tests) within a global concurrency budget (default: 6):
  1. Runs persona ingestions in parallel (1 sequential stream per persona -> up to 3 streams).
  2. As soon as any persona seals its memory checkpoint, launches its cold-context
     evaluation arms (`product`, `memory-only`, `search-only`) using the remaining
     global concurrency slots (`max_concurrency - active_ingestions`, scaling from
     4 -> 5 -> 6 workers as sibling ingestions finish).
  3. Continuously updates `<output>/live-status.json` every 30s for live monitoring
     and writes `<output>/suite-report.json` on completion.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any


PERSONA_TOTAL_SESSIONS = {
    "morgan": 3400,
    "alex": 5011,
    "riley": 5128,
}
PERSONA_TOTAL_TESTS = {
    "morgan": 200,
    "alex": 200,
    "riley": 200,
}


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


def collect_persona_progress(
    persona_out: Path, persona: str, arms: list[str]
) -> dict[str, Any]:
    sessions_dir = persona_out / "ingestion" / persona / "sessions"
    ingested = (
        len(list(sessions_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json")))
        if sessions_dir.exists()
        else 0
    )
    sealed = (persona_out / "sealed" / persona / "prepared.json").exists()
    arm_progress: dict[str, Any] = {}
    for arm in arms:
        arm_dir = persona_out / "tests" / arm / persona
        files = sorted(arm_dir.glob("[0-9][0-9][0-9].json")) if arm_dir.exists() else []
        passed = 0
        for f in files:
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
                if doc.get("grade", {}).get("passed"):
                    passed += 1
            except Exception:
                pass
        arm_progress[arm] = {
            "completed": len(files),
            "total": PERSONA_TOTAL_TESTS.get(persona, 200),
            "passed": passed,
            "accuracySoFar": round(passed / len(files), 4) if files else None,
        }
    return {
        "ingestedSessions": ingested,
        "totalSessions": PERSONA_TOTAL_SESSIONS.get(persona, 0),
        "ingestPct": round(
            ingested * 100.0 / max(1, PERSONA_TOTAL_SESSIONS.get(persona, 1)), 2
        ),
        "sealed": sealed,
        "arms": arm_progress,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dolphinbench",
        default=os.environ.get("DOLPHINBENCH_ROOT")
        or str(Path.home() / ".cache/nano-evals/dolphinbench"),
    )
    parser.add_argument("--personas", default="morgan,alex,riley")
    parser.add_argument("--arms", default="product,memory-only,search-only")
    parser.add_argument("--max-concurrency", type=int, default=6)
    parser.add_argument("--output", required=True, help="Suite root output directory.")
    parser.add_argument(
        "--local-state-root",
        default=str(Path.home() / ".cache/nano-evals/dolphinbench-state"),
        help="Local APFS directory for active SQLite/DSH ingestion state.",
    )
    parser.add_argument("--dream-min-interval-days", type=int, default=1)
    parser.add_argument("--model", default="codexOAuth:gpt-6.2-sol")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--judge-model", default="codexOAuth:gpt-6.2-sol@high")
    parser.add_argument("--base-url", default="http://127.0.0.1:4000")
    parser.add_argument(
        "--judge-endpoint", default="http://127.0.0.1:4000/v1/chat/completions"
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    run_py = repo_root / "evals/dolphinbench/run.py"
    suite_out = Path(args.output).resolve()
    suite_out.mkdir(parents=True, exist_ok=True)
    lock_fh = (suite_out / ".suite.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(
            f"Another run_suite.py instance already holds {suite_out / '.suite.lock'}"
        )
    lock_fh.seek(0)
    lock_fh.truncate()
    lock_fh.write(f"{os.getpid()}\n")
    lock_fh.flush()
    logs_dir = suite_out / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    local_state_root = Path(args.local_state_root).resolve() / suite_out.name
    local_state_root.mkdir(parents=True, exist_ok=True)

    personas = [p.strip() for p in args.personas.split(",") if p.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    state_lock = threading.Lock()
    active_ingestions = set(personas)
    persona_states: dict[str, str] = {p: "ingesting" for p in personas}
    persona_errors: dict[str, str] = {}
    stop_monitor = threading.Event()
    started_at = time.time()

    def write_live_status() -> None:
        with state_lock:
            states_copy = dict(persona_states)
            errors_copy = dict(persona_errors)
            active_ing_count = len(active_ingestions)
        progress = {
            p: collect_persona_progress(suite_out / p, p, arms) for p in personas
        }
        state_usage = shutil.disk_usage(str(local_state_root))
        out_usage = shutil.disk_usage(str(suite_out))
        payload = {
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "elapsedSeconds": round(time.time() - started_at, 1),
            "maxConcurrency": args.maxConcurrency
            if hasattr(args, "maxConcurrency")
            else args.max_concurrency,
            "activeIngestions": active_ing_count,
            "personaStates": states_copy,
            "personaErrors": errors_copy,
            "progress": progress,
            "diskFreeGiB": {
                "stateVolume": round(state_usage.free / (1024**3), 2),
                "outputVolume": round(out_usage.free / (1024**3), 2),
            },
        }
        atomic_write_json(suite_out / "live-status.json", payload)

    def monitor_loop() -> None:
        while not stop_monitor.wait(30.0):
            try:
                write_live_status()
            except Exception as exc:
                sys.stderr.write(f"[monitor] status update warning: {exc}\n")

    def run_cmd(cmd: list[str], log_path: Path) -> None:
        with log_path.open("a", encoding="utf-8") as lf:
            lf.write(
                f"\n=== START {datetime.now(timezone.utc).isoformat()} : {' '.join(cmd)} ===\n"
            )
            lf.flush()
            proc = subprocess.Popen(
                cmd, cwd=str(repo_root), stdout=lf, stderr=lf, env=dict(os.environ)
            )
            rc = proc.wait()
            lf.write(
                f"=== EXIT rc={rc} at {datetime.now(timezone.utc).isoformat()} ===\n"
            )
            lf.flush()
            if rc != 0:
                raise RuntimeError(f"Command failed (rc={rc}); see {log_path}")

    test_queue: list[str] = []
    queue_cond = threading.Condition(state_lock)

    def ingest_worker(persona: str) -> None:
        p_out = suite_out / persona
        p_state = local_state_root / persona
        log_file = logs_dir / f"{persona}-ingest.log"
        cmd = [
            sys.executable,
            str(run_py),
            "--dolphinbench",
            args.dolphinbench,
            "--persona",
            persona,
            "--arms",
            args.arms,
            "--phase",
            "ingest",
            "--ingestion-state-dir",
            str(p_state),
            "--dream-min-interval-days",
            str(args.dream_min_interval_days),
            "--model",
            args.model,
            "--reasoning-effort",
            args.reasoning_effort,
            "--judge-model",
            args.judge_model,
            "--base-url",
            args.base_url,
            "--judge-endpoint",
            args.judge_endpoint,
            "--output",
            str(p_out),
        ]
        try:
            sys.stderr.write(
                f"[suite] starting ingestion for {persona} -> {log_file}\n"
            )
            sys.stderr.flush()
            run_cmd(cmd, log_file)
            with queue_cond:
                active_ingestions.discard(persona)
                persona_states[persona] = "queued_for_tests"
                test_queue.append(persona)
                queue_cond.notify_all()
            sys.stderr.write(
                f"[suite] ingestion sealed for {persona}; queued for parallel tests!\n"
            )
            sys.stderr.flush()
        except Exception as exc:
            with queue_cond:
                active_ingestions.discard(persona)
                persona_states[persona] = "failed_ingest"
                persona_errors[persona] = str(exc)
                queue_cond.notify_all()
            sys.stderr.write(f"[suite] ERROR in {persona} ingestion: {exc}\n")
            sys.stderr.flush()

    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    write_live_status()

    ingest_threads = [
        threading.Thread(target=ingest_worker, args=(p,)) for p in personas
    ]
    for t in ingest_threads:
        t.start()

    # Test dispatcher: runs queued persona test suites one persona at a time using
    # all remaining concurrency slots (max_concurrency - len(active_ingestions)),
    # ensuring total concurrent streams <= max_concurrency!
    completed_test_personas = 0
    while True:
        with queue_cond:
            while not test_queue and active_ingestions:
                queue_cond.wait(timeout=10.0)
            if not test_queue and not active_ingestions:
                break
            persona = test_queue.pop(0)
            avail_workers = max(1, args.max_concurrency - len(active_ingestions))
            persona_states[persona] = f"testing(workers={avail_workers})"

        p_out = suite_out / persona
        log_file = logs_dir / f"{persona}-test.log"
        cmd = [
            sys.executable,
            str(run_py),
            "--dolphinbench",
            args.dolphinbench,
            "--persona",
            persona,
            "--arms",
            args.arms,
            "--phase",
            "test",
            "--test-workers",
            str(avail_workers),
            "--dream-min-interval-days",
            str(args.dream_min_interval_days),
            "--model",
            args.model,
            "--reasoning-effort",
            args.reasoning_effort,
            "--judge-model",
            args.judge_model,
            "--base-url",
            args.base_url,
            "--judge-endpoint",
            args.judge_endpoint,
            "--output",
            str(p_out),
        ]
        try:
            sys.stderr.write(
                f"[suite] starting tests for {persona} with --test-workers {avail_workers} -> {log_file}\n"
            )
            sys.stderr.flush()
            run_cmd(cmd, log_file)
            with state_lock:
                persona_states[persona] = "completed"
                completed_test_personas += 1
            sys.stderr.write(f"[suite] completed all tests for {persona}!\n")
            sys.stderr.flush()
        except Exception as exc:
            with state_lock:
                persona_states[persona] = "failed_test"
                persona_errors[persona] = str(exc)
            sys.stderr.write(f"[suite] ERROR in {persona} tests: {exc}\n")
            sys.stderr.flush()

    for t in ingest_threads:
        t.join()

    stop_monitor.set()
    write_live_status()

    # Aggregate suite-report.json across all completed personas
    persona_reports: dict[str, Any] = {}
    for p in personas:
        rep_file = suite_out / p / "report.json"
        if rep_file.exists():
            persona_reports[p] = json.loads(rep_file.read_text(encoding="utf-8"))

    arm_totals: dict[str, Any] = {}
    for arm in arms:
        planned = sum(
            r["arms"][arm]["planned"]
            for r in persona_reports.values()
            if arm in r.get("arms", {})
        )
        passed = sum(
            r["arms"][arm]["passed"]
            for r in persona_reports.values()
            if arm in r.get("arms", {})
        )
        completed = sum(
            r["arms"][arm]["completed"]
            for r in persona_reports.values()
            if arm in r.get("arms", {})
        )
        arm_totals[arm] = {
            "planned": planned,
            "completed": completed,
            "passed": passed,
            "accuracy": round(passed / planned, 4) if planned else None,
        }

    suite_report = {
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "elapsedSeconds": round(time.time() - started_at, 1),
        "personasRequested": personas,
        "personaStates": persona_states,
        "personaErrors": persona_errors,
        "overallArms": arm_totals,
        "personas": persona_reports,
    }
    atomic_write_json(suite_out / "suite-report.json", suite_report)
    print(json.dumps(suite_report, indent=2, ensure_ascii=False))
    if persona_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
