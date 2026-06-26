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
