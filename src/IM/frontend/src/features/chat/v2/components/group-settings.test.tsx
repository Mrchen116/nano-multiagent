import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import { GroupSettings, type GroupSettingsProps } from "./group-settings";

const MEMBERS: GroupSettingsProps["members"] = [
  { id: "user-1", userId: "user-1", type: "user", displayName: "Alex", isSelf: true, isCreator: true },
  { id: "planner", userId: "uuid-planner", type: "agent", displayName: "Planner", isSelf: false, isCreator: false, status: "online" },
  { id: "writer", userId: "uuid-writer", type: "agent", displayName: "Writer", isSelf: false, isCreator: false, status: "offline" }
];

const ADDABLE: GroupSettingsProps["addableAgents"] = [
  { agentId: "reviewer", displayName: "Reviewer", status: "online" }
];

function renderSettings(overrides: Partial<GroupSettingsProps> = {}) {
  const props: GroupSettingsProps = {
    title: "Research Squad",
    members: MEMBERS,
    addableAgents: ADDABLE,
    isMobile: false,
    onClose: vi.fn(),
    onRename: vi.fn(),
    onAddParticipants: vi.fn(),
    onRemoveParticipant: vi.fn(),
    onDissolve: vi.fn(),
    onOpenAgentConfig: vi.fn(),
    ...overrides
  };
  render(<GroupSettings {...props} />);
  return props;
}

describe("GroupSettings (desktop drawer)", () => {
  it("lists every member with the creator tag on self", () => {
    renderSettings();
    expect(screen.getByText("Alex")).toBeInTheDocument();
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("Writer")).toBeInTheDocument();
    // The self/creator row is tagged.
    expect(screen.getByText(/Creator/i)).toBeInTheDocument();
  });

  it("clicking an agent member opens that agent's config", async () => {
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByText("Planner"));
    expect(props.onOpenAgentConfig).toHaveBeenCalledWith("planner");
  });

  it("rename: empty name disables save; a new name calls onRename trimmed", async () => {
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByRole("button", { name: /Rename/i }));
    const input = screen.getByLabelText(/Group name/i);
    await user.clear(input);
    expect(screen.getByRole("button", { name: /^Save$/i })).toBeDisabled();
    await user.type(input, "  New Name  ");
    const save = screen.getByRole("button", { name: /^Save$/i });
    expect(save).toBeEnabled();
    await user.click(save);
    expect(props.onRename).toHaveBeenCalledWith("New Name");
  });

  it("add members: lists addable agents, selecting + confirming calls onAddParticipants", async () => {
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByRole("button", { name: /Add members/i }));
    await user.click(screen.getByLabelText("Reviewer"));
    await user.click(screen.getByRole("button", { name: /^Add/i }));
    expect(props.onAddParticipants).toHaveBeenCalledWith(["reviewer"]);
  });

  it("add members: empty candidate set shows an empty state", async () => {
    const user = userEvent.setup();
    renderSettings({ addableAgents: [] });
    await user.click(screen.getByRole("button", { name: /Add members/i }));
    expect(screen.getByText(/No agents available to add/i)).toBeInTheDocument();
  });

  it("remove: confirming passes the participant's user_id (not agent id)", async () => {
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByRole("button", { name: "Remove Planner" }));
    await user.click(screen.getByRole("button", { name: /^Remove$/i }));
    expect(props.onRemoveParticipant).toHaveBeenCalledWith("uuid-planner");
  });

  it("dissolve: requires a confirm then calls onDissolve", async () => {
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByRole("button", { name: /Dissolve group/i }));
    expect(props.onDissolve).not.toHaveBeenCalled();
    // A confirm affordance appears; clicking it dissolves.
    const confirm = screen.getByTestId("group-settings-dissolve-confirm");
    await user.click(within(confirm).getByRole("button", { name: /Dissolve group/i }));
    expect(props.onDissolve).toHaveBeenCalled();
  });

  it("close button calls onClose", async () => {
    const user = userEvent.setup();
    const props = renderSettings();
    await user.click(screen.getByRole("button", { name: /Close/i }));
    expect(props.onClose).toHaveBeenCalled();
  });

  // round-1 fix #1: a failed write must be visible inside the panel (the global
  // toast is hidden behind the scrim), and the user's pending action is preserved.
  it("surfaces an inline error when a remove fails and keeps the confirm open", async () => {
    const user = userEvent.setup();
    const onRemoveParticipant = vi.fn().mockRejectedValue(new Error("network boom"));
    renderSettings({ onRemoveParticipant });
    await user.click(screen.getByRole("button", { name: "Remove Planner" }));
    await user.click(screen.getByRole("button", { name: /^Remove$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/network boom/i);
    // The confirm stays so the user can retry.
    expect(screen.getByText(/Remove this member/i)).toBeInTheDocument();
  });

  // round-1 fix #4: a failed add keeps the selection (it is only cleared on success).
  it("keeps the selection and shows an error when add fails", async () => {
    const user = userEvent.setup();
    const onAddParticipants = vi.fn().mockRejectedValue(new Error("add failed"));
    renderSettings({ onAddParticipants });
    await user.click(screen.getByRole("button", { name: /Add members/i }));
    await user.click(screen.getByLabelText("Reviewer"));
    await user.click(screen.getByRole("button", { name: /^Add/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/add failed/i);
    expect(screen.getByLabelText("Reviewer")).toBeChecked();
  });

  // round-1 fix #3: an agent member with a null user_id must not render a clickable
  // remove (it would key the delete on nothing → silent no-op).
  it("does not render a remove affordance for an agent member with null user_id", () => {
    renderSettings({
      members: [
        { id: "user-1", userId: "user-1", type: "user", displayName: "Alex", isSelf: true, isCreator: true },
        { id: "ghost", userId: null, type: "agent", displayName: "Ghost", isSelf: false, isCreator: false, status: "offline" }
      ]
    });
    expect(screen.getByText("Ghost")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove Ghost" })).not.toBeInTheDocument();
  });
});

describe("GroupSettings (mobile fullscreen)", () => {
  it("renders members and a back affordance on mobile", () => {
    const props = renderSettings({ isMobile: true });
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Back/i })).toBeInTheDocument();
    // onClose drives the back navigation.
    expect(props.onClose).not.toHaveBeenCalled();
  });
});
