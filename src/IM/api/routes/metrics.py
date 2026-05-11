"""Usage metrics routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from IM.api.deps import current_user, get_metrics_service
from IM.application.metrics_service import MetricsService
from IM.domain.models import UsageMetric, User

router = APIRouter(tags=["metrics"])


class UsageMetricResponse(BaseModel):
    """Serialized aggregated usage row returned by metrics APIs."""

    scope: str
    scope_id: str | None
    owner_id: str | None
    conversation_id: str | None
    agent_id: str | None
    turns: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    last_used_at: str | None


def to_usage_metric_response(metric: UsageMetric) -> UsageMetricResponse:
    """Convert one usage metric domain model to API response shape."""
    return UsageMetricResponse(
        scope=metric.scope,
        scope_id=metric.scope_id,
        owner_id=metric.owner_id,
        conversation_id=metric.conversation_id,
        agent_id=metric.agent_id,
        turns=metric.turns,
        prompt_tokens=metric.prompt_tokens,
        completion_tokens=metric.completion_tokens,
        total_tokens=metric.total_tokens,
        last_used_at=metric.last_used_at,
    )


@router.get("/im/v1/metrics/usage", response_model=list[UsageMetricResponse])
def list_usage_metrics(
    conversation_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    service: MetricsService = Depends(get_metrics_service),
) -> list[UsageMetricResponse]:
    """List aggregated token/turn usage rows scoped to the caller's tenant.

    ``owner_id`` is no longer accepted as a query parameter — it is always taken
    from the authenticated subject so callers cannot probe another tenant.
    """
    return [
        to_usage_metric_response(item)
        for item in service.list_usage(
            owner_id=user.owner_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )
    ]
