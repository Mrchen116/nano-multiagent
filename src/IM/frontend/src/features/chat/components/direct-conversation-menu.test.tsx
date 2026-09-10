import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import "../../../i18n";
import { DirectConversationMenu } from "./direct-conversation-menu";

async function openRename() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Conversation menu" }));
  await user.click(screen.getByRole("menuitem", { name: "Rename" }));
  return user;
}

describe("private conversation menu", () => {
  it("keeps the Agent configuration action and supports keyboard dismissal", async () => {
    const configure = vi.fn();
    const user = userEvent.setup();
    render(<DirectConversationMenu title="Original" onRename={vi.fn()} onOpenConfig={configure} />);
    const trigger = screen.getByRole("button", { name: "Conversation menu" });
    await user.click(trigger);
    expect(screen.getByRole("menuitem", { name: "Rename" })).toHaveFocus();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(configure).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await user.click(trigger);
    await user.keyboard("{Escape}");
    expect(trigger).toHaveFocus();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("prefills the title, rejects blank names and saves trimmed input", async () => {
    const rename = vi.fn().mockResolvedValue(undefined);
    render(<DirectConversationMenu title="Original" onRename={rename} />);
    const user = await openRename();
    const input = screen.getByRole("textbox", { name: "Conversation name" });
    expect(input).toHaveValue("Original");
    expect(input).toHaveFocus();
    await user.clear(input);
    await user.type(input, "   ");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    await user.type(input, "Travel plans  ");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(rename).toHaveBeenCalledWith("Travel plans");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Conversation menu" })).toHaveFocus();
  });

  it("retains failed input for retry and prevents duplicate saves while pending", async () => {
    let resolve: () => void = () => {};
    const rename = vi.fn().mockRejectedValueOnce(new Error("Connection failed"))
      .mockImplementationOnce(() => new Promise<void>((done) => { resolve = done; }));
    render(<DirectConversationMenu title="Original" onRename={rename} />);
    const user = await openRename();
    const input = screen.getByRole("textbox", { name: "Conversation name" });
    await user.clear(input);
    await user.type(input, "Resume");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save. Please try again.");
    expect(input).toHaveValue("Resume");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    resolve();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(rename).toHaveBeenCalledTimes(2);
  });

  it("cancels without saving and omits configuration when no Agent is associated", async () => {
    const rename = vi.fn();
    render(<DirectConversationMenu title="Original" onRename={rename} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Conversation menu" }));
    expect(screen.queryByRole("menuitem", { name: "Agent configuration" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(rename).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
