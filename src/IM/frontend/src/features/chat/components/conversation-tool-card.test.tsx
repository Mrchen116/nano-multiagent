import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { ToolCall } from "../chat-types";
import { ToolDetailBody } from "./tool-detail-renderers";

const call: ToolCall = { id: "read", name: "inbox", status: "running", input: { action: "read", target: "group-a", limit: 20 }, detail: { action: "read", target: "group-a", limit: 20 } };
const page = { action: "read", target: "group-a", has_more: false, messages: [{ message_id: "message-a", sender: { name: "Alice" }, source_time: "2026-09-09", source: { conversation_id: "group-a" }, content: [{ type: "text", text: "The actual constraint" }], complete_message: true }] };

describe("conversation tool presentation", () => {
  it("shows parameters during execution, actual page after end, and no invented consumption", () => {
    const result = render(<MemoryRouter><ToolDetailBody call={call} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "group-a" })).toHaveAttribute("href", "/chat/group-a");
    expect(screen.queryByText("没有匹配记录")).not.toBeInTheDocument();
    expect(screen.queryByText("当前页面已返回")).not.toBeInTheDocument();
    result.rerender(<MemoryRouter><ToolDetailBody call={{ ...call, status: "completed", detail: page }} /></MemoryRouter>);
    expect(screen.getByText("The actual constraint")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "原消息" })).toHaveAttribute("href", "/chat/group-a?message_id=message-a");
    expect(screen.queryByText(/已.*摄取/)).not.toBeInTheDocument();
  });

  it("distinguishes history failure from an empty successful page", () => {
    const result = render(<MemoryRouter><ToolDetailBody call={{ ...call, name: "conversations", status: "failed", detail: { ...call.detail, error: "target_not_accessible" } }} /></MemoryRouter>);
    expect(screen.getByText("target_not_accessible")).toBeInTheDocument();
    expect(screen.queryByText("没有匹配记录")).not.toBeInTheDocument();
    result.rerender(<MemoryRouter><ToolDetailBody call={{ ...call, name: "conversations", status: "completed", detail: { ...page, messages: [] } }} /></MemoryRouter>);
    expect(screen.getByText("没有匹配记录")).toBeInTheDocument();
    expect(screen.getByText("聊天历史查询 · 不推进收件箱")).toBeInTheDocument();
  });
});
