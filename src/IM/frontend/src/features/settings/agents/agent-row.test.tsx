import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AgentRow, nodeLabelOf, statusOf } from "./agent-row";
import type { AgentSummary, NodeSummary } from "./im-agent-config-api";

const AGENT: AgentSummary = {
  agent_id: "agent-1",
  owner_id: "owner-1",
  display_name: "Planner",
  description: "Coordinates milestones",
  profile_version: 1,
  default_model: null,
  workspace_root: null,
  workspace_is_default: null,
  node_id: "node-1",
  node_status: "online"
};

const NODES: NodeSummary[] = [
  {
    node_id: "node-1",
    owner_id: "owner-1",
    node_name: "mac-mini",
    status: "online",
    last_heartbeat_at: "2026-08-18T00:00:00Z",
    agent_count: 1,
    version: "1.0.0"
  }
];

function renderRow(overrides: Partial<Parameters<typeof AgentRow>[0]> = {}) {
  const onSelect = vi.fn();
  render(
    <AgentRow
      agent={AGENT}
      nodes={NODES}
      isActive={false}
      isMobile={false}
      onSelect={onSelect}
      {...overrides}
    />
  );
  return onSelect;
}

describe("nodeLabelOf", () => {
  it("prefers alias, then node_name, matching the Account page precedence", () => {
    const aliased = [{ ...NODES[0], alias: "工作室" }];
    expect(nodeLabelOf(AGENT, aliased)).toBe("工作室");
    expect(nodeLabelOf(AGENT, NODES)).toBe("mac-mini");
  });

  it("falls back to node_id when the nodes table lacks the node, and to null without an owning node", () => {
    expect(nodeLabelOf(AGENT, [])).toBe("node-1");
    expect(nodeLabelOf({ ...AGENT, node_id: null }, NODES)).toBeNull();
  });
});

describe("statusOf", () => {
  it("trusts the agent's node_status first and falls back to the nodes table", () => {
    expect(statusOf(AGENT, NODES)).toBe("online");
    expect(statusOf({ ...AGENT, node_status: null }, NODES)).toBe("online");
    expect(statusOf({ ...AGENT, node_status: null }, [])).toBe("offline");
    expect(statusOf({ ...AGENT, node_id: null, node_status: null }, NODES)).toBe("offline");
  });
});

describe("AgentRow on desktop", () => {
  it("shows display name, agent id, and the owning device label at the trailing edge", () => {
    renderRow();

    const row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).getByText("Planner")).toBeInTheDocument();
    expect(within(row).getByText("agent-1")).toBeInTheDocument();
    expect(within(row).getByText("mac-mini")).toBeInTheDocument();
  });

  it("has no standalone status dot at the trailing edge — presence lives on the avatar badge", () => {
    renderRow();

    const row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).queryByLabelText("online")).not.toBeInTheDocument();
    expect(within(row).queryByLabelText("offline")).not.toBeInTheDocument();
  });

  it("renders nothing at the trailing edge when the agent has no owning node", () => {
    renderRow({ agent: { ...AGENT, node_id: null, node_status: null } });

    const row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).queryByText("node-1")).not.toBeInTheDocument();
  });

  it("keeps the light-on-dark identity colors: readable name/id in normal state, brighter when active", () => {
    const { unmount } = render(
      <AgentRow agent={AGENT} nodes={NODES} isActive={false} isMobile={false} onSelect={() => {}} />
    );
    let row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).getByText("Planner")).toHaveClass("text-[oklch(0.86_0.01_240)]");
    expect(within(row).getByText("agent-1")).toHaveClass("text-[oklch(0.64_0.01_240)]");
    expect(within(row).getByText("mac-mini")).toHaveClass("text-[oklch(0.55_0.01_240)]");
    unmount();

    render(
      <AgentRow agent={AGENT} nodes={NODES} isActive={true} isMobile={false} onSelect={() => {}} />
    );
    row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).getByText("Planner")).toHaveClass("text-white");
    expect(within(row).getByText("agent-1")).toHaveClass("text-[oklch(0.70_0.01_240)]");
    expect(within(row).getByText("mac-mini")).toHaveClass("text-[oklch(0.64_0.01_240)]");
  });

  it("gets its hover background from Tailwind classes, suppressed while active", () => {
    const { unmount } = render(
      <AgentRow agent={AGENT} nodes={NODES} isActive={false} isMobile={false} onSelect={() => {}} />
    );
    expect(screen.getByRole("button", { name: "Planner" })).toHaveClass(
      "hover:bg-[oklch(0.28_0.012_240)]"
    );
    unmount();

    render(
      <AgentRow agent={AGENT} nodes={NODES} isActive={true} isMobile={false} onSelect={() => {}} />
    );
    expect(screen.getByRole("button", { name: "Planner" })).not.toHaveClass(
      "hover:bg-[oklch(0.28_0.012_240)]"
    );
  });

  it("truncates only the device label itself, never the identity lines", () => {
    renderRow();

    const row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).getByText("mac-mini")).toHaveClass("truncate", "max-w-[92px]", "shrink-0");
  });

  it("invokes onSelect with the agent id", async () => {
    const user = userEvent.setup();
    const onSelect = renderRow();

    await user.click(screen.getByRole("button", { name: "Planner" }));

    expect(onSelect).toHaveBeenCalledWith("agent-1");
  });
});

describe("AgentRow on mobile", () => {
  it("shows the description line, keeps the chevron, and labels the device above it", () => {
    renderRow({ isMobile: true });

    const row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).getByText("Coordinates milestones")).toBeInTheDocument();
    expect(within(row).getByText("mac-mini")).toBeInTheDocument();
    expect(within(row).getByText("›")).toBeInTheDocument();
    expect(within(row).queryByText("agent-1")).not.toBeInTheDocument();
  });

  it("falls back to the agent id when the description is empty", () => {
    renderRow({ isMobile: true, agent: { ...AGENT, description: "" } });

    const row = screen.getByRole("button", { name: "Planner" });
    expect(within(row).getByText("agent-1")).toBeInTheDocument();
  });
});
