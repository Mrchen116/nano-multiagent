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
  it("keeps a personal assistant group private before and after submission", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    render(<NewGroupModal agents={[{ agent_id: "personal", display_name: "My assistant", space_id: "personal:owner" }]}
      onClose={() => {}} onCreate={onCreate} />);
    await user.click(screen.getByLabelText("My assistant"));
    expect(screen.getByLabelText("Visibility")).toHaveValue("private");
    expect(screen.getByLabelText("Visibility")).toBeDisabled();
    expect(screen.getByText(/stay private in your personal space/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Create group/ }));
    expect(onCreate).toHaveBeenCalledWith({ agentIds: ["personal"], userIds: [], name: "My assistant", visibility: "private" });
    await user.click(screen.getByLabelText("My assistant"));
    expect(screen.getByLabelText("Visibility")).toBeEnabled();
    expect(screen.getByLabelText("Visibility")).toHaveValue("public");
  });
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
    expect(screen.getByLabelText("Visibility")).toHaveValue("public");
    await user.selectOptions(screen.getByLabelText("Visibility"), "private");
    await user.type(screen.getByLabelText(/Group name/), "  Sprint  ");
    await user.click(screen.getByRole("button", { name: /Create group/ }));
    expect(onCreate).toHaveBeenCalledWith({ agentIds: ["agent-a", "agent-b"], userIds: [], visibility: "private", name: "Sprint" });
  });

  it("falls back to a comma-joined participant name when no group name is given", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    render(<NewGroupModal agents={AGENTS} onClose={() => {}} onCreate={onCreate} />);
    await user.click(screen.getByLabelText(/Planner/));
    await user.click(screen.getByLabelText(/Reviewer/));
    expect(screen.getByLabelText(/Group name/)).toHaveAttribute("placeholder", "Planner, Reviewer");
    await user.click(screen.getByRole("button", { name: /Create group/ }));
    expect(onCreate).toHaveBeenCalledWith({ agentIds: ["agent-b", "agent-c"], userIds: [], visibility: "public", name: "Planner, Reviewer" });
  });

  it("invokes onClose when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<NewGroupModal agents={AGENTS} onClose={onClose} onCreate={() => {}} />);
    await user.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(onClose).toHaveBeenCalled();
  });

  it("groups human colleagues first and displays @username instead of internal UUIDs", async () => {
    const user = userEvent.setup();
    render(
      <NewGroupModal
        agents={[
          { agent_id: "agent-a", display_name: "Assistant", kind: "agent", node_name: "mac-mini", status: "online" },
          { agent_id: "uuid-9999-hidden", display_name: "Lin Xia", username: "linxia", kind: "human" }
        ]}
        onClose={() => {}}
        onCreate={() => {}}
      />
    );
    expect(screen.getByText("People")).toBeVisible();
    expect(screen.getByText("My Agents")).toBeVisible();
    expect(screen.getByText("@linxia")).toBeVisible();
    expect(screen.queryByText("uuid-9999-hidden")).toBeNull();
    await user.type(screen.getByRole("searchbox"), "@linxia");
    expect(screen.getByLabelText("Lin Xia")).toBeVisible();
    expect(screen.queryByLabelText("Assistant")).toBeNull();
  });

  it("enforces mutual exclusion between private (owner_only) agents and human teammates and locks visibility to private", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    render(
      <NewGroupModal
        agents={[
          { agent_id: "u-colleague", display_name: "Lin Xia", username: "linxia", kind: "human" },
          { agent_id: "priv-agent", display_name: "Secret Writer", kind: "agent", collaboration_scope: "owner_only" },
          { agent_id: "team-agent", display_name: "Public Planner", kind: "agent", collaboration_scope: "team" }
        ]}
        onClose={() => {}}
        onCreate={onCreate}
      />
    );
    expect(screen.getByText("Private")).toBeVisible();
    // Selecting a private agent locks visibility to private and disables human teammates, while allowing same-owner team agents.
    await user.click(screen.getByLabelText("Secret Writer"));
    expect(screen.getByLabelText("Visibility")).toHaveValue("private");
    expect(screen.getByLabelText("Visibility")).toBeDisabled();
    expect(screen.getByLabelText("Lin Xia")).toBeDisabled();
    expect(screen.getByText("Unavailable while a private assistant is selected")).toBeVisible();
    expect(screen.getByLabelText("Public Planner")).toBeEnabled();

    // Unselecting the private agent and selecting a human teammate disables the private agent.
    await user.click(screen.getByLabelText("Secret Writer"));
    expect(screen.getByLabelText("Lin Xia")).toBeEnabled();
    await user.click(screen.getByLabelText("Lin Xia"));
    expect(screen.getByLabelText("Secret Writer")).toBeDisabled();
    expect(screen.getByText("Unavailable while a teammate is selected")).toBeVisible();
    await user.click(screen.getByLabelText("Public Planner"));
    await user.click(screen.getByRole("button", { name: /Create group/ }));
    expect(onCreate).toHaveBeenCalledWith({
      agentIds: ["team-agent"],
      userIds: ["u-colleague"],
      visibility: "public",
      name: "Lin Xia, Public Planner"
    });
  });

  it("locks visibility to private when a project agent is selected while keeping human teammates selectable", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    render(
      <NewGroupModal
        agents={[
          { agent_id: "u-colleague", display_name: "Lin Xia", username: "linxia", kind: "human" },
          { agent_id: "proj-agent", display_name: "Alpha Analyst", kind: "agent", collaboration_scope: "project" }
        ]}
        onClose={() => {}}
        onCreate={onCreate}
      />
    );
    expect(screen.getByText("Project")).toBeVisible();
    await user.click(screen.getByLabelText("Alpha Analyst"));
    expect(screen.getByLabelText("Visibility")).toHaveValue("private");
    expect(screen.getByLabelText("Visibility")).toBeDisabled();
    expect(screen.getByText(/Groups with a project assistant stay private/)).toBeVisible();
    // Human teammates remain selectable with a project assistant!
    expect(screen.getByLabelText("Lin Xia")).toBeEnabled();
    await user.click(screen.getByLabelText("Lin Xia"));
    await user.click(screen.getByRole("button", { name: /Create group/ }));
    expect(onCreate).toHaveBeenCalledWith({
      agentIds: ["proj-agent"],
      userIds: ["u-colleague"],
      visibility: "private",
      name: "Lin Xia, Alpha Analyst"
    });
  });
});
