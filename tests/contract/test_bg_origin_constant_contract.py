"""Contract: _BACKGROUND_TASK_ORIGIN must stay in sync with RunOrigin enum.

bugfix-404 F2: _BACKGROUND_TASK_ORIGIN in background_session_events.py is a
hand-copied string constant that must equal RunOrigin.BACKGROUND_TASK.value.
The R4 fix corrected a case mismatch; this test pins the invariant so future
refactors cannot reintroduce the same drift silently.

personal_assistant may not import agent.core directly (module-boundary rule),
so the constant is a necessary copy.  This contract test is the single place
where both sides are imported and compared, making any divergence a CI failure.
"""

from agent.core.runs.origin import RunOrigin
from personal_assistant.gateway.background_session_events import (
    _BACKGROUND_TASK_ORIGIN,
)


def test_background_task_origin_matches_run_origin_enum() -> None:
    """_BACKGROUND_TASK_ORIGIN must equal RunOrigin.BACKGROUND_TASK.value."""
    assert _BACKGROUND_TASK_ORIGIN == RunOrigin.BACKGROUND_TASK.value, (
        f"background_session_events._BACKGROUND_TASK_ORIGIN={_BACKGROUND_TASK_ORIGIN!r} "
        f"diverged from RunOrigin.BACKGROUND_TASK.value={RunOrigin.BACKGROUND_TASK.value!r}. "
        "Update _BACKGROUND_TASK_ORIGIN to match the enum (see bugfix-404 R4)."
    )
