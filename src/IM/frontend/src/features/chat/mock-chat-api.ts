import { ChatMessage, ConversationDetail, ConversationSummary } from "./types";

const wait = (ms = 80) => new Promise((resolve) => setTimeout(resolve, ms));

const conversations: ConversationSummary[] = [
  {
    conversation_id: "conv-kernel-ops",
    title: "Kernel Ops Crew",
    last_message_preview: "Retry policy was bumped to 30s cooldown.",
    last_message_at: "2026-03-03T22:35:00+08:00",
    unread_count: 3,
    participants: ["You", "OpsBot", "Alex"],
    is_pinned: true,
    is_muted: false
  },
  {
    conversation_id: "conv-agent-design",
    title: "Agent Design Desk",
    last_message_preview: "Need a safe default for NO_REPLY policy.",
    last_message_at: "2026-03-03T21:18:00+08:00",
    unread_count: 0,
    participants: ["You", "DesignBot"],
    is_pinned: false,
    is_muted: false
  },
  {
    conversation_id: "conv-platform-alerts",
    title: "Platform Alerts",
    last_message_preview: "node-app-07 heartbeat degraded",
    last_message_at: "2026-03-03T20:02:00+08:00",
    unread_count: 7,
    participants: ["System", "You"],
    is_pinned: false,
    is_muted: true
  }
];

const details = new Map<string, ConversationDetail>([
  [
    "conv-kernel-ops",
    {
      conversation_id: "conv-kernel-ops",
      title: "Kernel Ops Crew",
      messages: [
        {
          message_id: "m-1",
          sender_type: "agent",
          sender_name: "OpsBot",
          content: "CI is green after the retry-loop fix.",
          created_at: "2026-03-03T22:31:00+08:00",
          delivery_status: "completed"
        },
        {
          message_id: "m-2",
          sender_type: "user",
          sender_name: "You",
          content: "Ship the patch after frontend milestone smoke.",
          created_at: "2026-03-03T22:34:00+08:00",
          delivery_status: "sent"
        }
      ]
    }
  ],
  [
    "conv-agent-design",
    {
      conversation_id: "conv-agent-design",
      title: "Agent Design Desk",
      messages: [
        {
          message_id: "m-3",
          sender_type: "agent",
          sender_name: "DesignBot",
          content: "Policy drafts synced to settings mock layer.",
          created_at: "2026-03-03T21:16:00+08:00",
          delivery_status: "completed"
        }
      ]
    }
  ],
  [
    "conv-platform-alerts",
    {
      conversation_id: "conv-platform-alerts",
      title: "Platform Alerts",
      messages: [
        {
          message_id: "m-4",
          sender_type: "system",
          sender_name: "monitor",
          content: "node-app-07 status -> degraded",
          created_at: "2026-03-03T20:02:00+08:00",
          delivery_status: "running"
        }
      ]
    }
  ]
]);

export async function listConversations() {
  await wait();
  return [...conversations].sort((a, b) => Number(Boolean(b.is_pinned)) - Number(Boolean(a.is_pinned)));
}

export async function getConversation(conversationId: string) {
  await wait();
  const found = details.get(conversationId);
  return found ? { ...found, messages: [...found.messages] } : null;
}

export async function sendMessage(input: { conversationId: string; content: string }) {
  await wait(60);
  const conversation = details.get(input.conversationId);
  if (!conversation) {
    throw new Error("Conversation not found");
  }

  const timestamp = new Date().toISOString();
  const userMessage: ChatMessage = {
    message_id: `m-${Date.now()}`,
    sender_type: "user",
    sender_name: "You",
    content: input.content,
    created_at: timestamp,
    delivery_status: "sent"
  };
  conversation.messages.push(userMessage);

  const summary = conversations.find((item) => item.conversation_id === input.conversationId);
  if (summary) {
    summary.last_message_preview = input.content;
    summary.last_message_at = timestamp;
  }

  return userMessage;
}
