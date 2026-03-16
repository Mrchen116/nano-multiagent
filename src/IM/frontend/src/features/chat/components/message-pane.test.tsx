import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { getSendAvailabilityMessages, SendAvailability } from "../im-chat-api";
import { ChatAttachment, ChatUsageView, ConversationDetail, MentionCandidate } from "../types";
import { MessagePane } from "./message-pane";

const SEND_FAILURE_MESSAGE = "Chat unavailable. No online relay node is available for this chat. Connect an online node and retry.";
const DEFAULT_SEND_AVAILABILITY = {
  canSend: true,
  state: "available" as const,
  helperText: null,
  placeholder: getSendAvailabilityMessages().enabledPlaceholder
};
const DEFAULT_USAGE: ChatUsageView = {
  conversation: {
    turns: 2,
    promptTokens: 8,
    completionTokens: 5,
    totalTokens: 13
  },
  workspace: {
    turns: 7,
    promptTokens: 21,
    completionTokens: 12,
    totalTokens: 33
  },
  agents: []
};

function renderMessagePane(input?: {
  onSend?: (payload: { content: string; attachments: ChatAttachment[] }) => Promise<unknown>;
  onUploadAttachment?: (file: File) => Promise<ChatAttachment>;
  sendAvailability?: SendAvailability;
  usage?: ChatUsageView;
  detail?: ConversationDetail;
}) {
  const detail: ConversationDetail = input?.detail ?? {
    conversation_id: "conv-kernel-ops",
    title: "Kernel Ops Crew",
    kind_label: "主 Agent 会话",
    ownership_label: "这是你与主 Agent 的默认产品入口。",
    messages: []
  };

  const onSend = input?.onSend ?? (async () => undefined);
  const onUploadAttachment = input?.onUploadAttachment ??
    (async (file: File) => ({
      url: `http://im.test/im/uploads/${file.name}`,
      file_name: file.name,
      content_type: file.type || "application/octet-stream"
    }));
  const sendAvailability = input?.sendAvailability ?? DEFAULT_SEND_AVAILABILITY;
  const usage = input?.usage ?? DEFAULT_USAGE;

  return render(
    <MemoryRouter>
      <MessagePane
        detail={detail}
        isMobile={false}
        isSending={false}
        isStartingFreshSession={false}
        sendAvailability={sendAvailability}
        usage={usage}
        onSend={onSend}
        onUploadAttachment={onUploadAttachment}
      />
    </MemoryRouter>
  );
}

describe("message pane", () => {
  it("shows main-agent session semantics in the header", () => {
    renderMessagePane();

    expect(screen.getByText("主 Agent 会话")).toBeInTheDocument();
    expect(screen.getByText("这是你与主 Agent 的默认产品入口。")).toBeInTheDocument();
  });

  it("shows per-agent usage tabs and switches the active agent totals", async () => {
    const user = userEvent.setup();

    renderMessagePane({
      usage: {
        ...DEFAULT_USAGE,
        agents: [
          {
            agentId: "agent-alpha",
            label: "Agent Alpha",
            totals: {
              turns: 1,
              promptTokens: 11,
              completionTokens: 7,
              totalTokens: 18
            }
          },
          {
            agentId: "agent-beta",
            label: "Agent Beta",
            totals: {
              turns: 2,
              promptTokens: 5,
              completionTokens: 9,
              totalTokens: 14
            }
          }
        ]
      }
    });

    expect(screen.getByRole("tab", { name: "Agent Alpha" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Agent · Agent Alpha")).toBeInTheDocument();
    expect(screen.getByText("Completion 7")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Agent Beta" }));

    expect(screen.getByRole("tab", { name: "Agent Beta" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Agent · Agent Beta")).toBeInTheDocument();
    expect(screen.getByText("Completion 9")).toBeInTheDocument();
  });

  it("shows group-chat mention candidates with product labels while keeping stable payload tokens", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    const mentionCandidates: MentionCandidate[] = [
      { agentId: "agent-alpha", label: "Agent Alpha" },
      { agentId: "agent-beta", label: "Agent Beta" }
    ];

    renderMessagePane({
      onSend,
      detail: {
        conversation_id: "conv-group",
        title: "Kernel Ops Crew",
        kind_label: "Group chat",
        target_label: "Multiple participants",
        discoverability_hint: "Shared thread",
        messages: [],
        mention_candidates: mentionCandidates
      }
    });

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "@a");

    expect(screen.getByRole("listbox", { name: "Mention candidates" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Agent Alpha/i })).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowDown}{Enter}");

    expect(composer).toHaveValue("@Agent Beta ");
    expect(composer).not.toHaveValue("@agent:agent-beta ");
    expect(screen.queryByText(/@agent:/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("listbox", { name: "Mention candidates" })).not.toBeInTheDocument();

    await user.type(composer, "please investigate");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith({
      content: "@agent:agent-beta please investigate",
      attachments: []
    });
  });

  it("opens mention candidates after existing text, supports a second mention, and keeps stable payload tokens", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    const mentionCandidates: MentionCandidate[] = [
      { agentId: "agent-alpha", label: "Agent Alpha" },
      { agentId: "agent-beta", label: "Agent Beta" }
    ];

    renderMessagePane({
      onSend,
      detail: {
        conversation_id: "conv-group-second-mention",
        title: "Kernel Ops Crew",
        kind_label: "Group chat",
        target_label: "Multiple participants",
        discoverability_hint: "Shared thread",
        messages: [],
        mention_candidates: mentionCandidates
      }
    });

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "hello team @");

    expect(screen.getByRole("listbox", { name: "Mention candidates" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Agent Alpha/i })).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{Enter}");
    expect(composer).toHaveValue("hello team @Agent Alpha ");

    await user.type(composer, "and @b");

    expect(screen.getByRole("listbox", { name: "Mention candidates" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Agent Beta/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText(/@agent:/i)).not.toBeInTheDocument();

    await user.keyboard("{Enter}");
    expect(composer).toHaveValue("hello team @Agent Alpha and @Agent Beta ");

    await user.type(composer, "please investigate");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith({
      content: "hello team @agent:agent-alpha and @agent:agent-beta please investigate",
      attachments: []
    });
  });

  it("deletes an inserted mention token as a whole on backspace", async () => {
    const user = userEvent.setup();
    const mentionCandidates: MentionCandidate[] = [
      { agentId: "agent-alpha", label: "Agent Alpha" },
      { agentId: "agent-beta", label: "Agent Beta" }
    ];

    renderMessagePane({
      detail: {
        conversation_id: "conv-group-delete-mention",
        title: "Kernel Ops Crew",
        kind_label: "Group chat",
        target_label: "Multiple participants",
        discoverability_hint: "Shared thread",
        messages: [],
        mention_candidates: mentionCandidates
      }
    });

    const composer = screen.getByPlaceholderText("Type message") as HTMLTextAreaElement;
    await user.type(composer, "hello @a");
    await user.keyboard("{Enter}");
    expect(composer).toHaveValue("hello @Agent Alpha ");

    composer.setSelectionRange(composer.value.length, composer.value.length);
    await user.keyboard("{Backspace}");

    expect(composer).toHaveValue("hello ");
    expect(screen.queryByRole("listbox", { name: "Mention candidates" })).not.toBeInTheDocument();
  });

  it("does not open mention candidates for direct chat composers", async () => {
    const user = userEvent.setup();

    renderMessagePane({
      detail: {
        conversation_id: "conv-direct",
        title: "Agent Alpha",
        kind_label: "Direct agent chat",
        target_label: "Agent Alpha",
        messages: [],
        mention_candidates: [{ agentId: "agent-alpha", label: "Agent Alpha" }]
      }
    });

    await user.type(screen.getByPlaceholderText("Type message"), "@a");

    expect(screen.queryByRole("listbox", { name: "Mention candidates" })).not.toBeInTheDocument();
  });

  it("preserves the draft and shows explicit failure feedback when send fails", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockRejectedValue(new Error(SEND_FAILURE_MESSAGE));

    renderMessagePane({ onSend });

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "ping the agent");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith({ content: "ping the agent", attachments: [] });
    expect(await screen.findByRole("alert")).toHaveTextContent(SEND_FAILURE_MESSAGE);
    expect(screen.getByDisplayValue("ping the agent")).toBeInTheDocument();
  });

  it("normalizes raw relay 503 errors into a user-facing relay availability hint", async () => {
    const user = userEvent.setup();
    const onSend = vi
      .fn()
      .mockRejectedValue(new Error("POST /im/v1/conversations/conv-kernel-ops/messages failed: 503 (target_node_id is not connected)"));

    renderMessagePane({ onSend });

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "retry the relay path");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(SEND_FAILURE_MESSAGE);
    expect(screen.getByDisplayValue("retry the relay path")).toBeInTheDocument();
  });

  it("shows the unified offline failure banner before send", () => {
    renderMessagePane({
      sendAvailability: {
        canSend: false,
        state: "offline",
        helperText: "Your bound Gateway is offline. Bring that node online or bind another online node to re-enable chat.",
        placeholder: "Gateway offline — chat disabled"
      }
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Chat unavailable");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your bound Gateway is offline. Bring that node online or bind another online node to re-enable chat."
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Next: Bring Gateway online");
    expect(screen.getByPlaceholderText("Gateway offline — chat disabled")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("clears failure feedback after a successful retry", async () => {
    const user = userEvent.setup();
    const onSend = vi
      .fn()
      .mockRejectedValueOnce(new Error(SEND_FAILURE_MESSAGE))
      .mockResolvedValueOnce(undefined);

    renderMessagePane({ onSend });

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "retry with node online");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(SEND_FAILURE_MESSAGE);

    await user.click(screen.getByRole("button", { name: "Retry send" }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
    expect(composer).toHaveValue("");
  });

  it("supports multiline drafts with Shift+Enter and sends on Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);

    renderMessagePane({ onSend });

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "line one");
    await user.keyboard("{Shift>}{Enter}{/Shift}line two");

    expect(composer).toHaveValue("line one\nline two");

    await user.keyboard("{Enter}");

    expect(onSend).toHaveBeenCalledWith({
      content: "line one\nline two",
      attachments: []
    });
  });

  it("uploads attachments from the composer and sends them with the message", async () => {
    const user = userEvent.setup();
    const uploadedAttachment: ChatAttachment = {
      url: "http://im.test/im/uploads/uploaded-demo.txt",
      file_name: "demo.txt",
      content_type: "text/plain"
    };
    const onUploadAttachment = vi.fn().mockResolvedValue(uploadedAttachment);
    const onSend = vi.fn().mockResolvedValue(undefined);

    renderMessagePane({ onSend, onUploadAttachment });

    await user.upload(
      screen.getByLabelText("Attachment picker"),
      new File(["demo attachment"], "demo.txt", { type: "text/plain" })
    );

    expect(onUploadAttachment).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("demo.txt")).toBeInTheDocument();

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "see uploaded file");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith({
      content: "see uploaded file",
      attachments: [uploadedAttachment]
    });
    await waitFor(() => {
      expect(screen.queryByText("demo.txt")).not.toBeInTheDocument();
    });
  });

  it("lets users remove uploaded attachments before sending", async () => {
    const user = userEvent.setup();
    const uploadedAttachment: ChatAttachment = {
      url: "http://im.test/im/uploads/uploaded-demo.txt",
      file_name: "demo.txt",
      content_type: "text/plain"
    };
    const onUploadAttachment = vi.fn().mockResolvedValue(uploadedAttachment);
    const onSend = vi.fn().mockResolvedValue(undefined);

    renderMessagePane({ onSend, onUploadAttachment });

    await user.upload(
      screen.getByLabelText("Attachment picker"),
      new File(["demo attachment"], "demo.txt", { type: "text/plain" })
    );

    expect(await screen.findByText("demo.txt")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove attachment demo.txt" }));

    expect(screen.queryByText("demo.txt")).not.toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Type message"), "send without file");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith({
      content: "send without file",
      attachments: []
    });
  });

  it("shows upload failure feedback and lets users retry the same file", async () => {
    const user = userEvent.setup();
    const uploadedAttachment: ChatAttachment = {
      url: "http://im.test/im/uploads/uploaded-retry.txt",
      file_name: "retry.txt",
      content_type: "text/plain"
    };
    const onUploadAttachment = vi
      .fn()
      .mockRejectedValueOnce(new Error("upload unavailable"))
      .mockResolvedValueOnce(uploadedAttachment);

    renderMessagePane({ onUploadAttachment });

    await user.upload(
      screen.getByLabelText("Attachment picker"),
      new File(["retry attachment"], "retry.txt", { type: "text/plain" })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't upload retry.txt.");
    expect(screen.getByRole("button", { name: "Retry upload retry.txt" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry upload retry.txt" }));

    await waitFor(() => {
      expect(onUploadAttachment).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText("retry.txt")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry upload retry.txt" })).not.toBeInTheDocument();
  });

  it("renders understandable message status and recovery copy", () => {
    renderMessagePane({
      detail: {
        conversation_id: "conv-status",
        title: "Status thread",
        messages: [
          {
            message_id: "msg-sent",
            sender_type: "user",
            sender_name: "You",
            is_mine: true,
            content: "sent message",
            created_at: "2026-03-14T00:00:00Z",
            delivery_status: "sent"
          },
          {
            message_id: "msg-running",
            sender_type: "agent",
            sender_name: "OpsBot",
            content: "running message",
            created_at: "2026-03-14T00:01:00Z",
            delivery_status: "running"
          },
          {
            message_id: "msg-completed",
            sender_type: "agent",
            sender_name: "OpsBot",
            content: "completed message",
            created_at: "2026-03-14T00:02:00Z",
            delivery_status: "completed"
          },
          {
            message_id: "msg-failed",
            sender_type: "user",
            sender_name: "You",
            is_mine: true,
            content: "failed message",
            created_at: "2026-03-14T00:03:00Z",
            delivery_status: "failed"
          },
          {
            message_id: "msg-agent-failed",
            sender_type: "agent",
            sender_name: "OpsBot",
            content: "agent failed message",
            created_at: "2026-03-14T00:04:00Z",
            delivery_status: "failed",
            recovery_action_label: "Retry request",
            recovery_hint: "The agent stopped before finishing this turn. Retry the request to ask the agent again."
          }
        ]
      }
    });

    expect(screen.getByText("Sent to relay")).toBeInTheDocument();
    expect(screen.getByText("Your message left this device and is waiting for agent work.")).toBeInTheDocument();
    expect(screen.getByText("Agent is working")).toBeInTheDocument();
    expect(screen.getByText("The relay accepted your request and the agent is still processing it.")).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.queryByText("Agent replied")).not.toBeInTheDocument();
    expect(screen.queryByText("The latest agent response finished successfully.")).not.toBeInTheDocument();
    expect(screen.getByText("Didn't send")).toBeInTheDocument();
    expect(screen.getByText("The message did not reach the relay. Retry after the connection is back.")).toBeInTheDocument();
    expect(screen.getByText("Agent couldn't finish")).toBeInTheDocument();
    expect(screen.getByText("The agent stopped before finishing this turn. Retry the request to ask the agent again.")).toBeInTheDocument();
    expect(screen.getByText("Recovery: Retry request")).toBeInTheDocument();
  });
});
