import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import "../../../i18n";
import type { Conversation, Message, ToolCall } from "../chat-types";
import { MessagePane } from "./message-pane";
import { ToolCallsPanel } from "./tool-calls-panel";

async function openProcess() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /过程|process/i }));
  return user;
}

describe("Workflow tool detail", () => {
  it("renders input first and hides the result section while the launch is pending", async () => {
    const { container } = render(
      <ToolCallsPanel
        toolCalls={[
          {
            id: "workflow-running",
            name: "Workflow",
            status: "running",
            input: {},
            output: "review changes",
            detail: {
              description: "review changes",
              source: "inline",
              guideline: "medium",
              script_preview: "async def main():\n    return await parallel([...])",
            },
          },
        ]}
      />
    );

    await openProcess();
    expect(screen.getByText(/async def main/)).toBeInTheDocument();
    expect(screen.getByText(/medium/)).toBeInTheDocument();
    expect(container.querySelector(".chat-tool-detail-workflow-input")).not.toBeNull();
    expect(container.querySelector(".chat-tool-detail-workflow-result")).toBeNull();
  });

  it("appends the async launch result below the unchanged input", async () => {
    const { container } = render(
      <ToolCallsPanel
        toolCalls={[
          {
            id: "workflow-launched",
            name: "Workflow",
            status: "completed",
            input: {},
            output: "review changes",
            detail: {
              description: "review changes",
              source: "inline",
              guideline: "medium",
              script_preview: "async def main():\n    return await parallel([...])",
              status: "async_launched",
              name: "review-changes",
              runId: "wf-1",
              taskId: "task-1",
              scriptPath: "/workspace/workflows/review.py",
              transcriptDir: "/workspace/workflows/runs/wf-1",
            },
          },
        ]}
      />
    );

    await openProcess();
    const input = container.querySelector(".chat-tool-detail-workflow-input")!;
    const result = container.querySelector(".chat-tool-detail-workflow-result")!;
    expect(input.compareDocumentPosition(result) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
    expect(result).toHaveTextContent("async_launched");
    expect(result).toHaveTextContent("wf-1");
    expect(result).toHaveTextContent("task-1");
  });

  it("shows denied as not executed without inventing run/task/duration", async () => {
    const { container } = render(
      <ToolCallsPanel
        toolCalls={[
          {
            id: "workflow-denied",
            name: "Workflow",
            status: "failed",
            input: {},
            output: "review changes",
            reason: "denied",
            approval: "user_deny",
            detail: {
              description: "review changes",
              source: "inline",
              guideline: "medium",
              script_preview: "async def main(): pass",
            },
          },
        ]}
      />
    );

    await openProcess();
    const result = container.querySelector(".chat-tool-detail-workflow-result");
    expect(result).not.toBeNull();
    expect(result).toHaveTextContent(/未执行|not run/i);
    expect(container.textContent).not.toContain("runId");
    expect(container.textContent).not.toContain("taskId");
    expect(container.querySelector(".chat-tool-call-duration")).toBeNull();
  });
});

describe("background return process item", () => {
  const workflowReturn = {
    seq: 3,
    task_id: "task-workflow-1",
    task_type: "workflow" as const,
    status: "completed" as const,
    description: "review changes",
    workflow_run_id: "wf-1",
    result: "raw workflow result",
    usage: { total_tokens: 42180 },
    tool_use_count: 6,
    duration_ms: 184000,
    diagnostics: "/workspace/workflows/runs/wf-1",
    resume_hint: "/workflows wf-1 resume",
  };

  it("interleaves with thinking/tools by seq and keeps all counters independent", async () => {
    const calls: ToolCall[] = [
      {
        id: "read-1",
        name: "read",
        status: "completed",
        input: {},
        output: "read spec",
        seq: 2,
        approval: "user_allow",
      },
    ];
    render(
      <ToolCallsPanel
        toolCalls={calls}
        thinking={[{ seq: 1, text: "inspect first" }]}
        backgroundReturns={[workflowReturn]}
      />
    );

    const toggle = screen.getByRole("button", { name: /过程|process/i });
    expect(toggle).toHaveTextContent(/1 tool/i);
    expect(toggle).toHaveTextContent(/1 (background return|条后台返回)/i);
    expect(toggle).toHaveTextContent(/1 (approved|次授权)/i);
    expect(toggle).not.toHaveTextContent(/running|运行中/i);

    await openProcess();
    const rows = screen.getAllByTestId("process-item");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("inspect first");
    expect(rows[1]).toHaveTextContent("read");
    expect(rows[2]).toHaveTextContent(/background return|后台返回/i);
  });

  it("expands the raw Workflow result, identity, usage and artifact fields", async () => {
    render(<ToolCallsPanel toolCalls={[]} backgroundReturns={[workflowReturn]} />);
    const user = await openProcess();
    await user.click(screen.getByTestId("process-background-return-toggle"));

    const body = screen.getByTestId("process-background-return-body");
    expect(body).toHaveTextContent("task-workflow-1");
    expect(body).toHaveTextContent("wf-1");
    expect(body).toHaveTextContent("raw workflow result");
    expect(body).toHaveTextContent("42180");
    expect(body).toHaveTextContent("/workspace/workflows/runs/wf-1");
    expect(body).toHaveTextContent("/workflows wf-1 resume");
  });

  it("keeps failed/stopped terminal states and partial raw values distinct", async () => {
    const failedReturn = {
      ...workflowReturn,
      task_id: "task-failed",
      workflow_run_id: "wf-failed",
      status: "failed" as const,
      result: "partial verified findings",
      error: "verify agent timed out",
      seq: 1,
    };
    const stoppedReturn = {
      ...workflowReturn,
      task_id: "task-stopped",
      workflow_run_id: "wf-stopped",
      status: "stopped" as const,
      result: "five completed agent results retained",
      seq: 2,
    };
    render(
      <ToolCallsPanel
        toolCalls={[]}
        backgroundReturns={[failedReturn, stoppedReturn]}
      />
    );
    const user = await openProcess();
    const toggles = screen.getAllByTestId("process-background-return-toggle");
    expect(toggles[0]).toHaveClass("chat-tool-call-row--failed");
    expect(toggles[1]).toHaveClass("chat-tool-call-row--stopped");
    await user.click(toggles[0]!);
    await user.click(toggles[1]!);
    expect(screen.getByText("verify agent timed out")).toBeInTheDocument();
    expect(screen.getByText("partial verified findings")).toBeInTheDocument();
    expect(screen.getByText("five completed agent results retained")).toBeInTheDocument();
  });

  it("uses the same row for a background Agent result and output artifact", async () => {
    render(
      <ToolCallsPanel
        toolCalls={[]}
        backgroundReturns={[
          {
            seq: 1,
            task_id: "agent-task-1",
            task_type: "subagent",
            status: "completed",
            description: "review API contract",
            agent_id: "agent-reviewer",
            result: "raw subagent finding",
            usage: { total_tokens: 28416 },
            tool_use_count: 7,
            duration_ms: 108000,
            output_file: "/background-tasks/agent-task-1.output",
          },
        ]}
      />
    );
    const user = await openProcess();
    expect(screen.getByTestId("process-background-return-toggle")).toHaveTextContent(
      "Agent agent-reviewer",
    );
    await user.click(screen.getByTestId("process-background-return-toggle"));
    const body = screen.getByTestId("process-background-return-body");
    expect(body).toHaveTextContent("raw subagent finding");
    expect(body).toHaveTextContent("/background-tasks/agent-task-1.output");
  });

  it("keeps an empty assistant message visible when it only carries a background return", () => {
    const conversation: Conversation = {
      id: "c1",
      title: "Reviewer",
      participants: [{ type: "agent", id: "reviewer", display_name: "Reviewer" }],
      participant_ids: ["reviewer"],
      type: "direct",
      direct_kind: "agent",
      owner_id: "user-1",
      creator_id: "user-1",
      is_pinned: false,
      is_muted: false,
      unread_count: 0,
      last_message_preview: null,
      last_message_at: null,
      created_at: "2026-08-10T00:00:00Z",
    };
    const message = {
      id: "m-background-only",
      conversation_id: "c1",
      sender: { type: "agent", id: "reviewer", display_name: "Reviewer" },
      sender_user_id: "agent:reviewer",
      sender_type: "agent",
      content: "",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-08-10T00:00:01Z",
      permission_requests: [],
      background_returns: [workflowReturn],
    } as Message;

    render(
      <MessagePane
        conversation={conversation}
        messages={[message]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );

    expect(screen.getByTestId("message-bubble-m-background-only")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /过程|process/i })).toHaveTextContent(
      /1 (background return|条后台返回)/i,
    );
  });

  it("keeps the main Agent summary before its background-return process block", () => {
    const conversation: Conversation = {
      id: "c1",
      title: "Reviewer",
      participants: [{ type: "agent", id: "reviewer", display_name: "Reviewer" }],
      participant_ids: ["reviewer"],
      type: "direct",
      direct_kind: "agent",
      owner_id: "user-1",
      creator_id: "user-1",
      is_pinned: false,
      is_muted: false,
      unread_count: 0,
      last_message_preview: null,
      last_message_at: null,
      created_at: "2026-08-10T00:00:00Z",
    };
    const message = {
      id: "m-summary",
      conversation_id: "c1",
      sender: { type: "agent", id: "reviewer", display_name: "Reviewer" },
      sender_user_id: "agent:reviewer",
      sender_type: "agent",
      content: "Main Agent synthesis",
      attachments: [],
      delivery_status: "completed",
      created_at: "2026-08-10T00:00:01Z",
      permission_requests: [],
      background_returns: [workflowReturn],
    } as Message;

    const { container } = render(
      <MessagePane
        conversation={conversation}
        messages={[message]}
        mentionCandidates={[]}
        onSend={() => {}}
      />
    );
    const summary = screen.getByText("Main Agent synthesis");
    const process = container.querySelector(".chat-tool-calls")!;
    expect(summary.compareDocumentPosition(process) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  });
});
