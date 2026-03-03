"""Stable id generation helpers for runtime entities."""

from dataclasses import dataclass
from secrets import token_hex
from typing import Callable

TokenFactory = Callable[[], str]


def _default_token_factory() -> str:
    return token_hex(8)


@dataclass(frozen=True, slots=True)
class IdGenerator:
    """Generate prefixed opaque identifiers for domain entities."""

    token_factory: TokenFactory = _default_token_factory

    def _make_id(self, prefix: str) -> str:
        token = self.token_factory()
        if not token:
            raise ValueError("token_factory returned an empty token")
        return f"{prefix}_{token}"

    def make_session_id(self) -> str:
        """Generate a session id."""

        return self._make_id("sess")

    def make_turn_id(self) -> str:
        """Generate a turn id."""

        return self._make_id("turn")

    def make_message_id(self) -> str:
        """Generate a message id."""

        return self._make_id("msg")

    def make_tool_call_id(self) -> str:
        """Generate a tool call id."""

        return self._make_id("call")

    def make_event_id(self) -> str:
        """Generate an event id."""

        return self._make_id("evt")

    def make_run_id(self) -> str:
        """Generate a run id."""

        return self._make_id("run")


DEFAULT_ID_GENERATOR = IdGenerator()


def make_session_id() -> str:
    """Generate a session id using the default generator."""

    return DEFAULT_ID_GENERATOR.make_session_id()


def make_turn_id() -> str:
    """Generate a turn id using the default generator."""

    return DEFAULT_ID_GENERATOR.make_turn_id()


def make_message_id() -> str:
    """Generate a message id using the default generator."""

    return DEFAULT_ID_GENERATOR.make_message_id()


def make_tool_call_id() -> str:
    """Generate a tool call id using the default generator."""

    return DEFAULT_ID_GENERATOR.make_tool_call_id()


def make_event_id() -> str:
    """Generate an event id using the default generator."""

    return DEFAULT_ID_GENERATOR.make_event_id()


def make_run_id() -> str:
    """Generate a run id using the default generator."""

    return DEFAULT_ID_GENERATOR.make_run_id()
