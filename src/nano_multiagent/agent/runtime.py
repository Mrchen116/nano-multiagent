from typing import Any, Mapping, Sequence

from nano_multiagent.core.ids import make_message_id, make_turn_id
from nano_multiagent.core.types import TurnResult
from nano_multiagent.llm.factory import LLMFactoryConfig, create_llm_client
from nano_multiagent.llm.interfaces import LLMClient
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.models import Session

from .loop import AgentLoop
from .policies import AgentPolicies
from .state import AgentState, InputPart, parse_input_parts, render_user_text


class AgentRuntime:
    def __init__(
        self,
        *,
        session_manager: SessionManager,
        llm_client: LLMClient | None = None,
        model: str | None = None,
        policies: AgentPolicies | None = None,
    ) -> None:
        active_llm_client = llm_client or create_llm_client()
        self._session_manager = session_manager
        self._loop = AgentLoop(
            llm_client=active_llm_client,
            model=model or LLMFactoryConfig.from_env().model,
            policies=policies,
        )

    def run(self, session_id: str, parts: Sequence[Mapping[str, Any]], *, stream: bool = True) -> TurnResult:
        del stream  # M4 minimal runtime only supports non-stream flow.

        if self._session_manager.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")

        input_parts = parse_input_parts(parts)
        user_text = render_user_text(input_parts)
        if not user_text:
            raise ValueError("empty input parts are not allowed")

        turn_id = make_turn_id()
        history = self._session_manager.list_turn_messages(session_id)
        turn_count = sum(1 for message in history if message.role == "user")
        user_message_id = make_message_id()

        self._session_manager.append_turn_message(
            session_id,
            turn_id=turn_id,
            role="user",
            content=user_text,
            message_id=user_message_id,
            parts=_serialize_input_parts(input_parts),
        )

        turn_result = self._loop.run(
            AgentState(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history_messages=history,
                input_parts=input_parts,
                user_text=user_text,
            )
        )

        for assistant_message in turn_result.messages:
            self._session_manager.append_turn_message(
                session_id,
                turn_id=turn_id,
                role=assistant_message.role,
                content=assistant_message.content,
                message_id=assistant_message.message_id,
            )
        return turn_result

    def continue_turn(self, session_id: str, *, stream: bool = True) -> TurnResult:
        return self.run(
            session_id,
            [{"type": "text", "text": "continue"}],
            stream=stream,
        )

    def get_session(self, session_id: str) -> Session | None:
        return self._session_manager.get_session(session_id)


def _serialize_input_parts(parts: Sequence[InputPart]) -> tuple[dict[str, Any], ...]:
    serialized: list[dict[str, Any]] = []
    for part in parts:
        payload: dict[str, Any] = {"type": part.type}
        if part.text is not None:
            payload["text"] = part.text
        if part.image_url is not None:
            payload["image_url"] = part.image_url
        if part.mime_type is not None:
            payload["mime_type"] = part.mime_type
        payload.update(part.metadata)
        serialized.append(payload)
    return tuple(serialized)
