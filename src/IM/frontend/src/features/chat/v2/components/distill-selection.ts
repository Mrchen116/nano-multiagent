import type { Conversation } from "../chat-types";

export function isDistillConversationEligible(conversation: Conversation): boolean {
  return (
    conversation.run_state !== "running"
    && Boolean(conversation.source_agent_id)
    && Boolean(conversation.source_jsonl_path)
  );
}

export function getDistillConversationUnavailableKey(
  conversation: Conversation,
): "running" | "noTranscript" | null {
  if (conversation.run_state === "running") return "running";
  if (!conversation.source_agent_id || !conversation.source_jsonl_path) {
    return "noTranscript";
  }
  return null;
}
