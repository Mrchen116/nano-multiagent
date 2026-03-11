"""Application service for IM usage metrics APIs."""

from IM.domain.models import UsageMetric
from IM.infra.repositories import UsageMetricsRepository


class MetricsService:
    """Coordinate usage metric reads and writes for IM-visible activity."""

    def __init__(self, *, metrics: UsageMetricsRepository) -> None:
        """Bind service to the usage metrics repository."""
        self._metrics = metrics

    def list_usage(
        self,
        *,
        owner_id: str | None = None,
        conversation_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[UsageMetric]:
        """Return aggregated token/turn usage rows filtered by optional scope IDs."""
        return self._metrics.list_usage_metrics(
            owner_id=owner_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )

    def record_usage(
        self,
        *,
        owner_id: str | None,
        conversation_id: str | None,
        agent_id: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        turns: int = 1,
    ) -> None:
        """Persist one usage sample produced by IM-visible activity."""
        self._metrics.record_usage(
            owner_id=owner_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            turns=turns,
        )
