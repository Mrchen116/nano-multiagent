"""Trusted deployment access facts used when rendering PA prompts."""

from dataclasses import dataclass
from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class RuntimeAccessContext:
    """Capture authenticated IM entry and an optional configured execution host."""

    im_user_url: str
    execution_access_address: str | None = None


RuntimeAccessContextProvider = Callable[[], RuntimeAccessContext]


def offline_access_context() -> RuntimeAccessContext:
    """Return clearly marked configuration placeholders for offline previews."""
    return RuntimeAccessContext("{IM_PUBLIC_URL (not connected)}")
