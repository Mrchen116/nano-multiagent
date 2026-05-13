import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("expands an individual tool call to reveal its input/output", async () => {
    const user = userEvent.setup();
    render(<ToolCallsPanel toolCalls={SAMPLE} />);
    await user.click(screen.getByRole("button", { name: /tool call/i }));
    // First tool call (list_files, i=0) defaults to open per prototype; verify its input/output are visible
    expect(screen.getByText(/INPUT/i)).toBeInTheDocument();
    expect(screen.getByText(/OUTPUT/i)).toBeInTheDocument();
    // Second tool call (str_replace_edit, i=1) starts collapsed; click to expand
    const strReplaceBtn = screen.getByText("str_replace_edit").closest("button");
    expect(strReplaceBtn).toBeTruthy();
    fireEvent.click(strReplaceBtn!);
    // After expanding the second row, there should be two INPUT labels (one per row)
    expect(screen.getAllByText(/INPUT/i)).toHaveLength(2);
  });
});
