"""Settings policies routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from IM.api.deps import get_policy_service
from IM.application.policy_service import PolicyService
from IM.domain.models import SettingsPolicy

router = APIRouter(tags=["policies"])


class PolicyResponse(BaseModel):
    """Serialized settings-policy object returned by policies APIs."""

    default_model: str
    max_turn_per_run: int
    max_attachment_size_mb: int
    retention_days: int
    audit_level: str
    rate_limit_per_min: int


class UpdatePolicyRequest(BaseModel):
    """Request payload for updating the singleton settings-policy document."""

    default_model: str = Field(min_length=1)
    max_turn_per_run: int = Field(ge=1)
    max_attachment_size_mb: int = Field(ge=1)
    retention_days: int = Field(ge=1)
    audit_level: str = Field(pattern="^(off|basic|strict)$")
    rate_limit_per_min: int = Field(ge=1)


def to_policy_response(policy: SettingsPolicy) -> PolicyResponse:
    """Convert a domain policy snapshot to the API response model."""
    return PolicyResponse(
        default_model=policy.default_model,
        max_turn_per_run=policy.max_turn_per_run,
        max_attachment_size_mb=policy.max_attachment_size_mb,
        retention_days=policy.retention_days,
        audit_level=policy.audit_level,
        rate_limit_per_min=policy.rate_limit_per_min,
    )


@router.get("/im/v1/policies", response_model=PolicyResponse)
def get_policies(service: PolicyService = Depends(get_policy_service)) -> PolicyResponse:
    """Return the singleton settings-policy snapshot."""
    return to_policy_response(service.get_policies())


@router.patch("/im/v1/policies", response_model=PolicyResponse)
def update_policies(
    payload: UpdatePolicyRequest,
    service: PolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    """Update the singleton settings-policy document."""
    try:
        updated = service.update_policies(
            default_model=payload.default_model,
            max_turn_per_run=payload.max_turn_per_run,
            max_attachment_size_mb=payload.max_attachment_size_mb,
            retention_days=payload.retention_days,
            audit_level=payload.audit_level,
            rate_limit_per_min=payload.rate_limit_per_min,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_policy_response(updated)
