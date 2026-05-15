import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { Attachment, Conversation, MentionCandidate, Message, PermissionRequest } from "../chat-types";
import { MessagePane } from "./message-pane";

const DIRECT_CONV: Conversation = {
  id: "c1",
  title: "Planner",
  participants: [{ type: "agent", id: "a-planner", display_name: "Planner" }],
  participant_ids: ["a-planner"],
  type: "direct",
  direct_kind: "agent",
  owner_id: "u1",
  creator_id: "u1",
  is_pinned: false,
  is_muted: false,
  unread_count: 0,
  last_message_preview: null,
  last_message_at: null,
  created_at: "2026-01-01T00:00:00Z"
};

const GROUP_CONV: Conversation = {
  ...DIRECT_CONV,
  id: "c2",
  title: "Sprint Crew",
  type: "group",
  direct_kind: null,
  participants: [
    { type: "user", id: "u1", display_name: "You" },
    { type: "agent", id: "a-planner", display_name: "Planner" },
    { type: "agent", id: "a-coder", display_name: "Coder" }
  ],
  participant_ids: ["u1", "a-planner", "a-coder"]
};

const SAMPLE_MESSAGES: Message[] = [
  {
    id: "m1",
    conversation_id: "c1",
    sender: { type: "user", id: "u1", display_name: "You" },
    sender_user_id: "u1",
    sender_type: "user",
    content: "Hello",
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-01-01T00:00:00Z"
  },
  {
    id: "m2",
    conversation_id: "c1",
    sender: { type: "agent", id: "a-planner", display_name: "Planner" },
    sender_user_id: "u1",
    sender_type: "agent",
    content: "Hi back",
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-01-01T00:00:01Z"
  }
];

const MENTION_CANDIDATES: MentionCandidate[] = [
  { agent_id: "a-planner", display_name: "Planner", initials: "PL", status: "online" },
  { agent_id: "a-coder", display_name: "Coder", initials: "CO", status: "online" }
];

describe("MessagePane", () => {
  it("renders the conversation title and each message content", () => {
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={SAMPLE_MESSAGES}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );
    expect(screen.getByRole("heading", { name: "Planner" })).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Hi back")).toBeInTheDocument();
  });

  it("renders an empty-state hint when there are no messages", () => {
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );
    expect(screen.getByText(/No messages yet/i)).toBeInTheDocument();
  });

  it("submits typed draft and calls onSend with trimmed text", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={SAMPLE_MESSAGES}
        mentionCandidates={[]}
        onSend={onSend}
      />
    );
    const composer = screen.getByRole("textbox");
    await user.type(composer, "  hello world  ");
    await user.click(screen.getByRole("button", { name: /Send/i }));
    expect(onSend).toHaveBeenCalledWith("hello world", []);
  });

  it("uploads dropped files and surfaces chips in the composer", async () => {
    const onSend = vi.fn();
    const uploaded: Attachment = {
      url: "http://im.local/im/uploads/dropped.png",
      content_type: "image/png",
      file_name: "dropped.png"
    };
    const uploader = vi.fn(async (_file: File): Promise<Attachment> => uploaded);
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[]}
        mentionCandidates={[]}
        onSend={onSend}
        uploadAttachment={uploader}
      />
    );
    const composer = screen.getByRole("textbox");
    await userEvent.type(composer, "see image");

    const file = new File([new Uint8Array(4)], "dropped.png", { type: "image/png" });
    const dropZone = composer.closest("[data-dragging]") as HTMLElement;
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file], items: [], types: ["Files"] }
    });

    // wait for chip to render after upload resolves
    const chipImg = await screen.findByRole("img", { name: "dropped.png" });
    expect(chipImg).toBeInTheDocument();
    expect(uploader).toHaveBeenCalledWith(file);

    await userEvent.click(screen.getByRole("button", { name: /Send/i }));
    expect(onSend).toHaveBeenCalledWith("see image", [uploaded]);

    // After send, chips should clear
    expect(screen.queryByRole("img", { name: "dropped.png" })).not.toBeInTheDocument();
  });

  it("removes a pending attachment when its chip × is clicked", async () => {
    const uploaded: Attachment = {
      url: "http://im.local/im/uploads/a.pdf",
      content_type: "application/pdf",
      file_name: "a.pdf"
    };
    const uploader = vi.fn(async () => uploaded);
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[]}
        mentionCandidates={[]}
        onSend={() => {}}
        uploadAttachment={uploader}
      />
    );
    const composer = screen.getByRole("textbox");
    const dropZone = composer.closest("[data-dragging]") as HTMLElement;
    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [new File([new Uint8Array(4)], "a.pdf", { type: "application/pdf" })],
        items: [],
        types: ["Files"]
      }
    });
    const removeBtn = await screen.findByRole("button", { name: /Remove a\.pdf/i });
    await userEvent.click(removeBtn);
    expect(screen.queryByText("a.pdf")).not.toBeInTheDocument();
  });

  it("renders received-message attachments inside the bubble (image + doc)", () => {
    const withAttach: Message = {
      ...SAMPLE_MESSAGES[1]!,
      id: "m3",
      content: "see",
      attachments: [
        { url: "http://im.local/im/uploads/x.png", content_type: "image/png", file_name: "x.png" },
        { url: "http://im.local/im/uploads/y.pdf", content_type: "application/pdf", file_name: "y.pdf" }
      ]
    };
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[withAttach]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );
    expect(screen.getByRole("img", { name: "x.png" })).toHaveAttribute(
      "src",
      "http://im.local/im/uploads/x.png"
    );
    expect(screen.getByText("y.pdf").closest("a")).toHaveAttribute(
      "href",
      "http://im.local/im/uploads/y.pdf"
    );
  });

  it("shows mention picker after typing '@' inside a group conversation", async () => {
    const user = userEvent.setup();
    render(
      <MessagePane
        conversation={GROUP_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={() => {}}
      />
    );
    await user.type(screen.getByRole("textbox"), "hey @P");
    expect(await screen.findByRole("button", { name: /Planner/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Coder/ })).not.toBeInTheDocument();
  });

  it("does not show mention picker in direct-agent conversations", async () => {
    const user = userEvent.setup();
    render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={() => {}}
      />
    );
    await user.type(screen.getByRole("textbox"), "@");
    // mention picker container is the listbox/role-button list; ensure no candidate
    // buttons render
    expect(screen.queryByRole("button", { name: /Planner/i })).not.toBeInTheDocument();
  });

  it("inserts @AgentName when a mention candidate is clicked", async () => {
    const user = userEvent.setup();
    render(
      <MessagePane
        conversation={GROUP_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={() => {}}
      />
    );
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(composer, "ping @P");
    await user.click(await screen.findByRole("button", { name: /Planner/ }));
    expect(composer.value).toBe("ping @Planner ");
  });

  // R4 C1: PermissionCard mount point — renders inline card when message has permission_request
  describe("PermissionCard mount point (R4)", () => {
    const PERM_REQUEST: PermissionRequest = {
      request_id: "req-1",
      tool_name: "bash",
      tool_input: { command: "ls" },
      question: "Allow bash to run this command?",
      options: [
        { id: "allow_once", label: "Allow once", description: "Allow this single action" },
        { id: "deny", label: "Deny", description: "Block this action" },
      ],
      status: "pending",
    };

    const AGENT_MSG_WITH_PERM: Message = {
      id: "m-perm",
      conversation_id: "c1",
      sender: { type: "agent", id: "a-planner", display_name: "Planner" },
      sender_user_id: "u1",
      sender_type: "agent",
      content: "",
      attachments: [],
      delivery_status: "running",
      created_at: "2026-01-01T00:00:00Z",
      permission_request: PERM_REQUEST,
    };

    it("renders PermissionCard inline when agent message has permission_request", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[AGENT_MSG_WITH_PERM]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      // PermissionCard should render with the question text
      expect(screen.getByText(/Allow bash to run this command/i)).toBeInTheDocument();
      // Option buttons should be present
      expect(screen.getByRole("button", { name: /allow once/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /deny/i })).toBeInTheDocument();
    });

    it("does not render PermissionCard when message has no permission_request", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[{
            ...AGENT_MSG_WITH_PERM,
            id: "m-no-perm",
            permission_request: null,
            content: "Regular reply",
          }]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(screen.queryByText(/Allow bash to run this command/i)).not.toBeInTheDocument();
      expect(screen.getByText("Regular reply")).toBeInTheDocument();
    });

    it("renders resolved PermissionCard (no buttons) when status=resolved", () => {
      const resolvedMsg: Message = {
        ...AGENT_MSG_WITH_PERM,
        id: "m-resolved",
        permission_request: { ...PERM_REQUEST, status: "resolved", decision: "allow_once" },
      };
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[resolvedMsg]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(screen.getByTestId("permission-resolved")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /allow once/i })).not.toBeInTheDocument();
    });
  });

  // M19/R11-8: prototype `im-chat-page.jsx::MessagePaneView` 移动模式头部紧凑 —
  // 隐藏 participants / KindBadge / 顶部 TokenChip,Config 退化为 ⚙ icon-only 方块。
  // 桌面模式 (>= 768px) 全部保留 (不回归 R7-5 Node chip + ⚙ 桌面布局)。
  describe("R11-8: mobile compact header", () => {
    it("hides participants line on mobile", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={SAMPLE_MESSAGES}
          mentionCandidates={[]}
          onSend={() => {}}
          onBack={() => {}}
          isMobile
        />
      );
      expect(screen.queryByText("Planner", { selector: ".chat-pane-participants" })).not.toBeInTheDocument();
    });

    it("hides KindBadge on mobile but keeps NodeChip", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={SAMPLE_MESSAGES}
          mentionCandidates={[]}
          onSend={() => {}}
          onBack={() => {}}
          isMobile
          nodeName="laptop-prod"
          nodeStatus="online"
        />
      );
      expect(document.querySelector(".chat-kind-badge")).toBeNull();
      expect(screen.getByText("laptop-prod")).toBeInTheDocument();
    });

    it("hides the header TokenChip on mobile (token chip lives under each bubble per R6)", () => {
      const msg: Message = {
        ...SAMPLE_MESSAGES[1],
        token_usage: { output: 100, context_used: 5000, context_window: 20000 }
      };
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[msg]}
          mentionCandidates={[]}
          onSend={() => {}}
          onBack={() => {}}
          isMobile
        />
      );
      const header = document.querySelector(".chat-pane-header");
      expect(header).not.toBeNull();
      expect(header!.querySelector(".chat-token-chip")).toBeNull();
    });

    it("renders compact icon-only Config button on mobile (no Config text)", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={SAMPLE_MESSAGES}
          mentionCandidates={[]}
          onSend={() => {}}
          onBack={() => {}}
          onOpenConfig={() => {}}
          isMobile
        />
      );
      const configBtn = screen.getByRole("button", { name: /config/i });
      expect(configBtn.className).toMatch(/compact|icon|chat-pane-config-icon/);
      expect(configBtn.textContent?.trim()).toBe("⚙");
    });

    it("keeps participants + KindBadge + text Config on desktop (isMobile=false)", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={SAMPLE_MESSAGES}
          mentionCandidates={[]}
          onSend={() => {}}
          onOpenConfig={() => {}}
        />
      );
      expect(document.querySelector(".chat-pane-participants")).not.toBeNull();
      const configBtn = screen.getByRole("button", { name: /config/i });
      expect(configBtn.textContent).toMatch(/Config/i);
    });
  });

  // R8.5 — R11-7 MessageBubble visual rewrite on v2 production path.
  // Prototype source: docs/changes/feat-340-agent-native-im/attachments/prototype/project/im-components.jsx::MessageBubble
  //   avatar 30×30 outside bubble (row-reverse for user) + timestamp + per-bubble TokenChip in status row below bubble
  describe("R11-7 v2 MessageBubble visual", () => {
    const TS_USER: Message = {
      id: "mt-user",
      conversation_id: "c1",
      sender: { type: "user", id: "u1", display_name: "You" },
      sender_user_id: "u1",
      sender_type: "user",
      content: "User bubble",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-05-12T14:30:00Z"
    };
    const TS_AGENT_LOW: Message = {
      id: "mt-agent-low",
      conversation_id: "c1",
      sender: { type: "agent", id: "a-planner", display_name: "Planner" },
      sender_user_id: "u1",
      sender_type: "agent",
      content: "Agent bubble low usage",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-05-12T14:30:01Z",
      token_usage: { output: 1234, context_used: 30000, context_window: 200000 }
    };
    const TS_AGENT_WARN: Message = {
      ...TS_AGENT_LOW,
      id: "mt-agent-warn",
      token_usage: { output: 2000, context_used: 150000, context_window: 200000 }
    };
    const TS_AGENT_CRIT: Message = {
      ...TS_AGENT_LOW,
      id: "mt-agent-crit",
      token_usage: { output: 5000, context_used: 185000, context_window: 200000 }
    };

    it("matches prototype: user bubbles have no avatar, agent avatar stays outside the bubble", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[TS_USER, TS_AGENT_LOW]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      const userBubble = screen.getByTestId(`message-bubble-${TS_USER.id}`);
      expect(screen.queryByTestId(`message-avatar-${TS_USER.id}`)).toBeNull();
      const agentAvatar = screen.getByTestId(`message-avatar-${TS_AGENT_LOW.id}`);
      const agentBubble = screen.getByTestId(`message-bubble-${TS_AGENT_LOW.id}`);
      expect(agentBubble.contains(agentAvatar)).toBe(false);
    });

    it("renders a timestamp BELOW the bubble (not inside) in HH:MM format", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[TS_USER]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      const ts = screen.getByTestId(`message-timestamp-${TS_USER.id}`);
      const bubble = screen.getByTestId(`message-bubble-${TS_USER.id}`);
      expect(bubble.contains(ts)).toBe(false);
      expect(ts.textContent ?? "").toMatch(/\d{1,2}:\d{2}/);
    });

    it("renders a per-bubble TokenChip when token_usage is present", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[TS_AGENT_LOW]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      const chip = screen.getByTestId(`message-token-chip-${TS_AGENT_LOW.id}`);
      expect(chip).toBeInTheDocument();
      const bubble = screen.getByTestId(`message-bubble-${TS_AGENT_LOW.id}`);
      expect(bubble.contains(chip)).toBe(true);
    });

    it("token chip flips to warn color at >=70% context", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[TS_AGENT_WARN]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      const chip = screen.getByTestId(`message-token-chip-${TS_AGENT_WARN.id}`);
      expect(chip.className).toMatch(/chat-token-chip--warn/);
    });

    it("token chip flips to critical color at >=90% context", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[TS_AGENT_CRIT]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      const chip = screen.getByTestId(`message-token-chip-${TS_AGENT_CRIT.id}`);
      expect(chip.className).toMatch(/chat-token-chip--critical/);
    });

    it("does not render a per-bubble TokenChip when token_usage is absent", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[TS_USER]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(screen.queryByTestId(`message-token-chip-${TS_USER.id}`)).not.toBeInTheDocument();
    });
  });
});
