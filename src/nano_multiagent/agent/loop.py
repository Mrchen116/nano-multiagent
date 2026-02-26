from nano_multiagent.core.ids import make_message_id
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.llm.interfaces import LLMClient, LLMGenerateRequest

from .policies import AgentPolicies
from .prompting import DEFAULT_SYSTEM_PROMPT, build_prompt_messages
from .state import AgentState


class AgentLoop:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model: str,
        policies: AgentPolicies | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._llm_client = llm_client
        self._model = model
        self._policies = policies or AgentPolicies()
        self._system_prompt = system_prompt

    def run(self, state: AgentState) -> TurnResult:
        self._policies.ensure_turn_allowed(turn_count=state.turn_count)
        history = self._policies.truncate_history(state.history_messages)
        prompt_messages = build_prompt_messages(
            history_messages=history,
            user_text=state.user_text,
            system_prompt=self._system_prompt,
        )

        response = self._llm_client.generate(
            LLMGenerateRequest(
                session_id=state.session_id,
                model=self._model,
                messages=prompt_messages,
                stream=False,
            )
        )

        assistant_message = Message(
            message_id=make_message_id(),
            role=response.message.role,
            content=response.message.content,
            name=response.message.name,
        )

        return TurnResult(
            session_id=state.session_id,
            turn_id=state.turn_id,
            messages=(assistant_message,),
            completed=True,
            stop_reason=response.finish_reason or "completed",
        )
