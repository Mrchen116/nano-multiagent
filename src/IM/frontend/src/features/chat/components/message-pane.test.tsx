import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ConversationDetail } from "../types";
import { MessagePane } from "./message-pane";

const SEND_FAILURE_MESSAGE = "No relay node is available. Connect an online node and retry.";

function renderMessagePane(input?: { onSend?: (content: string) => Promise<unknown> }) {
  const detail: ConversationDetail = {
    conversation_id: "conv-kernel-ops",
    title: "Kernel Ops Crew",
    messages: []
  };

  const onSend = input?.onSend ?? (async () => undefined);

  return render(
    <MemoryRouter>
      <MessagePane
        detail={detail}
        isMobile={false}
        isSending={false}
        canSend
        helperText={null}
        sendPlaceholder="Type message"
        onSend={onSend}
      />
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
