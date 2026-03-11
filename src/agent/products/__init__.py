"""Canonical product package exports."""

from .base import ProductProfile, ResolvedProductConfig
from .local_coding import LOCAL_CODING_PROFILE
from .personal_assistant import PERSONAL_ASSISTANT_PROFILE

__all__ = [
    "ProductProfile",
    "ResolvedProductConfig",
    "LOCAL_CODING_PROFILE",
    "PERSONAL_ASSISTANT_PROFILE",
]
