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
// presenter-produced `output` (the summary string); the front-end must NOT derive the
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
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    // The presenter summary travels in `output`; it must show ON the collapsed
    // row itself (not only inside the expanded body) — one glance is informative.
    const summaryEl = container.querySelector(".chat-tool-call-summary");
    expect(summaryEl?.textContent).toBe("跑 heartbeat 单元测试");
    expect(summaryEl?.closest(".chat-tool-call-row")).not.toBeNull();
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

// feat-409-M2 R2: expanded-body per-tool rendering. Known names get bespoke
// cards (bash terminal, edit diff, agent prompt-before-result, …); unknown /
// DIY tools fall back to a generic structured key/value card (NOT raw JSON);
// rows without detail degrade to the output string.
describe("ToolCallsPanel · expanded body (R2)", () => {
  function renderSingle(call: ToolCall) {
    // A single call defaults open (i===0) once the panel is expanded.
    return render(<ToolCallsPanel toolCalls={[call]} />);
  }
  async function open() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /tool call/i }));
  }

  it("renders bash as a terminal block with command + stdout", async () => {
    const { container } = renderSingle({
      id: "b1",
      name: "bash",
      status: "completed",
      input: {},
      output: "run tests",
      detail: { command: "pytest -x", exit_code: 0, duration_ms: 120, stdout: "12 passed", stderr: "", truncated: false }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-term")).not.toBeNull();
    expect(screen.getByText("pytest -x")).toBeInTheDocument();
    expect(screen.getByText(/12 passed/)).toBeInTheDocument();
  });

  it("renders edit as a colourised diff", async () => {
    const { container } = renderSingle({
      id: "e1",
      name: "edit",
      status: "completed",
      input: {},
      output: "updated (line 14)",
      detail: {
        path: "src/state.py",
        diff: "--- src/state.py\n+++ src/state.py\n-old line\n+new line\n",
        firstChangedLine: 14,
        truncated: false
      }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-diff")).not.toBeNull();
    expect(container.querySelector(".chat-tool-detail-diff-add")?.textContent).toContain("new line");
    expect(container.querySelector(".chat-tool-detail-diff-del")?.textContent).toContain("old line");
  });

  it("renders write content", async () => {
    renderSingle({
      id: "w1",
      name: "write",
      status: "completed",
      input: {},
      output: "created (28 bytes)",
      detail: { path: "docs/x.md", content: "# Title\nbody text", bytes: 28, truncated: false }
    });
    await open();
    expect(screen.getByText("docs/x.md")).toBeInTheDocument();
    expect(screen.getByText(/body text/)).toBeInTheDocument();
  });

  it("renders web_fetch as a card with title + url + content", async () => {
    const { container } = renderSingle({
      id: "wf1",
      name: "web_fetch",
      status: "completed",
      input: {},
      output: "status=200 (Lifespan)",
      detail: { url: "https://uvicorn.org/lifespan/", final_url: "https://uvicorn.org/lifespan/", status: 200, title: "Lifespan Protocol", content: "The lifespan protocol …", truncated: false }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-web")).not.toBeNull();
    expect(screen.getByText("Lifespan Protocol")).toBeInTheDocument();
    expect(screen.getByText(/uvicorn.org\/lifespan/)).toBeInTheDocument();
  });

  it("renders agent with the full prompt BEFORE the result", async () => {
    const { container } = renderSingle({
      id: "a1",
      name: "agent",
      status: "completed",
      input: {},
      output: "清理 30 天前的日志",
      detail: {
        description: "清理 30 天前的日志",
        prompt: "扫描 logs 目录删除超过 30 天的文件",
        subagent_type: "explore",
        status: "completed",
        agent_id: "agent-7f3a",
        content: "删除了 142 个文件释放 380MB",
        output_file: "",
        error: null
      }
    });
    await open();
    const promptEl = screen.getByText(/扫描 logs 目录删除超过 30 天的文件/);
    const resultEl = screen.getByText(/删除了 142 个文件释放 380MB/);
    expect(promptEl).toBeInTheDocument();
    expect(resultEl).toBeInTheDocument();
    // Prompt must come before result in document order (spec requirement).
    const pos = promptEl.compareDocumentPosition(resultEl);
    expect(pos & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.querySelector(".chat-tool-detail-agent-prompt")).not.toBeNull();
  });

  it("renders memory as a card surfacing target + content", async () => {
    renderSingle({
      id: "m1",
      name: "memory",
      status: "completed",
      input: {},
      output: "saved",
      detail: { action: "add", target: "project", content: "heartbeat 状态文件迁移到 ~/.nano-assistant/", message: "saved", success: true }
    });
    await open();
    expect(screen.getByText(/heartbeat 状态文件迁移/)).toBeInTheDocument();
  });

  it("renders skill_manage as a card surfacing the message", async () => {
    renderSingle({
      id: "s1",
      name: "skill_manage",
      status: "completed",
      input: {},
      output: "created log-cleanup",
      detail: { action: "create", name: "log-cleanup", message: "created skills/log-cleanup/SKILL.md", path: "skills/log-cleanup", content: "", success: true }
    });
    await open();
    expect(screen.getByText(/created skills\/log-cleanup/)).toBeInTheDocument();
  });

  it("renders task_stop as a card surfacing status + task_id", async () => {
    const { container } = renderSingle({
      id: "ts1",
      name: "task_stop",
      status: "completed",
      input: {},
      output: "killed bash-21c9",
      detail: { task_id: "bash-21c9", status: "killed" }
    });
    await open();
    // Scope to the body card so the assertion isn't satisfied by the collapsed
    // summary (which mirrors output) — the bespoke card must surface these.
    const card = container.querySelector(".chat-tool-detail-info");
    expect(card?.textContent).toContain("bash-21c9");
    expect(card?.textContent).toContain("killed");
  });

  it("renders an unknown / DIY tool as a generic key/value card (not raw JSON)", async () => {
    const { container } = renderSingle({
      id: "x1",
      name: "my_custom_tool",
      status: "completed",
      input: {},
      output: "done",
      detail: { region: "ap-southeast-1", instances: 3, dry_run: false }
    });
    await open();
    const card = container.querySelector(".chat-tool-detail-generic");
    expect(card).not.toBeNull();
    // Keys rendered as structured rows, not a single JSON blob.
    expect(screen.getByText("region")).toBeInTheDocument();
    expect(screen.getByText("ap-southeast-1")).toBeInTheDocument();
    expect(screen.getByText("instances")).toBeInTheDocument();
  });

  it("renders a failed call's error message in the expanded body", async () => {
    renderSingle({
      id: "b1",
      name: "bash",
      status: "failed",
      input: {},
      output: "failed: boom",
      detail: { error: { message: "boom: command not found" } }
    });
    await open();
    expect(screen.getByText(/boom: command not found/)).toBeInTheDocument();
  });

  it("degrades to the output string when a call carries no detail (historical message)", async () => {
    const { container } = renderSingle({
      id: "old1",
      name: "bash",
      status: "completed",
      input: { command: "ls" },
      output: "exit=0 elapsed=152ms"
    });
    await open();
    // No bespoke card; the raw output is shown in the body as a fallback.
    expect(container.querySelector(".chat-tool-detail-term")).toBeNull();
    const body = container.querySelector(".chat-tool-call-body-inner");
    expect(body?.querySelector(".chat-tool-call-pre")?.textContent).toBe("exit=0 elapsed=152ms");
  });
});

// feat-409-M2 R3: long-output two-level expand. Large fields (bash stdout, write
// content, web content, edit diff) truncate by a front-end threshold with an
// "expand all" toggle → height-capped inner scroll + "collapse". When the
// kernel already tail-truncated at the 256KB cap (detail.truncated === true) a
// "truncated at source" note appears.
describe("ToolCallsPanel · long output (R3)", () => {
  function renderSingle(call: ToolCall) {
    return render(<ToolCallsPanel toolCalls={[call]} />);
  }
  async function open() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /tool call/i }));
  }

  const LONG_STDOUT = Array.from({ length: 200 }, (_, i) => `line ${i + 1}`).join("\n");

  // The long stdout is a single text node inside a <pre>; assert via textContent
  // (line 200 is not its own element).
  function termOut(container: HTMLElement): string {
    return container.querySelector(".chat-tool-detail-term-out")?.textContent ?? "";
  }

  it("truncates a long bash stdout and offers an expand-all toggle", async () => {
    const { container } = renderSingle({
      id: "b1",
      name: "bash",
      status: "completed",
      input: {},
      output: "run",
      detail: { command: "seq 200", exit_code: 0, stdout: LONG_STDOUT, stderr: "", truncated: false }
    });
    await open();
    // Far-down line is hidden in the truncated preview until expanded.
    expect(termOut(container)).toContain("line 1");
    expect(termOut(container)).not.toContain("line 200");
    expect(screen.getByText(/expand all/i)).toBeInTheDocument();
    // The truncated block carries the cap class for the scroll container.
    expect(container.querySelector(".chat-tool-long-output")).not.toBeNull();
  });

  it("reveals the full content and switches to collapse after expanding", async () => {
    const user = userEvent.setup();
    const { container } = renderSingle({
      id: "b1",
      name: "bash",
      status: "completed",
      input: {},
      output: "run",
      detail: { command: "seq 200", exit_code: 0, stdout: LONG_STDOUT, stderr: "", truncated: false }
    });
    await open();
    await user.click(screen.getByText(/expand all/i));
    expect(termOut(container)).toContain("line 200");
    expect(screen.getByText(/collapse/i)).toBeInTheDocument();
  });

  it("collapses back to the truncated view", async () => {
    const user = userEvent.setup();
    const { container } = renderSingle({
      id: "b1",
      name: "bash",
      status: "completed",
      input: {},
      output: "run",
      detail: { command: "seq 200", exit_code: 0, stdout: LONG_STDOUT, stderr: "", truncated: false }
    });
    await open();
    await user.click(screen.getByText(/expand all/i));
    await user.click(screen.getByText(/collapse/i));
    expect(termOut(container)).not.toContain("line 200");
    expect(screen.getByText(/expand all/i)).toBeInTheDocument();
  });

  it("does not show an expand toggle for short output", async () => {
    renderSingle({
      id: "b1",
      name: "bash",
      status: "completed",
      input: {},
      output: "run",
      detail: { command: "echo hi", exit_code: 0, stdout: "hi", stderr: "", truncated: false }
    });
    await open();
    expect(screen.queryByText(/expand all/i)).not.toBeInTheDocument();
    expect(screen.getByText("hi")).toBeInTheDocument();
  });

  it("marks output that was truncated at the kernel source", async () => {
    renderSingle({
      id: "b1",
      name: "bash",
      status: "completed",
      input: {},
      output: "run",
      detail: { command: "huge", exit_code: 0, stdout: LONG_STDOUT, stderr: "", truncated: true }
    });
    await open();
    expect(screen.getByText(/truncated at source|源头截断/i)).toBeInTheDocument();
  });
});

// feat-409-M2 Round-1 fix: agent in-band failure was hijacked by the generic
// ErrorCard (first `if (detail.error)` branch), bypassing AgentCard → empty
// error card + lost prompt. Bespoke tools with rich failure context (agent:
// prompt + status + error) must render via their own card; ErrorCard is the
// fallback only for error-only details (bash/edit/web out-of-band failures
// whose detail is just {error:{message}}).
describe("ToolCallsPanel · bespoke failure routing (Round-1 fix)", () => {
  function renderSingle(call: ToolCall) {
    return render(<ToolCallsPanel toolCalls={[call]} />);
  }
  async function open() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /tool call/i }));
  }

  it("renders an agent in-band failure via AgentCard with prompt + error text (not an empty ErrorCard)", async () => {
    const { container } = renderSingle({
      id: "a1",
      name: "agent",
      status: "failed",
      input: {},
      output: "failed: subagent blew up",
      // in-band failure: result.error is None, output={status:failed, error:<str>}
      // → presenter detail carries full prompt + status + plain-string error.
      detail: {
        description: "清理 30 天前的日志",
        prompt: "扫描 logs 目录删除超过 30 天的文件，统计释放空间。",
        subagent_type: "explore",
        status: "failed",
        agent_id: "agent-7f3a",
        content: "",
        output_file: "",
        error: "FileNotFoundError: logs 目录不存在"
      }
    });
    await open();
    // Routed to AgentCard, not the generic ErrorCard.
    expect(container.querySelector(".chat-tool-detail-agent")).not.toBeNull();
    expect(container.querySelector(".chat-tool-detail-error")).toBeNull();
    // The dispatch prompt — most valuable on failure — is still rendered.
    expect(container.querySelector(".chat-tool-detail-agent-prompt")?.textContent).toContain(
      "扫描 logs 目录删除超过 30 天的文件"
    );
    // The error text (plain string) is visible, not an empty card.
    expect(screen.getByText(/FileNotFoundError: logs 目录不存在/)).toBeInTheDocument();
  });

  it("still routes a bash out-of-band failure (error-only detail) to ErrorCard", async () => {
    const { container } = renderSingle({
      id: "b1",
      name: "bash",
      status: "failed",
      input: {},
      output: "failed: boom",
      detail: { error: { message: "boom: command not found" } }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-error")).not.toBeNull();
    expect(container.querySelector(".chat-tool-detail-term")).toBeNull();
    expect(screen.getByText(/boom: command not found/)).toBeInTheDocument();
  });

  it("ErrorCard tolerates a plain-string error (no .message wrapper)", async () => {
    const { container } = renderSingle({
      id: "x1",
      name: "my_unknown_tool",
      status: "failed",
      input: {},
      output: "failed",
      // error-only detail but the error is a bare string, not {message}.
      detail: { error: "raw failure string" }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-error")).not.toBeNull();
    expect(screen.getByText(/raw failure string/)).toBeInTheDocument();
  });
});

// feat-409-M2 Round-3 fix: memory/skill_manage failures (kernel never raises —
// returns {success:False, error}) were rendered as success. detail carries
// {message:err, success:False} with NO error key → isErrorOnly=false → routed to
// MemoryCard/SkillCard which always render ✓; collapsed row not red (call.status
// is completed since kernel reported no result.error). Failure must derive from
// detail.success===false, not call.status alone.
describe("ToolCallsPanel · success-false failure (Round-3 fix)", () => {
  function renderSingle(call: ToolCall) {
    return render(<ToolCallsPanel toolCalls={[call]} />);
  }
  async function open() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /tool call/i }));
  }

  it("renders a memory success=false detail as a failure (✕ + error text, not ✓)", async () => {
    const { container } = renderSingle({
      id: "m1",
      name: "memory",
      status: "completed", // kernel reported no result.error
      output: "failed: add action requires content",
      input: {},
      detail: {
        action: "add",
        target: "project",
        content: "",
        message: "add action requires content",
        success: false
      }
    });
    await open();
    const card = container.querySelector(".chat-tool-detail-info");
    expect(card?.textContent).toContain("add action requires content");
    // Must NOT show the success check.
    expect(card?.textContent).not.toContain("✓");
    // A dedicated failure marker / styling is present.
    expect(container.querySelector(".chat-tool-detail-info--failed")).not.toBeNull();
  });

  it("renders a skill_manage success=false detail as a failure (✕ + error text, not ✓)", async () => {
    const { container } = renderSingle({
      id: "s1",
      name: "skill_manage",
      status: "completed",
      output: "failed: skill not found",
      input: {},
      detail: { action: "edit", name: "log-cleanup", message: "skill not found", path: "", success: false }
    });
    await open();
    const card = container.querySelector(".chat-tool-detail-info");
    expect(card?.textContent).toContain("skill not found");
    expect(card?.textContent).not.toContain("✓");
    expect(container.querySelector(".chat-tool-detail-info--failed")).not.toBeNull();
  });

  it("marks the collapsed row red + fail tag when detail.success===false (call.status=completed)", async () => {
    const { container } = renderSingle({
      id: "m1",
      name: "memory",
      status: "completed",
      output: "failed: add action requires content",
      input: {},
      detail: { action: "add", target: "project", content: "", message: "add action requires content", success: false }
    });
    await open();
    const row = container.querySelector(".chat-tool-call-row");
    // Failure styling derived from detail.success, not call.status.
    expect(row?.className).toContain("chat-tool-call-row--failed");
    expect(row?.querySelector(".chat-tool-call-fail-tag")).not.toBeNull();
  });

  it("still renders a memory success=true detail with the success check + content", async () => {
    const { container } = renderSingle({
      id: "m1",
      name: "memory",
      status: "completed",
      output: "saved",
      input: {},
      detail: {
        action: "add",
        target: "project",
        content: "heartbeat 状态迁移到 ~/.nano-assistant/",
        message: "saved",
        success: true
      }
    });
    await open();
    const card = container.querySelector(".chat-tool-detail-info");
    expect(card?.textContent).toContain("✓");
    // minor: written content is surfaced clearly (target + content).
    expect(card?.textContent).toContain("project");
    expect(card?.textContent).toContain("heartbeat 状态迁移到 ~/.nano-assistant/");
    expect(container.querySelector(".chat-tool-detail-info--failed")).toBeNull();
  });

  it("surfaces the skill name + action on a successful skill_manage card", async () => {
    const { container } = renderSingle({
      id: "s1",
      name: "skill_manage",
      status: "completed",
      output: "created log-cleanup",
      input: {},
      detail: { action: "create", name: "log-cleanup", message: "created skills/log-cleanup/SKILL.md", path: "skills/log-cleanup", content: "", success: true }
    });
    await open();
    const card = container.querySelector(".chat-tool-detail-info");
    expect(card?.textContent).toContain("log-cleanup");
    expect(card?.textContent).toContain("create");
  });
});
