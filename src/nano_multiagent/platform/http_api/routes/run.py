"""HTTP handlers for async run state query and cancellation."""

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from nano_multiagent.runs.registry import RunRecord, RunsRegistry

from ..auth import require_bearer_auth
from ..deps import APIError, get_runs_registry

router = APIRouter(
    prefix="/v1/runs",
    tags=["runs"],
    dependencies=[Depends(require_bearer_auth)],
)


class RunResponse(BaseModel):
    """Run snapshot returned by polling and cancel endpoints."""

    run_id: str
    session_id: str
    status: str
    created_at: str
    updated_at: str
    turn_id: str | None = None
    stop_reason: str | None = None
    error: dict[str, Any] | None = None
    usage: dict[str, int] | None = None


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    runs: RunsRegistry = Depends(get_runs_registry),
) -> RunResponse:
    """Return current run state, or 404 when run id is unknown."""
    record = runs.get(run_id)
    if record is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message=f"run does not exist: {run_id}",
            retryable=False,
        )
    return _to_run_response(record)


@router.post("/{run_id}/cancel", response_model=RunResponse)
def cancel_run(
    run_id: str,
    runs: RunsRegistry = Depends(get_runs_registry),
) -> RunResponse:
    """Request run cancellation and return updated run record."""
    record = runs.cancel(run_id)
    if record is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message=f"run does not exist: {run_id}",
            retryable=False,
        )
    return _to_run_response(record)


def _to_run_response(record: RunRecord) -> RunResponse:
    """Convert registry model to stable HTTP response schema."""
    return RunResponse(
        run_id=record.run_id,
        session_id=record.session_id,
        status=record.status.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
        turn_id=record.turn_id,
        stop_reason=record.stop_reason,
        error=dict(record.error) if record.error is not None else None,
        usage=(
            {
                "prompt_tokens": record.usage.prompt_tokens,
                "completion_tokens": record.usage.completion_tokens,
                "total_tokens": record.usage.total_tokens,
            }
            if record.usage is not None
            else None
        ),
    )
