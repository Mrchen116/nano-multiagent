export type SenderType = "user" | "agent" | "system";

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  last_message_preview?: string;
  last_message_at?: string;
  unread_count: number;
  participants: string[];
  is_pinned?: boolean;
  is_muted?: boolean;
}

export interface ChatMessage {
  message_id: string;
  sender_type: SenderType;
  sender_name?: string;
  content: string;
  created_at: string;
  delivery_status?: "sent" | "running" | "completed" | "failed";
}

export interface ConversationDetail {
  conversation_id: string;
  title: string;
  messages: ChatMessage[];
}
