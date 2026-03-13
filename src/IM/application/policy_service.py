"""Application service for IM settings-policy APIs."""

from IM.domain.models import SettingsPolicy
from IM.infra.repositories import SettingsPolicyRepository


class PolicyService:
    """Coordinate reads and writes for the settings center policy document."""

    def __init__(self, *, policies: SettingsPolicyRepository) -> None:
        """Bind service to the singleton settings-policy repository."""
        self._policies = policies

    def get_policies(self) -> SettingsPolicy:
        """Return the current settings-policy snapshot."""
        return self._policies.get_policies()

    def update_policies(
        self,
        *,
        default_model: str,
        max_turn_per_run: int,
        max_attachment_size_mb: int,
        retention_days: int,
        audit_level: str,
        rate_limit_per_min: int,
    ) -> SettingsPolicy:
        """Persist a new settings-policy snapshot and return it."""
        return self._policies.update_policies(
            default_model=default_model,
            max_turn_per_run=max_turn_per_run,
            max_attachment_size_mb=max_attachment_size_mb,
            retention_days=retention_days,
            audit_level=audit_level,
            rate_limit_per_min=rate_limit_per_min,
        )
