import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { i18n } from "../../../i18n";
import { NewGroupModal } from "./new-group-modal";

const AGENTS = [
  { agent_id: "agent-a", display_name: "Assistant", description: "Coding partner" },
  { agent_id: "agent-b", display_name: "Planner", description: "Sprint planner" },
  { agent_id: "agent-c", display_name: "Reviewer", description: "Reviewer" }
];

describe("NewGroupModal", () => {
  it.each(["en", "zh"])("shows machine identity and translated presence in %s", async (locale) => {
    await act(async () => { await i18n.changeLanguage(locale); });
    try {
      render(<NewGroupModal agents={[
        { agent_id: "a", display_name: "Assistant", node_name: "mac-mini", status: "online" },
        { agent_id: "b", display_name: "Planner", node_name: "macbook-air", status: "offline" }
      ]} onClose={() => {}} onCreate={() => {}} />);
      expect(screen.getByText("mac-mini")).toBeVisible();
      expect(screen.getByText("macbook-air")).toBeVisible();
      expect(screen.getByText(locale === "en" ? "online" : "在线")).toBeVisible();
      expect(screen.getByText(locale === "en" ? "offline" : "离线")).toBeVisible();
    } finally {
      await act(async () => { await i18n.changeLanguage("en"); });
    }
  });
  it("Create is disabled until at least one agent is selected", async () => {
    const user = userEvent.setup();
    render(<NewGroupModal agents={AGENTS} onClose={() => {}} onCreate={() => {}} />);
    const create = screen.getByRole("button", { name: /Create group/ });
    expect(create).toBeDisabled();
    await user.click(screen.getByLabelText(/Assistant/));
    expect(create).toBeEnabled();
  });

  it("invokes onCreate with selected agent ids and the trimmed group name", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    render(<NewGroupModal agents={AGENTS} onClose={() => {}} onCreate={onCreate} />);
    await user.click(screen.getByLabelText(/Assistant/));
    await user.click(screen.getByLabelText(/Planner/));
    await user.type(screen.getByLabelText(/Group name/), "  Sprint  ");
    await user.click(screen.getByRole("button", { name: /Create group/ }));
    expect(onCreate).toHaveBeenCalledWith({ agentIds: ["agent-a", "agent-b"], name: "Sprint" });
  });

  it("falls back to a comma-joined participant name when no group name is given", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    render(<NewGroupModal agents={AGENTS} onClose={() => {}} onCreate={onCreate} />);
    await user.click(screen.getByLabelText(/Planner/));
    await user.click(screen.getByLabelText(/Reviewer/));
    expect(screen.getByLabelText(/Group name/)).toHaveAttribute("placeholder", "Planner, Reviewer");
    await user.click(screen.getByRole("button", { name: /Create group/ }));
    expect(onCreate).toHaveBeenCalledWith({ agentIds: ["agent-b", "agent-c"], name: "Planner, Reviewer" });
  });

  it("invokes onClose when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<NewGroupModal agents={AGENTS} onClose={onClose} onCreate={() => {}} />);
    await user.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(onClose).toHaveBeenCalled();
  });
});
