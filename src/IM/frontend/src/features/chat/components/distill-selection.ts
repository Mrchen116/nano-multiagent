import type { Conversation } from "../chat-types";

export function isDistillConversationEligible(conversation: Conversation): boolean {
  return (
    conversation.run_state !== "running"
    && Boolean(conversation.source_agent_id)
    && Boolean(conversation.source_node_id)
    && Boolean(conversation.source_jsonl_path)
    && (conversation.source_jsonl_status === undefined || conversation.source_jsonl_status === "ready")
  );
}

export function getDistillConversationUnavailableKey(
  conversation: Conversation,
  selectedSourceNodeId?: string | null,
): "running" | "noTranscript" | "transcriptUnavailable" | "differentNode" | null {
  if (conversation.run_state === "running") return "running";
  if (conversation.source_jsonl_status === "unavailable") return "transcriptUnavailable";
  if (!conversation.source_agent_id || !conversation.source_node_id) {
    return "noTranscript";
  }
  if (!conversation.source_jsonl_path) return "noTranscript";
  if (selectedSourceNodeId && conversation.source_node_id !== selectedSourceNodeId) {
    return "differentNode";
  }
  return null;
}
