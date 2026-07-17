"""Cron run history materialization, concurrency, and restart behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from personal_assistant.scheduler.cron_execution_service import (
    CronRunRecord,
    CronRunsStore,
)


def _record(index: int, *, job_id: str = "job-a") -> CronRunRecord:
    return CronRunRecord(
        request_id=f"req-{index:03d}",
        job_id=job_id,
        trigger="manual" if index % 2 else "scheduled",
        status="accepted",
        accepted_at=f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}+00:00",
    )


def test_append_update_and_restart_reconstruct_latest_state(tmp_path: Path) -> None:
    """A new owner must reconstruct the same latest lifecycle records from JSONL."""

    store = CronRunsStore(workspace_root=tmp_path)
    store.append(_record(1))
    store.update_status(
        "req-001",
        "completed",
        finished_at="2026-01-01T00:02:00+00:00",
        result_summary="done",
    )

    live = store.list_by_job("job-a")
    restarted = CronRunsStore(workspace_root=tmp_path).list_by_job("job-a")

    assert live == restarted
    assert restarted[0].status == "completed"
    assert restarted[0].result_summary == "done"


def test_repeated_updates_materialize_runs_file_once_per_owner(
    tmp_path: Path, monkeypatch
) -> None:
    """Status transitions after first use must not replay the growing JSONL file."""

    seed = CronRunsStore(workspace_root=tmp_path)
    seed.append(_record(2))
    runs_path = tmp_path / ".nanoassistant" / "cron" / "runs.jsonl"
    original_read_text = Path.read_text
    reads = 0

    def _counted_read_text(path: Path, *args, **kwargs):
        nonlocal reads
        if path == runs_path:
            reads += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counted_read_text)
    store = CronRunsStore(workspace_root=tmp_path)

    for index in range(25):
        store.update_status(
            "req-002",
            "running",
            started_at=f"2026-01-01T01:00:{index:02d}+00:00",
        )
    assert store.list_by_job("job-a")[0].status == "running"
    assert store.list_by_job("job-a")[0].request_id == "req-002"
    assert reads == 1


def test_concurrent_append_and_update_survives_restart(tmp_path: Path) -> None:
    """One owner serializes concurrent transitions without corrupting durable replay."""

    store = CronRunsStore(workspace_root=tmp_path)
    records = [_record(index) for index in range(60)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(store.append, records))

    def _complete(record: CronRunRecord) -> None:
        store.update_status(
            record.request_id,
            "completed",
            finished_at="2026-01-01T02:00:00+00:00",
            result_summary=record.request_id,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_complete, records))

    live = {item.request_id: item for item in store.list_by_job("job-a", limit=100)}
    restarted = {
        item.request_id: item
        for item in CronRunsStore(workspace_root=tmp_path).list_by_job(
            "job-a", limit=100
        )
    }

    assert live == restarted
    assert len(restarted) == 60
    assert all(item.status == "completed" for item in restarted.values())
    assert all(item.result_summary == item.request_id for item in restarted.values())


def test_list_by_job_keeps_newest_first_and_max_limit(tmp_path: Path) -> None:
    """Incremental state must preserve newest-first ordering and the public hard cap."""

    store = CronRunsStore(workspace_root=tmp_path)
    for index in range(105):
        store.append(_record(index))

    results = store.list_by_job("job-a", limit=1000)

    assert len(results) == 100
    assert results[0].request_id == "req-104"
    assert results[-1].request_id == "req-005"


def test_materialized_index_bounds_terminal_history_but_keeps_active_runs(
    tmp_path: Path,
) -> None:
    """Durable history may grow, but one owner keeps only 100 terminals per job."""

    store = CronRunsStore(workspace_root=tmp_path)
    active = _record(999, job_id="job-a")
    store.append(active)
    for index in range(105):
        record = _record(index, job_id="job-a")
        store.append(record)
        store.update_status(record.request_id, "completed")

    live = store._materialize_all()  # noqa: SLF001
    restarted = CronRunsStore(workspace_root=tmp_path)._materialize_all()  # noqa: SLF001

    assert live == restarted
    assert active.request_id in live
    terminal = [record for record in live.values() if record.status == "completed"]
    assert len(terminal) == 100
    assert {record.request_id for record in terminal} == {
        f"req-{index:03d}" for index in range(5, 105)
    }


def test_restart_converges_only_non_terminal_records(tmp_path: Path) -> None:
    """Restart convergence must retain completed rows and fail accepted/running rows."""

    store = CronRunsStore(workspace_root=tmp_path)
    for index, status in enumerate(("accepted", "running", "completed")):
        record = _record(index, job_id="job-restart")
        store.append(record)
        if status != "accepted":
            store.update_status(record.request_id, status)

    restarted = CronRunsStore(workspace_root=tmp_path)
    restarted.converge_stale_on_restart()
    records = {
        item.request_id: item
        for item in restarted.list_by_job("job-restart", limit=100)
    }

    assert records["req-000"].status == "failed"
    assert records["req-001"].status == "failed"
    assert records["req-002"].status == "completed"
