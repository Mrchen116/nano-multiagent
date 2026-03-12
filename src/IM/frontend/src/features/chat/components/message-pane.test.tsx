import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { getSendAvailabilityMessages, SendAvailability } from "../im-chat-api";
import { ConversationDetail } from "../types";
import { MessagePane } from "./message-pane";

const SEND_FAILURE_MESSAGE = "Chat unavailable. No online relay node is available for this chat. Connect an online node and retry.";
const DEFAULT_SEND_AVAILABILITY = {
  canSend: true,
  state: "available" as const,
  helperText: null,
  placeholder: getSendAvailabilityMessages().enabledPlaceholder
};

function renderMessagePane(input?: {
  onSend?: (content: string) => Promise<unknown>;
  sendAvailability?: SendAvailability;
}) {
  const detail: ConversationDetail = {
    conversation_id: "conv-kernel-ops",
    title: "Kernel Ops Crew",
    messages: []
  };

  const onSend = input?.onSend ?? (async () => undefined);
  const sendAvailability = input?.sendAvailability ?? DEFAULT_SEND_AVAILABILITY;

  return render(
    <MemoryRouter>
      <MessagePane detail={detail} isMobile={false} isSending={false} sendAvailability={sendAvailability} onSend={onSend} />
    </MemoryRouter>
  );
}

describe("message pane", () => {
  it("preserves the draft and shows explicit failure feedback when send fails", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockRejectedValue(new Error(SEND_FAILURE_MESSAGE));

    renderMessagePane({ onSend });

    const composer = screen.getByPlaceholderText("Type message");
    await user.type(composer, "ping the agent");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("ping the agent");
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

    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
    expect(composer).toHaveValue("");
  });
});
