import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import "../../../../i18n";
import type { ToolCall } from "../chat-types";
import { ToolCallsPanel } from "./tool-calls-panel";

const SAMPLE: ToolCall[] = [
  { id: "t1", name: "list_files", status: "completed", input: { path: "/" }, output: "ok", duration_ms: 48 },
  { id: "t2", name: "str_replace_edit", status: "running", input: { file: "a" } }
];

describe("ToolCallsPanel", () => {
  it("renders nothing when there are no tool calls", () => {
    const { container } = render(<ToolCallsPanel toolCalls={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the running indicator when at least one tool call is in flight", () => {
    render(<ToolCallsPanel toolCalls={SAMPLE} />);
    expect(screen.getByText(/running/i)).toBeInTheDocument();
  });

  it("expands the panel and reveals tool call rows on click", async () => {
    const user = userEvent.setup();
    render(<ToolCallsPanel toolCalls={SAMPLE} />);
    expect(screen.queryByText("list_files")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /tool call/i }));
    expect(screen.getByText("list_files")).toBeInTheDocument();
    expect(screen.getByText("str_replace_edit")).toBeInTheDocument();
  });
});

// feat-409-M2 R1: collapsed-row rendering — summary(=output), failure styling,
// real tool name, emoji fallback by name. The collapsed text is the
// presenter-produced `output` (人话 summary); the front-end must NOT derive the
// collapsed text by tool name (决策 4).
describe("ToolCallsPanel · collapsed row (R1)", () => {
  async function expandPanel() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /tool call/i }));
  }

  it("renders the presenter output as the collapsed-row summary text", async () => {
    const calls: ToolCall[] = [
      { id: "b1", name: "bash", status: "completed", input: {}, output: "跑 heartbeat 单元测试", duration_ms: 8200 }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    // The 人话 summary travels in `output`; it must show ON the collapsed row
    // itself (not only inside the expanded body) — one glance gives信息量.
    const summaryEl = screen.getByText("跑 heartbeat 单元测试");
    expect(summaryEl.closest(".chat-tool-call-row")).not.toBeNull();
  });

  it("shows the real tool name even for unknown / DIY tools", async () => {
    const calls: ToolCall[] = [
      { id: "x1", name: "my_custom_tool", status: "completed", input: {}, output: "done" }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(screen.getByText("my_custom_tool")).toBeInTheDocument();
  });

  it("maps a known tool name to its emoji prefix", async () => {
    const calls: ToolCall[] = [
      { id: "b1", name: "bash", status: "completed", input: {}, output: "run tests" }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const nameEl = screen.getByText("bash").closest(".chat-tool-call-name");
    expect(nameEl?.textContent).toContain("💻");
  });

  it("falls back to a generic emoji for unknown tools", async () => {
    const calls: ToolCall[] = [
      { id: "x1", name: "my_custom_tool", status: "completed", input: {}, output: "done" }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const nameEl = screen.getByText("my_custom_tool").closest(".chat-tool-call-name");
    // generic fallback icon (🔧) — not blank, not a known-tool emoji.
    expect(nameEl?.textContent).toContain("🔧");
  });

  it("marks a failed call with the error row modifier and a fail tag", async () => {
    const calls: ToolCall[] = [
      {
        id: "b1",
        name: "bash",
        status: "failed",
        input: {},
        output: "failed: exit 1",
        detail: { error: { message: "exit 1" } }
      }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const row = screen.getByText("bash").closest(".chat-tool-call-row");
    expect(row?.className).toContain("chat-tool-call-row--failed");
    // The failed call carries a dedicated fail tag in the collapsed row so the
    // failure is visible without expanding (prototype: red "exit 1" tag).
    expect(row?.querySelector(".chat-tool-call-fail-tag")).not.toBeNull();
  });

  // bugfix-410-M2 R4 (#97): tool_call badge must render the reason label per cause.
  it.each([
    ["denied", /denied/i],
    ["timed_out", /timed out/i],
    ["interrupted", /interrupted/i],
  ] as const)("renders the %s reason badge", async (reason, label) => {
    const user = userEvent.setup();
    const calls: ToolCall[] = [
      { id: "x1", name: "bash", status: "failed", input: {}, reason },
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await user.click(screen.getByRole("button", { name: /tool call/i }));
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("renders no reason badge for a normally completed tool call", async () => {
    const user = userEvent.setup();
    const calls: ToolCall[] = [
      { id: "ok1", name: "read", status: "completed", input: {}, output: "ok" },
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await user.click(screen.getByRole("button", { name: /tool call/i }));
    expect(screen.queryByText(/denied|timed out|interrupted/i)).not.toBeInTheDocument();
  });
});
