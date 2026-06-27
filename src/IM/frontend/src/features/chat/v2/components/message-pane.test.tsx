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
    created_at: "2026-01-01T00:00:00Z",
    permission_requests: []
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
    created_at: "2026-01-01T00:00:01Z",
    permission_requests: []
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

  it("renders a GFM markdown table in an agent message as a real <table>", () => {
    const tableMsg: Message = {
      id: "m-table",
      conversation_id: "c1",
      sender: { type: "agent", id: "a-planner", display_name: "Planner" },
      sender_user_id: "u1",
      sender_type: "agent",
      content: [
        "Here are the repos:",
        "",
        "| Repo | Note |",
        "|------|------|",
        "| **nano-multiagent** | main |",
        "| LLM_PROXY | proxy |",
        "",
        "That is all.",
      ].join("\n"),
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:02Z",
      permission_requests: [],
    };
    const { container } = render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[tableMsg]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );

    expect(container.querySelector("table")).not.toBeNull();
    expect(screen.getByRole("columnheader", { name: "Repo" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Note" })).toBeInTheDocument();
    // inline **bold** inside a cell still renders via renderInlineContent
    expect(screen.getByText("nano-multiagent").tagName).toBe("STRONG");
    expect(screen.getByText("LLM_PROXY")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3); // 1 header + 2 body
    // prose around the table stays as paragraphs, not swallowed into it
    expect(screen.getByText("Here are the repos:")).toBeInTheDocument();
    expect(screen.getByText("That is all.")).toBeInTheDocument();
    // raw delimiter pipes are no longer dumped as plain text
    expect(screen.queryByText(/\|------\|/)).toBeNull();
  });

  // CR-6: GFM table column alignment — th/td align attr mapped to style.textAlign
  it("applies column alignment from GFM table delimiter row to th and td", () => {
    const alignMsg: Message = {
      id: "m-align",
      conversation_id: "c1",
      sender: { type: "agent", id: "a-planner", display_name: "Planner" },
      sender_user_id: "a-planner",
      sender_type: "agent",
      content: [
        "| Left | Center | Right |",
        "|:-----|:------:|------:|",
        "| a    | b      | c     |",
      ].join("\n"),
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:02Z",
      permission_requests: [],
    };
    const { container } = render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[alignMsg]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );
    const headers = container.querySelectorAll("th");
    expect(headers[0]?.style.textAlign).toBe("left");
    expect(headers[1]?.style.textAlign).toBe("center");
    expect(headers[2]?.style.textAlign).toBe("right");
    const cells = container.querySelectorAll<HTMLTableCellElement>("tbody td");
    expect(cells[0]?.style.textAlign).toBe("left");
    expect(cells[1]?.style.textAlign).toBe("center");
    expect(cells[2]?.style.textAlign).toBe("right");
  });

  it("keeps blank lines inside fenced code blocks", () => {
    const codeMsg: Message = {
      id: "m-code",
      conversation_id: "c1",
      sender: { type: "agent", id: "a-planner", display_name: "Planner" },
      sender_user_id: "u1",
      sender_type: "agent",
      content: [
        "The file contains:",
        "",
        "```markdown",
        "# MEMORY",
        "",
        "First entry",
        "<!-- source: session -->",
        "",
        "Second entry",
        "```",
        "",
        "Done.",
      ].join("\n"),
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:02Z",
      permission_requests: [],
    };
    const { container } = render(
      <MessagePane
        conversation={DIRECT_CONV}
        messages={[codeMsg]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );

    const code = container.querySelector("pre > code");
    expect(code).not.toBeNull();
    expect(code).toHaveTextContent(
      "# MEMORY First entry <!-- source: session --> Second entry",
    );
    expect(screen.queryByText(/```markdown/)).toBeNull();
    expect(screen.getByText("Done.")).toBeInTheDocument();
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

  // bugfix-358 (composer): textarea 装可见形式 `@DisplayName`,wire XML 在 send 前重建。
  // 这样光标 / IME / 撤销栈跟视觉字符宽度对齐(原 textarea 装 XML 时,IME 输入框
  // 按 XML 字符长度定位,会飘到 chip 右侧远处)。
  it("inserts visible @DisplayName text into textarea (not raw XML)", async () => {
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
    // textarea 应该装可见形式 `@Planner`,不应含 wire XML 字符
    expect(composer.value).toContain("@Planner");
    expect(composer.value).not.toContain("<mention");
    expect(composer.value).not.toContain('target_id="');
  });

  it("reconstructs wire <mention/> XML in onSend when picker-tracked label is present", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <MessagePane
        conversation={GROUP_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={onSend}
      />
    );
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(composer, "ping @P");
    await user.click(await screen.findByRole("button", { name: /Planner/ }));
    await user.type(composer, "hi");
    await user.keyboard("{Enter}");
    expect(onSend).toHaveBeenCalledTimes(1);
    const sentText = onSend.mock.calls[0][0];
    expect(sentText).toContain('<mention type="agent" target_id="a-planner"/>');
    expect(sentText).not.toContain("@Planner");
  });

  it("drops a tracked mention from wire content when user deletes the @DisplayName label before send", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <MessagePane
        conversation={GROUP_CONV}
        messages={[]}
        mentionCandidates={MENTION_CANDIDATES}
        onSend={onSend}
      />
    );
    const composer = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(composer, "@P");
    await user.click(await screen.findByRole("button", { name: /Planner/ }));
    // User regrets, removes whole `@Planner ` and types plain text instead
    await user.clear(composer);
    await user.type(composer, "never mind");
    await user.keyboard("{Enter}");
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][0]).toBe("never mind");
    expect(onSend.mock.calls[0][0]).not.toContain("<mention");
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
      permission_requests: [PERM_REQUEST],
    };

    it("renders the pending PermissionCard INSIDE the bubble (feat-434 合一气泡)", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[AGENT_MSG_WITH_PERM]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(screen.getByText(/Allow bash to run this command/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /allow once/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /deny/i })).toBeInTheDocument();
      // feat-434 决策 1/3: the card now lives inside the agent bubble card, not as a
      // sibling floating outside it (the old "黑框墙" lived outside chat-bubble-card).
      const card = container.querySelector(".chat-permission-card");
      expect(card).not.toBeNull();
      expect(card?.closest(".chat-bubble-card")).not.toBeNull();
    });

    it("does not render PermissionCard when message has empty permission_requests list", () => {
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[{
            ...AGENT_MSG_WITH_PERM,
            id: "m-no-perm",
            permission_requests: [],
            content: "Regular reply",
          }]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(screen.queryByText(/Allow bash to run this command/i)).not.toBeInTheDocument();
      expect(screen.getByText("Regular reply")).toBeInTheDocument();
    });

    // feat-434 决策 3: a resolved审批 no longer renders an独立 card —— its呈现 moved to
    // the tool-call row's gate region. The bubble must NOT show a resolved permission card.
    it("does NOT render a resolved permission card (已决并入工具行)", () => {
      const resolvedMsg: Message = {
        ...AGENT_MSG_WITH_PERM,
        id: "m-resolved",
        permission_requests: [{ ...PERM_REQUEST, status: "resolved", decision: "allow_once" }],
      };
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[resolvedMsg]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(screen.queryByTestId("permission-resolved")).not.toBeInTheDocument();
      // no pending buttons either (it's resolved)
      expect(screen.queryByRole("button", { name: /allow once/i })).not.toBeInTheDocument();
    });

    // feat-434 决策 3 / spec Scenario-又来新待决: when one ask is已决 and a new ask is
    // pending, only the pending card shows (resolved已并入工具行); 用户仍能分清。
    it("shows only the new pending card when a prior ask is resolved (no resolved card)", () => {
      const msg: Message = {
        ...AGENT_MSG_WITH_PERM,
        id: "m-two-asks",
        permission_requests: [
          { ...PERM_REQUEST, request_id: "req-1", question: "Allow bash command #1?", status: "resolved", decision: "allow_once" },
          { ...PERM_REQUEST, request_id: "req-2", tool_name: "write", question: "Allow write call #2?", status: "pending" },
        ],
      };
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[msg]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      // resolved card gone
      expect(screen.queryByTestId("permission-resolved")).not.toBeInTheDocument();
      expect(screen.queryByText(/Allow bash command #1/i)).not.toBeInTheDocument();
      // 当前 pending 的按钮组仍可见
      expect(screen.getByText(/Allow write call #2/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /allow once/i })).toBeInTheDocument();
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
      created_at: "2026-05-12T14:30:00Z",
      permission_requests: []
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
      token_usage: { output: 1234, context_used: 30000, context_window: 200000 },
      permission_requests: []
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

  // bugfix-413: agent 气泡块级 Markdown 渲染（react-markdown 管线）
  describe("MarkdownContent block-level rendering (bugfix-413)", () => {
    function agentMsg(content: string): Message {
      return {
        id: "m-block",
        conversation_id: "c1",
        sender: { type: "agent", id: "a-planner", display_name: "Planner" },
        sender_user_id: "a-planner",
        sender_type: "agent",
        content,
        attachments: [],
        delivery_status: "completed",
        created_at: "2026-01-01T00:00:00Z",
        permission_requests: [],
      };
    }

    it("renders ## heading as h2, not literal ##", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg("## 二级标题")]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(container.querySelector("h2")).not.toBeNull();
      expect(screen.queryByText(/^##/)).toBeNull();
    });

    it("renders ### heading as h3, not literal ###", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg("### 三级标题")]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(container.querySelector("h3")).not.toBeNull();
      expect(screen.queryByText(/^###/)).toBeNull();
    });

    it("renders --- as <hr>, not literal ---", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg("above\n\n---\n\nbelow")]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(container.querySelector("hr")).not.toBeNull();
      expect(screen.queryByText("---")).toBeNull();
    });

    it("renders > blockquote as <blockquote>, not literal >", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg("> 引用文本")]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(container.querySelector("blockquote")).not.toBeNull();
      expect(screen.queryByText(/^>/)).toBeNull();
    });

    it("renders unclosed fenced code block as <pre><code>, not prose", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg("```python\nprint('hello')\nx = 1")]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(container.querySelector("pre > code")).not.toBeNull();
      // Content should not be squashed into one prose paragraph
      expect(screen.queryByText(/```python/)).toBeNull();
    });

    it("renders nested list with indented sub-items", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg("- 顶层\n  - 子项")]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      // nested list: ul > li > ul
      const nestedUl = container.querySelector("ul ul");
      expect(nestedUl).not.toBeNull();
    });

    it("renders [text](url) as <a> link, not literal brackets", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg("[点击这里](https://example.com)")]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      const anchor = container.querySelector("a");
      expect(anchor).not.toBeNull();
      expect(anchor?.getAttribute("href")).toBe("https://example.com");
      expect(screen.queryByText(/\[点击这里\]/)).toBeNull();
    });

    it("renders <script> as escaped text, not executed", () => {
      const { container } = render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[agentMsg('<script>alert("xss")</script>')]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      // No actual <script> element should exist in DOM
      expect(container.querySelector("script")).toBeNull();
    });

    // mention 在各类块级元素内的渲染（bugfix-413 关键回归点）
    describe("@mention inside block-level elements", () => {
      const PARTICIPANTS = [
        { type: "agent" as const, id: "a-planner", display_name: "Planner" },
        { type: "agent" as const, id: "a-coder", display_name: "Coder" },
      ];
      const CONV_WITH_PARTICIPANTS = {
        ...DIRECT_CONV,
        participants: PARTICIPANTS,
        participant_ids: ["a-planner", "a-coder"],
      };

      function agentMsgWithParticipants(content: string): Message {
        return { ...agentMsg(content), conversation_id: CONV_WITH_PARTICIPANTS.id };
      }

      it("renders mention chip inside a paragraph", () => {
        render(
          <MessagePane
            conversation={CONV_WITH_PARTICIPANTS}
            messages={[agentMsgWithParticipants('<mention type="agent" target_id="a-coder"/> 你怎么看？')]}
            mentionCandidates={[]}
            onSend={() => {}}
          />
        );
        expect(screen.getByText("@Coder")).toBeInTheDocument();
        expect(screen.queryByText(/<mention/)).toBeNull();
      });

      it("renders mention chip inside a heading", () => {
        render(
          <MessagePane
            conversation={CONV_WITH_PARTICIPANTS}
            messages={[agentMsgWithParticipants('## 请 <mention type="agent" target_id="a-coder"/> 审阅')]}
            mentionCandidates={[]}
            onSend={() => {}}
          />
        );
        expect(screen.getByText("@Coder")).toBeInTheDocument();
        expect(screen.queryByText(/<mention/)).toBeNull();
      });

      it("renders mention chip inside a blockquote", () => {
        render(
          <MessagePane
            conversation={CONV_WITH_PARTICIPANTS}
            messages={[agentMsgWithParticipants('> <mention type="agent" target_id="a-coder"/> 的意见')]}
            mentionCandidates={[]}
            onSend={() => {}}
          />
        );
        expect(screen.getByText("@Coder")).toBeInTheDocument();
      });

      it("renders mention chip inside a list item", () => {
        render(
          <MessagePane
            conversation={CONV_WITH_PARTICIPANTS}
            messages={[agentMsgWithParticipants('- <mention type="agent" target_id="a-coder"/> 负责此项')]}
            mentionCandidates={[]}
            onSend={() => {}}
          />
        );
        expect(screen.getByText("@Coder")).toBeInTheDocument();
      });

      it("renders unknown mention as --unknown chip inside block content", () => {
        const { container } = render(
          <MessagePane
            conversation={CONV_WITH_PARTICIPANTS}
            messages={[agentMsgWithParticipants('## <mention type="agent" target_id="nonexistent"/> 审阅')]}
            mentionCandidates={[]}
            onSend={() => {}}
          />
        );
        const unknownChip = container.querySelector(".chat-mention-chip--unknown");
        expect(unknownChip).not.toBeNull();
        expect(unknownChip?.textContent).toBe("@unknown");
      });

      // CR-1: CommonMark HTML block type-7 — mention 独占首行紧跟非空行时
      // remark-parse 将整段（mention行+后续文本）打包为单个 html 节点，
      // 旧 MENTION_FULL_RE 全锚定失配导致 mention 退化为字面量。
      it("renders mention chip when mention is on first line with no blank line before next text (type-7 html block)", () => {
        render(
          <MessagePane
            conversation={CONV_WITH_PARTICIPANTS}
            messages={[agentMsgWithParticipants('<mention type="agent" target_id="a-coder"/>\n正文继续')]}
            mentionCandidates={[]}
            onSend={() => {}}
          />
        );
        expect(screen.getByText("@Coder")).toBeInTheDocument();
        // Prose text after the mention must still appear
        expect(screen.getByText(/正文继续/)).toBeInTheDocument();
        expect(screen.queryByText(/<mention/)).toBeNull();
      });

      it("renders multiple mentions mixed with text in a single html node", () => {
        // Two mentions in the same block-level html node (no blank lines between)
        render(
          <MessagePane
            conversation={CONV_WITH_PARTICIPANTS}
            messages={[agentMsgWithParticipants(
              '<mention type="agent" target_id="a-coder"/> 和 <mention type="agent" target_id="a-planner"/> 请审阅'
            )]}
            mentionCandidates={[]}
            onSend={() => {}}
          />
        );
        expect(screen.getByText("@Coder")).toBeInTheDocument();
        expect(screen.getByText("@Planner")).toBeInTheDocument();
        expect(screen.queryByText(/<mention/)).toBeNull();
      });
    });
  });

  // bugfix-358 R6: MessageBubble renders <mention/> inline tags as MentionChip nodes
  describe("MessageBubble MentionChip rendering (bugfix-358)", () => {
    const GROUP_CONV_WITH_PARTICIPANTS: Conversation = {
      ...GROUP_CONV,
      id: "c-group-mention",
      participants: [
        { type: "user", id: "u1", display_name: "You" },
        { type: "agent", id: "a-planner", display_name: "Planner" },
        { type: "agent", id: "a-coder", display_name: "Coder" },
      ],
    };

    const AGENT_MSG_WITH_MENTION: Message = {
      id: "m-mention",
      conversation_id: "c-group-mention",
      sender: { type: "agent", id: "a-planner", display_name: "Planner" },
      sender_user_id: "a-planner",
      sender_type: "agent",
      content: '<mention type="agent" target_id="a-coder"/> 你怎么看？',
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-01-01T00:00:00Z",
      permission_requests: [],
    };

    it("renders mention tag as chip showing current display_name (not raw tag text)", () => {
      render(
        <MessagePane
          conversation={GROUP_CONV_WITH_PARTICIPANTS}
          messages={[AGENT_MSG_WITH_MENTION]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      // Should not show raw XML tag
      expect(screen.queryByText(/<mention/)).not.toBeInTheDocument();
      // Should show the display_name chip for the mentioned agent
      expect(screen.getByText("@Coder")).toBeInTheDocument();
    });

    it("renders unknown target_id as fallback @unknown text", () => {
      const msg: Message = {
        ...AGENT_MSG_WITH_MENTION,
        id: "m-unknown",
        content: '<mention type="agent" target_id="nonexistent-agent"/> hello',
      };
      render(
        <MessagePane
          conversation={GROUP_CONV_WITH_PARTICIPANTS}
          messages={[msg]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      // Unknown target: should degrade gracefully (not throw, not show raw tag)
      expect(screen.queryByText(/<mention/)).not.toBeInTheDocument();
    });

    it("renders plain text content unchanged when no mention tags present", () => {
      const msg: Message = {
        ...AGENT_MSG_WITH_MENTION,
        id: "m-plain",
        content: "regular message without any mention",
      };
      render(
        <MessagePane
          conversation={GROUP_CONV_WITH_PARTICIPANTS}
          messages={[msg]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );
      expect(screen.getByText("regular message without any mention")).toBeInTheDocument();
    });
  });

  // feat-414-M1 W1: running 气泡 status 行随时间推进显示实时 tick 秒数
  describe("feat-414-M1 · running tick (W1)", () => {
    it("advances the running tick text after 6 seconds", () => {
      vi.useFakeTimers();
      const NOW = new Date("2026-01-01T10:00:00Z").getTime();
      vi.setSystemTime(NOW);

      const RUNNING_MSG: Message = {
        id: "m-running-tick",
        conversation_id: "c1",
        sender: { type: "agent", id: "a-planner", display_name: "Planner" },
        sender_user_id: "u1",
        sender_type: "agent",
        content: "Processing…",
        attachments: [],
        delivery_status: "running",
        // created_at = 3s before NOW so initial tick starts at 3s
        created_at: new Date(NOW - 3000).toISOString(),
        permission_requests: []
      };

      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[RUNNING_MSG]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );

      // Advance clock by 6 seconds → tick should reach ~9s from created_at
      vi.advanceTimersByTime(6000);

      // Status row should contain a digit-seconds pattern (e.g. "9s")
      const statusRow = screen.getByTestId(`message-timestamp-m-running-tick`).closest("div")!;
      expect(statusRow.textContent).toMatch(/\d+s/);

      vi.useRealTimers();
    });
  });

  // feat-414-M1 W2: 用户气泡不显示 ⏱ 耗时（sender_type=user 无 elapsed）
  describe("feat-414-M1 · user bubble no elapsed (W2)", () => {
    it("does not render message-elapsed testid for a user message", () => {
      const USER_MSG: Message = {
        id: "m-user-no-elapsed",
        conversation_id: "c1",
        sender: { type: "user", id: "u1", display_name: "You" },
        sender_user_id: "u1",
        sender_type: "user",
        content: "User message",
        attachments: [],
        delivery_status: "completed",
        elapsed_ms: 1234, // even if elapsed_ms is set, user bubble must not display it
        created_at: "2026-01-01T00:00:00Z",
        permission_requests: []
      };

      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[USER_MSG]}
          mentionCandidates={[]}
          onSend={() => {}}
        />
      );

      expect(
        screen.queryByTestId("message-elapsed-m-user-no-elapsed")
      ).toBeNull();
    });
  });

  // feat-430: slash picker integration in the composer (single + group chat).
  describe("slash picker (feat-430)", () => {
    const SLASH_SKILLS = [
      { kind: "skill" as const, name: "pr-review", description: "review", location: "/a", fromAgents: ["Planner"] },
      { kind: "skill" as const, name: "doc", description: "docs", location: "/b", fromAgents: ["Planner"] },
    ];

    it("opens the slash picker with /stop and skills when typing '/' at the start", async () => {
      const user = userEvent.setup();
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[]}
          mentionCandidates={[]}
          slashSkills={SLASH_SKILLS}
          onSend={() => {}}
        />
      );
      await user.type(screen.getByRole("textbox"), "/");
      expect(await screen.findByText("/stop")).toBeInTheDocument();
      expect(screen.getByText("pr-review")).toBeInTheDocument();
    });

    it("does not open the picker when '/' is in the middle of the text", async () => {
      const user = userEvent.setup();
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[]}
          mentionCandidates={[]}
          slashSkills={SLASH_SKILLS}
          onSend={() => {}}
        />
      );
      await user.type(screen.getByRole("textbox"), "hello /world");
      expect(screen.queryByText("/stop")).not.toBeInTheDocument();
    });

    it("inserts /skill:name when a skill is selected", async () => {
      const user = userEvent.setup();
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[]}
          mentionCandidates={[]}
          slashSkills={SLASH_SKILLS}
          onSend={() => {}}
        />
      );
      const box = screen.getByRole("textbox") as HTMLTextAreaElement;
      await user.type(box, "/pr");
      await user.click(await screen.findByText("pr-review"));
      expect(box.value).toBe("/skill:pr-review ");
    });

    it("Esc closes the picker but keeps the typed '/' text", async () => {
      const user = userEvent.setup();
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[]}
          mentionCandidates={[]}
          slashSkills={SLASH_SKILLS}
          onSend={() => {}}
        />
      );
      const box = screen.getByRole("textbox") as HTMLTextAreaElement;
      await user.type(box, "/pr");
      expect(await screen.findByText("pr-review")).toBeInTheDocument();
      await user.keyboard("{Escape}");
      expect(screen.queryByText("pr-review")).not.toBeInTheDocument();
      expect(box.value).toBe("/pr");
    });

    it("opens the picker in a group conversation too", async () => {
      const user = userEvent.setup();
      render(
        <MessagePane
          conversation={GROUP_CONV}
          messages={[]}
          mentionCandidates={MENTION_CANDIDATES}
          slashSkills={SLASH_SKILLS}
          onSend={() => {}}
        />
      );
      await user.type(screen.getByRole("textbox"), "/");
      expect(await screen.findByText("/stop")).toBeInTheDocument();
    });

    // R5-S3: editing an already-inserted `/skill:doc` down to `/skill:d` re-opens the
    // picker and re-filters skills by the `d` prefix (not the literal `skill:d` query).
    it("re-filters skills when editing a /skill: prefix for correction", async () => {
      const user = userEvent.setup();
      render(
        <MessagePane
          conversation={DIRECT_CONV}
          messages={[]}
          mentionCandidates={[]}
          slashSkills={SLASH_SKILLS}
          onSend={() => {}}
        />
      );
      const box = screen.getByRole("textbox") as HTMLTextAreaElement;
      // Simulate the corrected state `/skill:d` (after deleting chars from `/skill:doc`).
      await user.type(box, "/skill:d");
      // `doc` matches the `d` prefix; `/stop` must NOT show (skill-only namespace).
      expect(await screen.findByText("doc")).toBeInTheDocument();
      expect(screen.queryByText("/stop")).not.toBeInTheDocument();
      expect(screen.queryByText("pr-review")).not.toBeInTheDocument();
    });
  });
});
