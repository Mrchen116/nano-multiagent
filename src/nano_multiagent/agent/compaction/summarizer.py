"""Generate compaction summaries from dropped conversation history."""

from typing import Sequence

from nano_multiagent.core.types import Message
from nano_multiagent.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage

from .types import CompactionReason

SUMMARY_SYSTEM_PROMPT = (
    "Summarize conversation context with fixed sections: "
    "目标, 约束, 进展, 决策, 下一步, 关键上下文. Keep it concise."
)


class CompactionSummarizer:
    """Summarize dropped history via LLM with deterministic fallback."""

    def __init__(self, *, llm_client: LLMClient, model: str) -> None:
        self._llm_client = llm_client
        self._model = model

    def summarize(
        self,
        *,
        session_id: str,
        reason: CompactionReason,
        dropped_messages: Sequence[Message],
    ) -> str:
        """Summarize dropped messages for compaction record.

        Args:
            session_id: Session id used for provider tracing.
            reason: Compaction trigger reason.
            dropped_messages: Messages that will be removed from active context.

        Returns:
            Generated summary, or fallback summary on empty input/failure.
        """

        if not dropped_messages:
            return _fallback_summary(reason=reason)

        transcript_lines = [
            f"- {message.role}: {message.content}"
            for message in dropped_messages
        ]
        prompt = (
            f"Compaction reason: {reason.value}\n"
            "Conversation slice:\n"
            f"{chr(10).join(transcript_lines)}"
        )
        try:
            response = self._llm_client.generate(
                LLMGenerateRequest(
                    session_id=session_id,
                    model=self._model,
                    messages=(
                        LLMMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
                        LLMMessage(role="user", content=prompt),
                    ),
                    stream=False,
                )
            )
            summary = response.message.content.strip()
            return summary or _fallback_summary(reason=reason)
        except Exception:
            return _fallback_summary(reason=reason)


def _fallback_summary(*, reason: CompactionReason) -> str:
    return (
        "目标: 维持会话连续性\n"
        "约束: 上下文窗口受限\n"
        "进展: 已完成历史压缩\n"
        f"决策: 触发原因为 {reason.value}\n"
        "下一步: 继续处理最新用户请求\n"
        "关键上下文: 仅保留近期消息"
    )
