"""Gateway recovery handoff validation and exactly-once adoption."""

from types import SimpleNamespace

import pytest

from personal_assistant.gateway.session_run_coordinator import (
    AcceptedRecoveryFollower,
    RecoveryHandoffError,
    RecoveryHandoffLedger,
)


def _follower(pending_id: str):  # noqa: ANN202
    return AcceptedRecoveryFollower(
        pending_id=pending_id,
        request=SimpleNamespace(message=SimpleNamespace(text=pending_id)),
    )


def _queued(
    *,
    run_id: str,
    recovery_id: str,
    batch_index: int,
    origin: str,
    pending_ids: list[str],
) -> dict[str, object]:
    return {
        "event": "run_status",
        "run_id": run_id,
        "status": "queued",
        "continuation": {
            "recovery_id": recovery_id,
            "predecessor_run_id": "run-old",
            "batch_index": batch_index,
            "origin": origin,
            "pending_ids": pending_ids,
        },
    }


def test_ledger_claims_user_suffix_across_origin_batches_and_settles_once() -> None:
    ledger = RecoveryHandoffLedger(
        predecessor_run_id="run-old",
        followers=(_follower("pending-1"), _follower("pending-2")),
    )

    first = ledger.observe_successor(
        _queued(
            run_id="run-user-1",
            recovery_id="recovery-1",
            batch_index=0,
            origin="user",
            pending_ids=["pending-1"],
        )
    )
    background = ledger.observe_successor(
        _queued(
            run_id="run-background",
            recovery_id="recovery-1",
            batch_index=1,
            origin="background_task",
            pending_ids=["pending-background"],
        )
    )
    second = ledger.observe_successor(
        _queued(
            run_id="run-user-2",
            recovery_id="recovery-1",
            batch_index=2,
            origin="user",
            pending_ids=["pending-2"],
        )
    )

    assert first is not None and [item.pending_id for item in first.followers] == [
        "pending-1"
    ]
    assert background is None
    assert second is not None and [item.pending_id for item in second.followers] == [
        "pending-2"
    ]
    settlement = {
        "event": "recovery_settled",
        "recovery_id": "recovery-1",
        "predecessor_run_id": "run-old",
        "outcome": "scheduled",
        "successor_run_ids": ["run-user-1", "run-background", "run-user-2"],
    }
    assert ledger.observe_settlement(settlement) is True
    assert ledger.observe_settlement(settlement) is False
    assert (
        ledger.observe_successor(
            _queued(
                run_id="run-user-1",
                recovery_id="recovery-1",
                batch_index=0,
                origin="user",
                pending_ids=["pending-1"],
            )
        )
        is None
    )


def test_ledger_ignores_duplicate_batch_identity_and_late_successor() -> None:
    ledger = RecoveryHandoffLedger(
        predecessor_run_id="run-old", followers=(_follower("pending-1"),)
    )
    assert (
        ledger.observe_successor(
            _queued(
                run_id="run-user",
                recovery_id="recovery-1",
                batch_index=0,
                origin="user",
                pending_ids=["pending-1"],
            )
        )
        is not None
    )
    assert (
        ledger.observe_successor(
            _queued(
                run_id="duplicate-batch",
                recovery_id="recovery-1",
                batch_index=0,
                origin="background_task",
                pending_ids=["background"],
            )
        )
        is None
    )
    assert (
        ledger.observe_settlement(
            {
                "event": "recovery_settled",
                "recovery_id": "recovery-1",
                "predecessor_run_id": "run-old",
                "outcome": "scheduled",
                "successor_run_ids": ["run-user"],
            }
        )
        is True
    )
    assert (
        ledger.observe_successor(
            _queued(
                run_id="late",
                recovery_id="recovery-1",
                batch_index=1,
                origin="background_task",
                pending_ids=["background"],
            )
        )
        is None
    )


@pytest.mark.parametrize(
    ("event", "match"),
    [
        (
            _queued(
                run_id="run-corrupt",
                recovery_id="recovery-1",
                batch_index=0,
                origin="user",
                pending_ids=["wrong-pending"],
            ),
            "pending ids",
        ),
        (
            {
                "event": "recovery_settled",
                "recovery_id": "recovery-1",
                "predecessor_run_id": "run-old",
                "outcome": "unavailable",
                "successor_run_ids": [],
            },
            "unavailable",
        ),
    ],
)
def test_ledger_fails_closed_on_corrupt_or_unavailable_handoff(
    event: dict[str, object], match: str
) -> None:
    ledger = RecoveryHandoffLedger(
        predecessor_run_id="run-old", followers=(_follower("pending-1"),)
    )

    with pytest.raises(RecoveryHandoffError, match=match):
        if event["event"] == "run_status":
            ledger.observe_successor(event)
        else:
            ledger.observe_settlement(event)
