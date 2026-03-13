import { ChatAttachment, ChatMessage, ChatStarter, ConversationDetail, ConversationSummary, UsageMetricRow } from "./types";

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
    is_muted: false,
    kind: "group",
    kind_label: "Group chat",
    target_label: "OpsBot + Alex",
    discoverability_hint: "Collaborate with multiple teammates and agents in one thread."
  },
  {
    conversation_id: "conv-agent-design",
    title: "Agent Design Desk",
    last_message_preview: "Need a safe default for NO_REPLY policy.",
    last_message_at: "2026-03-03T21:18:00+08:00",
    unread_count: 0,
    participants: ["You", "DesignBot"],
    is_pinned: false,
    is_muted: false,
    kind: "direct-agent",
    kind_label: "Direct agent chat",
    target_label: "DesignBot",
    discoverability_hint: "Message this agent directly for design questions."
  },
  {
    conversation_id: "conv-platform-alerts",
    title: "Platform Alerts",
    last_message_preview: "node-app-07 heartbeat degraded",
    last_message_at: "2026-03-03T20:02:00+08:00",
    unread_count: 7,
    participants: ["System", "You"],
    is_pinned: false,
    is_muted: true,
    kind: "system",
    kind_label: "System feed",
    target_label: "Platform monitoring",
    discoverability_hint: "Operational notices land here so they stay separate from direct chats."
  },
  {
    conversation_id: "conv-agent-network",
    title: "OpsBot ↔ ReviewBot",
    last_message_preview: "ReviewBot will inspect the rollout checklist next.",
    last_message_at: "2026-03-03T19:42:00+08:00",
    unread_count: 0,
    participants: ["OpsBot", "ReviewBot"],
    is_pinned: false,
    is_muted: false,
    kind: "agent-network",
    kind_label: "Agent-to-agent chat",
    target_label: "OpsBot and ReviewBot",
    discoverability_hint: "Read how your agents coordinate before they report back to you."
  }
];

const DEFAULT_STARTER: ChatStarter = {
  title: "Agent · OpsBot",
  actionLabel: "Open Agent · OpsBot",
  actionHref: "/chat/conv-agent-design",
  agentName: "OpsBot",
  description: "OpsBot is your default starter chat, but you can also open direct agent chats, group chats, and agent-to-agent threads from the conversation list.",
  nodeLabel: "node-app-01",
  statusLabel: "Online and ready to chat via OpsBot on node-app-01"
};

const details = new Map<string, ConversationDetail>([
  [
    "conv-kernel-ops",
    {
      conversation_id: "conv-kernel-ops",
      title: "Kernel Ops Crew",
      kind_label: "Group chat",
      target_label: "OpsBot + Alex",
      discoverability_hint: "Use this thread when you want multiple participants working together.",
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
          is_mine: true,
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
      kind_label: "Direct agent chat",
      target_label: "DesignBot",
      discoverability_hint: "This is a one-to-one conversation with an available agent.",
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
      kind_label: "System feed",
      target_label: "Platform monitoring",
      discoverability_hint: "System notices stay here so they do not get mixed into your direct chats.",
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
  ],
  [
    "conv-agent-network",
    {
      conversation_id: "conv-agent-network",
      title: "OpsBot ↔ ReviewBot",
      kind_label: "Agent-to-agent chat",
      target_label: "OpsBot and ReviewBot",
      discoverability_hint: "You can inspect agent collaboration threads here before acting on the result.",
      messages: [
        {
          message_id: "m-5",
          sender_type: "agent",
          sender_name: "OpsBot",
          content: "I finished the rollout draft and need a second pass.",
          created_at: "2026-03-03T19:39:00+08:00",
          delivery_status: "completed"
        },
        {
          message_id: "m-6",
          sender_type: "agent",
          sender_name: "ReviewBot",
          content: "ReviewBot will inspect the rollout checklist next.",
          created_at: "2026-03-03T19:42:00+08:00",
          delivery_status: "completed"
        }
      ]
    }
  ]
]);

export async function getChatBootstrapState() {
  await wait();
  return {
    selfUserId: "mock-you",
    targetNodeId: "mock-node-1",
    initialConversationId: conversations[0]?.conversation_id ?? null
  };
}

export async function confirmBindToken(_: string) {
  await wait(40);
  return { node_id: "mock-node-1" };
}

export function resetChatBootstrapState() {
  return undefined;
}

export async function getChatStarter(): Promise<ChatStarter> {
  await wait();
  return { ...DEFAULT_STARTER };
}

export async function listConversations() {
  await wait();
  return [...conversations].sort((a, b) => Number(Boolean(b.is_pinned)) - Number(Boolean(a.is_pinned)));
}

export async function getConversation(conversationId: string) {
  await wait();
  const found = details.get(conversationId);
  return found ? { ...found, messages: [...found.messages] } : null;
}

export async function uploadAttachment(file: File): Promise<ChatAttachment> {
  await wait(40);
  return {
    url: `http://localhost:8011/im/uploads/mock-${file.name}`,
    file_name: file.name,
    content_type: file.type || "application/octet-stream"
  };
}

export async function getUsageMetrics(input: { ownerId?: string; conversationId?: string; agentId?: string } = {}) {
  await wait(40);
  const rows: UsageMetricRow[] = [
    {
      scope: "conversation",
      scope_id: "conv-kernel-ops",
      owner_id: "mock-you",
      conversation_id: "conv-kernel-ops",
      agent_id: null,
      turns: 4,
      prompt_tokens: 14,
      completion_tokens: 10,
      total_tokens: 24,
      last_used_at: "2026-03-03T22:35:00+08:00"
    },
    {
      scope: "conversation",
      scope_id: "conv-agent-design",
      owner_id: "mock-you",
      conversation_id: "conv-agent-design",
      agent_id: null,
      turns: 2,
      prompt_tokens: 6,
      completion_tokens: 5,
      total_tokens: 11,
      last_used_at: "2026-03-03T21:18:00+08:00"
    }
  ];
  return rows.filter((item) => {
    if (input.conversationId && item.conversation_id !== input.conversationId) {
      return false;
    }
    if (input.ownerId && item.owner_id !== input.ownerId) {
      return false;
    }
    if (input.agentId && item.agent_id !== input.agentId) {
      return false;
    }
    return true;
  });
}

export async function sendMessage(input: { conversationId: string; content: string; attachments?: ChatAttachment[] }) {
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
    is_mine: true,
    content: input.content,
    attachments: input.attachments ?? [],
    created_at: timestamp,
    delivery_status: "sent"
  };
  conversation.messages.push(userMessage);

  const summary = conversations.find((item) => item.conversation_id === input.conversationId);
  if (summary) {
    summary.last_message_preview = input.content || input.attachments?.[0]?.file_name || "Attachment";
    summary.last_message_at = timestamp;
  }

  return userMessage;
}

export function streamConversationEvents(_: {
  conversationId: string;
  onEvent: (event: { eventType: string; payload: Record<string, unknown> }) => void;
  onError?: (error: Error) => void;
}) {
  return () => undefined;
}
