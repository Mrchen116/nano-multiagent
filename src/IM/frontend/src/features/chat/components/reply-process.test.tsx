import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import "../../../i18n";
import { ToolCallsPanel } from "./tool-calls-panel";

it("preserves process-only drafts and exact source navigation without tool counts", () => {
  const navigate = vi.fn();
  render(<ToolCallsPanel toolCalls={[]} availableMessageIds={new Set(["source-1", "next-1"])} onNavigateMessage={navigate} replyProcess={[
    {item_id: "d1", kind: "draft", run_id: "run", seq: 0, text: "The full unsent draft."},
    {item_id: "r1", kind: "revalidation", run_id: "run", seq: 1, status: "failed", source_messages: [{message_id:"source-1", sender:"Alice", timestamp:"10:00"}, {message_id:"missing", sender:"Bob", timestamp:"10:01"}]},
    {item_id: "h1", kind: "segment_handoff", run_id: "run", seq: 2, successor_message_id:"next-1"}
  ]} />);
  expect(screen.getByRole("button", {name: /process|过程/i})).toHaveTextContent("1 unsent draft");
  expect(screen.getByRole("button", {name: /process|过程/i})).toHaveTextContent("1 revalidation");
  fireEvent.click(screen.getByRole("button", {name: /process|过程/i}));
  expect(screen.getByText("The full unsent draft.").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText(/原草稿.*未发送/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: /Alice/}));
  expect(navigate).toHaveBeenCalledWith("source-1");
  expect(screen.getByText(/Bob.*不可用/)).toBeInTheDocument();
  expect(screen.getByText("复核失败")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: /查看后续处理/}));
  expect(navigate).toHaveBeenLastCalledWith("next-1");
  expect(screen.queryByText(/tool call|次工具调用/i)).not.toBeInTheDocument();
});

it("labels held send_message text as unsent without reporting successful sending", () => {
  render(<ToolCallsPanel toolCalls={[{id:"send",name:"send_message",status:"completed",input:{text:"held text"},detail:{status:"held_for_revalidation",text:"held text"}}]} />);
  fireEvent.click(screen.getByRole("button", {name:/process|过程/i}));
  expect(screen.getByText("未发送")).toBeInTheDocument();
  expect(screen.getByText("未发送 · 已保留为草稿")).toBeInTheDocument();
});
