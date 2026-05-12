import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { Attachment, Conversation, MentionCandidate, Message } from "../chat-types";
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
});
