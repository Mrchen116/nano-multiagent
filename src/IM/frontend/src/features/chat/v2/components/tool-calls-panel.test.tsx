import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

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

  it("prefers the tool-carried emoji over the name table (event-first)", async () => {
    // feat-425 决策 1: 自定义/MCP 工具声明了 emoji,折叠行就显该图标,不再一律 🔧。
    const calls: ToolCall[] = [
      { id: "x1", name: "my_custom_tool", status: "completed", input: {}, output: "done", emoji: "🚀" }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const nameEl = screen.getByText("my_custom_tool").closest(".chat-tool-call-name");
    expect(nameEl?.textContent).toContain("🚀");
    expect(nameEl?.textContent).not.toContain("🔧");
  });

  it("shows the carried emoji on a running row (feat-425 C1)", async () => {
    // running 阶段 tool_call_upserted 也带上自带 emoji,执行中就显该图标,不回退 🔧
    // 等完成才跳变(C1 polish)。
    const calls: ToolCall[] = [
      { id: "x1", name: "my_custom_tool", status: "running", input: {}, emoji: "🚀" }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const nameEl = screen.getByText("my_custom_tool").closest(".chat-tool-call-name");
    expect(nameEl?.textContent).toContain("🚀");
    expect(nameEl?.textContent).not.toContain("🔧");
  });

  it("falls back to the name table when the tool carries no emoji (historical rows)", async () => {
    // 历史行/运行中行无 emoji 字段 → 名表兜底,内置工具不退化。
    const calls: ToolCall[] = [
      { id: "b1", name: "bash", status: "completed", input: {}, output: "run tests" }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const nameEl = screen.getByText("bash").closest(".chat-tool-call-name");
    expect(nameEl?.textContent).toContain("💻");
  });

  it("marks a failed call with the error row modifier and a fail tag", async () => {
    // feat-409 failalign: 折叠行 summary 是干净主参数(description),失败仅由
    // ✕ 图标 + fail-tag 表达,error 文本绝不出现在折叠行(只在展开卡)。
    const calls: ToolCall[] = [
      {
        id: "b1",
        name: "bash",
        status: "failed",
        input: {},
        output: "跑测试",
        detail: { command: "pytest", exit_code: 1, error: { message: "boom traceback" } }
      }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const row = screen.getByText("bash").closest(".chat-tool-call-row");
    expect(row?.className).toContain("chat-tool-call-row--failed");
    // The failed call carries a dedicated fail tag in the collapsed row so the
    // failure is visible without expanding (prototype: red "exit 1" tag).
    const tag = row?.querySelector(".chat-tool-call-fail-tag");
    expect(tag).not.toBeNull();
    expect(tag?.textContent).toBe("exit 1");
    // The collapsed row must never leak error text — that belongs to the card.
    expect(row?.textContent).not.toContain("boom traceback");
    expect(row?.querySelector(".chat-tool-call-summary")?.textContent).toBe("跑测试");
  });

  it("suppresses the fail tag when a reason badge is shown (no double label)", async () => {
    // cr4-frontend: a denied call already shows the "已拒绝" reason badge; the
    // generic "failed" fail-tag alongside it is a confusing double identifier.
    const calls: ToolCall[] = [
      { id: "d1", name: "bash", status: "failed", input: {}, output: "reboot", reason: "denied" }
    ];
    render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const row = screen.getByText("bash").closest(".chat-tool-call-row");
    expect(row?.querySelector(".chat-tool-call-reason")).not.toBeNull();
    expect(row?.querySelector(".chat-tool-call-fail-tag")).toBeNull();
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

  it("renders read success as a term single line with path + line count", async () => {
    // feat-409 protoalign: read 展开态对齐原型 .term 单行 `<path> · N 行`。
    const { container } = renderSingle({
      id: "r1",
      name: "read",
      status: "completed",
      input: {},
      output: "src/app.py · 120 行",
      detail: { path: "src/app.py", total_lines: 120, offset: 1, limit: null, truncated: false }
    });
    await open();
    const term = container.querySelector(".chat-tool-detail-term .chat-tool-detail-term-out");
    expect(term).not.toBeNull();
    expect(term?.textContent).toContain("src/app.py");
    expect(term?.textContent).toMatch(/120/);
  });

  it("renders read failure with path + error in the failed style", async () => {
    // feat-409 readfix: 失败态必须显示读的是哪个文件 + 错误,走失败样式。
    const { container } = renderSingle({
      id: "r2",
      name: "read",
      status: "failed",
      input: {},
      output: "missing.py: file does not exist",
      detail: { path: "missing.py", error: { message: "file does not exist" } }
    });
    await open();
    const card = container.querySelector(".chat-tool-detail-info--failed");
    expect(card).not.toBeNull();
    expect(card?.textContent).toContain("missing.py");
    expect(card?.textContent).toContain("file does not exist");
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

  it("renders web_fetch as a card with url + status + non-empty content", async () => {
    // feat-425 决策 4: 去掉恒空的 title;展开卡显 URL + 状态 + 抓到的正文(非空)。
    const { container } = renderSingle({
      id: "wf1",
      name: "web_fetch",
      status: "completed",
      input: {},
      output: "https://uvicorn.org/lifespan/",
      detail: { url: "https://uvicorn.org/lifespan/", final_url: "https://uvicorn.org/lifespan/", status: 200, content: "The lifespan protocol …", truncated: false }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-web")).not.toBeNull();
    expect(container.querySelector(".chat-tool-detail-web-url")?.textContent).toContain(
      "uvicorn.org/lifespan"
    );
    // 正文非空(修复 #131 的空正文 bug)。
    expect(screen.getByText(/The lifespan protocol/)).toBeInTheDocument();
  });

  it("renders web_search as a card listing result entries", async () => {
    // feat-425 决策 5: 展开按条目列出标题/网址/摘要,不是一坨原始字符串。
    const { container } = renderSingle({
      id: "ws1",
      name: "web_search",
      status: "completed",
      input: {},
      output: "nano 架构",
      detail: {
        query: "nano 架构",
        provider: "duckduckgo",
        count: 2,
        results: [
          { title: "结果一", url: "https://a.example", snippet: "摘要一" },
          { title: "结果二", url: "https://b.example", snippet: "摘要二" }
        ]
      }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-search")).not.toBeNull();
    expect(screen.getByText("结果一")).toBeInTheDocument();
    expect(screen.getByText("结果二")).toBeInTheDocument();
    expect(screen.getByText(/a.example/)).toBeInTheDocument();
    expect(screen.getByText("摘要一")).toBeInTheDocument();
  });

  it("renders web_search empty state when there are no results", async () => {
    renderSingle({
      id: "ws2",
      name: "web_search",
      status: "completed",
      input: {},
      output: "无命中查询",
      detail: { query: "无命中查询", provider: "searxng", count: 0, results: [] }
    });
    await open();
    // 明确"无结果"空态文案,而非空白或原始字符串。
    expect(screen.getByText(/无结果|没有结果|no results/i)).toBeInTheDocument();
  });

  it("routes a web_search failure to the error card (provider error)", async () => {
    // 失败态:detail 只带 error → 走 ErrorCard(isErrorOnly),展开看到出错原因。
    const { container } = renderSingle({
      id: "ws3",
      name: "web_search",
      status: "failed",
      input: {},
      output: "kw",
      detail: { error: { message: "Unknown provider: bogus" } }
    });
    await open();
    expect(container.querySelector(".chat-tool-detail-error")).not.toBeNull();
    expect(screen.getByText(/Unknown provider: bogus/)).toBeInTheDocument();
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

  it("shows the total line count in the truncated hint (BUG2)", async () => {
    // feat-409 protoalign BUG2: 截断提示要告诉用户被隐藏了多少行(原型「… 已截断，
    // 共 N 行（展开全部）」),而非裸 "展开全部"。
    const { container } = renderSingle({
      id: "b1",
      name: "bash",
      status: "completed",
      input: {},
      output: "run",
      detail: { command: "show", exit_code: 0, stdout: LONG_STDOUT, stderr: "", truncated: false }
    });
    await open();
    // 200 行总数出现在截断 toggle 按钮文案里。
    const toggle = container.querySelector(".chat-tool-long-output-toggle");
    expect(toggle?.textContent).toMatch(/200/);
    expect(toggle?.textContent).toMatch(/expand all/i);
  });

  it("only caps height after expand, never in the truncated/collapsed state (BUG1)", async () => {
    // feat-409 protoalign BUG1: 截断态必须平铺无滚——高度上限只由 --expanded 容器
    // 控制。collapsed 态不带 --expanded,展开后才带。覆盖 write(用 .chat-tool-call-pre
    // 内层,曾因该类常驻 max-height 导致截断态假滚动)。
    const user = userEvent.setup();
    const LONG_CONTENT = Array.from({ length: 120 }, (_, i) => `row ${i + 1}`).join("\n");
    const { container } = renderSingle({
      id: "w1",
      name: "write",
      status: "completed",
      input: {},
      output: "docs/big.md · 新建 1.2KB",
      detail: { path: "docs/big.md", content: LONG_CONTENT, bytes: 1200, truncated: false }
    });
    await open();
    // 截断态:有 long-output 容器,但不带 --expanded(无滚动盒)。
    const block = container.querySelector(".chat-tool-long-output");
    expect(block).not.toBeNull();
    expect(block?.classList.contains("chat-tool-long-output--expanded")).toBe(false);
    // 内层 pre 不自带滚动盒类(高度只归 --expanded 容器管)。
    expect(container.querySelector(".chat-tool-long-output .chat-tool-call-pre")).not.toBeNull();
    // 点开后容器才加 --expanded(此时才限高滚动)。
    await user.click(screen.getByText(/expand all/i));
    expect(
      container.querySelector(".chat-tool-long-output")?.classList.contains(
        "chat-tool-long-output--expanded"
      )
    ).toBe(true);
  });

  it("does not show an expand toggle for short write content (BUG1)", async () => {
    // 短 write 内容:无截断、无 "展开全部"、无滚动按钮。
    renderSingle({
      id: "w2",
      name: "write",
      status: "completed",
      input: {},
      output: "docs/x.md · 新建 28B",
      detail: { path: "docs/x.md", content: "# Title\nbody text", bytes: 28, truncated: false }
    });
    await open();
    expect(screen.queryByText(/expand all/i)).not.toBeInTheDocument();
    expect(screen.getByText(/body text/)).toBeInTheDocument();
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

// feat-414-M1 W3: 折叠态工具徽标 toggle button 不含求和耗时（无 `· Xs` 后缀）
describe("feat-414-M1 · collapsed toggle has no total duration (W3)", () => {
  const COMPLETED_CALLS: ToolCall[] = [
    { id: "c1", name: "bash", status: "completed", input: {}, output: "ok", duration_ms: 1200 },
    { id: "c2", name: "read", status: "completed", input: {}, output: "ok", duration_ms: 800 },
  ];

  it("does not show total duration in the collapsed toggle button text", () => {
    render(<ToolCallsPanel toolCalls={COMPLETED_CALLS} />);
    const btn = screen.getByRole("button", { name: /tool call/i });
    // Must not contain a pattern like "· 1.2s" or "· 800ms"
    expect(btn.textContent).not.toMatch(/·\s*\d/);
  });
});

// feat-434-M1: inline gate region (是否授权) vs result region (执行结果), denied dedup,
// failTag i18n, collapsed-state approval count suffix. Default test locale is "en";
// the gate/result/count assertions run in zh and en where the文案随语言.
import { setLanguage } from "../../../../i18n";

describe("ToolCallsPanel · approval gate region (feat-434-M1)", () => {
  async function expandPanel() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /tool call/i }));
  }

  afterEach(() => setLanguage("en"));

  it("shows the authorized gate near the name for a user-allowed success (zh)", async () => {
    setLanguage("zh");
    const calls: ToolCall[] = [
      { id: "a1", name: "bash", status: "completed", input: {}, output: "npm run build", duration_ms: 1200, approval: "user_allow" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const gate = container.querySelector(".chat-tool-call-gate");
    expect(gate).not.toBeNull();
    expect(gate?.textContent).toBe("已授权");
    expect(gate?.className).toContain("chat-tool-call-gate--allow");
    expect(container.querySelector(".chat-tool-call-duration")?.textContent).toContain("1.2s");
  });

  it("renders the authorized gate label in English when locale is en", async () => {
    const calls: ToolCall[] = [
      { id: "a1", name: "bash", status: "completed", input: {}, output: "x", approval: "user_allow" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(container.querySelector(".chat-tool-call-gate")?.textContent).toBe("Authorized");
  });

  it("authorized-but-failed shows BOTH gate and the fail tag (key boundary, zh)", async () => {
    setLanguage("zh");
    const calls: ToolCall[] = [
      {
        id: "f1", name: "bash", status: "failed", input: {}, output: "npm test",
        duration_ms: 3100, approval: "user_allow",
        detail: { command: "npm test", exit_code: 1 }
      }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(container.querySelector(".chat-tool-call-gate")?.textContent).toBe("已授权");
    expect(container.querySelector(".chat-tool-call-fail-tag")?.textContent).toBe("退出码 1");
  });

  it("failTag follows the interface language: exit code zh vs en", async () => {
    const calls: ToolCall[] = [
      { id: "f1", name: "bash", status: "failed", input: {}, output: "t", detail: { command: "x", exit_code: 1 } }
    ];
    // en
    const en = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(en.container.querySelector(".chat-tool-call-fail-tag")?.textContent).toBe("exit 1");
    en.unmount();
    // zh
    setLanguage("zh");
    const zh = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(zh.container.querySelector(".chat-tool-call-fail-tag")?.textContent).toBe("退出码 1");
  });

  it("failTag generic 失败/failed follows language (no exit code)", async () => {
    const calls: ToolCall[] = [
      { id: "g1", name: "memory", status: "completed", input: {}, output: "m", detail: { success: false } }
    ];
    const en = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(en.container.querySelector(".chat-tool-call-fail-tag")?.textContent).toBe("failed");
    en.unmount();
    setLanguage("zh");
    const zh = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(zh.container.querySelector(".chat-tool-call-fail-tag")?.textContent).toBe("失败");
  });

  it("denied row shows deny gate + not-run result, and NO duplicate reason badge (zh)", async () => {
    setLanguage("zh");
    const calls: ToolCall[] = [
      { id: "d1", name: "bash", status: "failed", input: {}, output: "rm -rf x", reason: "denied", approval: "user_deny" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    const gate = container.querySelector(".chat-tool-call-gate");
    expect(gate?.textContent).toBe("已拒绝");
    expect(gate?.className).toContain("chat-tool-call-gate--deny");
    expect(container.textContent).toContain("未执行");
    expect(container.querySelector(".chat-tool-call-reason")).toBeNull();
    expect(container.querySelector(".chat-tool-call-fail-tag")).toBeNull();
  });

  it("historical denied row (reason only, no approval) still shows the deny gate", async () => {
    setLanguage("zh");
    const calls: ToolCall[] = [
      { id: "h1", name: "bash", status: "failed", input: {}, output: "rm x", reason: "denied" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(container.querySelector(".chat-tool-call-gate")?.textContent).toBe("已拒绝");
    expect(container.querySelector(".chat-tool-call-reason")).toBeNull();
  });

  it("non-denied reason (timed_out) stays in the result region, not the gate", async () => {
    const calls: ToolCall[] = [
      { id: "t1", name: "bash", status: "failed", input: {}, reason: "timed_out" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(container.querySelector(".chat-tool-call-gate")).toBeNull();
    expect(container.querySelector(".chat-tool-call-reason")).not.toBeNull();
  });

  it("auto-allowed / plain tool shows no gate region", async () => {
    const calls: ToolCall[] = [
      { id: "p1", name: "read", status: "completed", input: {}, output: "ok", duration_ms: 200 }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    await expandPanel();
    expect(container.querySelector(".chat-tool-call-gate")).toBeNull();
  });

  it("collapsed-state suffix shows approval count + allow/deny segments (only non-zero, zh)", () => {
    setLanguage("zh");
    const calls: ToolCall[] = [
      { id: "1", name: "bash", status: "completed", input: {}, output: "a", approval: "user_allow" },
      { id: "2", name: "bash", status: "completed", input: {}, output: "b", approval: "user_allow" },
      { id: "3", name: "bash", status: "failed", input: {}, output: "c", approval: "user_deny", reason: "denied" },
      { id: "4", name: "read", status: "completed", input: {}, output: "d" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    const btn = container.querySelector(".chat-tool-calls-toggle") as HTMLElement;
    expect(btn.textContent).toContain("3 次授权");
    expect(btn.textContent).toContain("2 允许");
    expect(btn.textContent).toContain("1 拒绝");
  });

  it("collapsed-state suffix omits the deny segment when there are no denials (zh)", () => {
    setLanguage("zh");
    const calls: ToolCall[] = [
      { id: "1", name: "bash", status: "completed", input: {}, output: "a", approval: "user_allow" },
      { id: "2", name: "read", status: "completed", input: {}, output: "b" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    const btn = container.querySelector(".chat-tool-calls-toggle") as HTMLElement;
    expect(btn.textContent).toContain("1 允许");
    expect(btn.textContent).not.toContain("拒绝");
  });

  it("no approval count suffix when no call was user-decided (empty state, zh)", () => {
    setLanguage("zh");
    const calls: ToolCall[] = [
      { id: "1", name: "read", status: "completed", input: {}, output: "a" }
    ];
    const { container } = render(<ToolCallsPanel toolCalls={calls} />);
    const btn = container.querySelector(".chat-tool-calls-toggle") as HTMLElement;
    expect(btn.textContent).not.toContain("授权");
  });
});
