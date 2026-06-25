/**
 * PermissionCard tests.
 *
 * bugfix-367: resolved 状态由 prop (request.status === "resolved") 派生,组件
 * 不再用本地 useState 缓存"已解决",所以"点击后立刻看到 resolved"那条断言
 * 改成"onResolved callback 被调用,且后续传入 status='resolved' prop 时渲染
 * resolved 标签"。此外新增三组断言覆盖 §A:
 *  - tool_input 直接渲染到 chat-permission-cmd
 *  - tool_input.description (bash/task/agent 才有) 渲染成 chat-permission-desc
 *  - 删除 useState 派生 prop 反模式: 新 pending request 进来时不会卡在
 *    旧 resolved 上
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../../features/auth/auth-fetch", () => ({
  authFetch: vi.fn(),
}));

import "../../../../i18n";
import * as authFetchModule from "../../../../features/auth/auth-fetch";
import type { PermissionOption, PermissionRequest } from "../chat-types";
import { PermissionCard } from "./permission-card";

const SAMPLE_OPTIONS: PermissionOption[] = [
  { id: "allow_once", label: "Allow once", description: "Allow this single action" },
  { id: "deny", label: "Deny", description: "Block this action" },
  { id: "allow_session", label: "Allow for session", description: "Allow all calls this session" },
];

const SAMPLE_REQUEST: PermissionRequest = {
  request_id: "req-abc",
  tool_name: "bash",
  tool_input: { command: "rm -rf /tmp/old" },
  question: "Allow bash to run this command?",
  options: SAMPLE_OPTIONS,
  status: "pending",
};

describe("PermissionCard — pending state", () => {
  it("renders tool name in the card header", () => {
    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    const elements = screen.getAllByText(/bash/i);
    expect(elements.length).toBeGreaterThan(0);
  });

  it("renders the question text", () => {
    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.getByText(/Allow bash to run this command/i)).toBeInTheDocument();
  });

  it("renders all option buttons", () => {
    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: /allow once/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /deny/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /allow for session/i })).toBeInTheDocument();
  });

  // bugfix-367 §A: tool_input 必须直接渲染到卡内 —— 用户不再需要去点开
  // 上方"工具调用详情"才能看到要授权的命令/参数。
  it("renders tool_input as JSON inside the card (raw input block)", () => {
    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    const block = screen.getByTestId("permission-tool-input");
    expect(block.textContent).toContain("rm -rf /tmp/old");
  });

  // bugfix-367 §A: bash / task / agent 工具的 input_schema 提供了 `description`
  // 字段供 LLM 写人类可读摘要,卡内单独突出渲染该行;raw input 区不重复显示。
  it("renders tool_input.description as a separate summary line, stripped from raw block", () => {
    const req: PermissionRequest = {
      ...SAMPLE_REQUEST,
      tool_input: { command: "rm hello.py", description: "删除 hello.py", timeout: 5 },
    };
    render(
      <PermissionCard
        request={req}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.getByTestId("permission-description").textContent).toBe("删除 hello.py");
    // description 应该不再出现在 raw input 区里
    const raw = screen.getByTestId("permission-tool-input").textContent ?? "";
    expect(raw).toContain("rm hello.py");
    expect(raw).toContain("timeout");
    expect(raw).not.toContain("description");
  });

  it("does not render description line for tools without that field", () => {
    const req: PermissionRequest = {
      ...SAMPLE_REQUEST,
      tool_input: { file_path: "/tmp/foo.py", content: "print('x')" },
    };
    render(
      <PermissionCard
        request={req}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.queryByTestId("permission-description")).not.toBeInTheDocument();
  });
});

describe("PermissionCard — submitting state", () => {
  it("disables all buttons after clicking one option", async () => {
    const user = userEvent.setup();
    let resolvePost!: (value: Response) => void;
    const mockFetch = vi.fn(() =>
      new Promise<Response>((res) => {
        resolvePost = res;
      })
    );

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    await user.click(screen.getByRole("button", { name: /allow once/i }));

    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
    resolvePost(new Response(JSON.stringify({ ok: true }), { status: 200 }));
  });
});

// bugfix-367: 决策结果不再用本地 useState 缓存。点击后 onResolved 被回调,
// 真正的视觉"resolved"由 reducer 接到 permission.resolved WS 事件后改 prop
// 触发。所以测试拆成 (a) callback 被调 (b) 传入 status="resolved" prop 时渲染。
describe("PermissionCard — POST success → onResolved callback", () => {
  it("invokes onResolved with the chosen decision after successful POST (no local resolved state)", async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    const onResolved = vi.fn();

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={onResolved}
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    await user.click(screen.getByRole("button", { name: /allow once/i }));
    await waitFor(() => {
      expect(onResolved).toHaveBeenCalledWith("allow_once");
    });
    // 卡片仍然是 pending 形态(因为 prop 没变),决策后的"已允许"小条由父组件
    // 收到 WS event 改 prop 后再渲染。
    expect(screen.queryByTestId("permission-resolved")).not.toBeInTheDocument();
  });
});

// feat-434 决策 3: PermissionCard 不再渲染 resolved 形态 —— 已决审批并入工具行的
// 闸门区（已授权/已拒绝），独立的「已决卡」彻底取消。resolved 时组件渲染空。
describe("PermissionCard — resolved renders nothing (feat-434 决策 3)", () => {
  it("renders nothing when status='resolved' decision='allow_once'", () => {
    const { container } = render(
      <PermissionCard
        request={{ ...SAMPLE_REQUEST, status: "resolved", decision: "allow_once" }}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.queryByTestId("permission-resolved")).not.toBeInTheDocument();
    expect(container.querySelector(".chat-permission-card")).toBeNull();
  });

  it("renders nothing when status='resolved' decision='deny'", () => {
    const { container } = render(
      <PermissionCard
        request={{ ...SAMPLE_REQUEST, status: "resolved", decision: "deny" }}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.queryByTestId("permission-resolved")).not.toBeInTheDocument();
    expect(container.querySelector(".chat-permission-card")).toBeNull();
  });
});

describe("PermissionCard — error state", () => {
  it("shows error text when POST fails", async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockRejectedValue(new Error("Network error"));

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
        fetchFn={mockFetch as unknown as typeof fetch}
      />
    );

    await user.click(screen.getByRole("button", { name: /allow once/i }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /allow once/i })).toBeEnabled();
    });
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("PermissionCard — M4 auth header (default fetchFn → authFetch)", () => {
  beforeEach(() => {
    vi.mocked(authFetchModule.authFetch).mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls authFetch (not bare fetch) when no fetchFn prop is supplied", async () => {
    const user = userEvent.setup();
    vi.mocked(authFetchModule.authFetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "forwarded" }), { status: 200 })
    );
    const onResolved = vi.fn();

    render(
      <PermissionCard
        request={SAMPLE_REQUEST}
        conversationId="conv-default-auth"
        messageId="msg-1"
        onResolved={onResolved}
      />
    );

    await user.click(screen.getByRole("button", { name: /allow once/i }));
    await waitFor(() => {
      expect(onResolved).toHaveBeenCalledWith("allow_once");
    });

    expect(authFetchModule.authFetch).toHaveBeenCalledOnce();
    const [url, init] = vi.mocked(authFetchModule.authFetch).mock.calls[0];
    expect(url).toContain("/im/v1/conversations/conv-default-auth/permissions/req-abc");
    expect((init as RequestInit).method).toBe("POST");
  });
});

// bugfix-367 核心场景: 同一组件实例(同 message,同 React key=request_id)
// 上,prop 从 resolved 切换到一个新的 pending request 时,组件不能再卡在
// 旧 resolved 上(根因 3: 删除 useState 派生 prop 反模式后这条自动满足,
// 但仍写一条断言锁定该行为防回归)。
describe("PermissionCard — prop change reactivity", () => {
  it("re-renders as pending when prop switches from resolved to a fresh pending request", () => {
    const { rerender } = render(
      <PermissionCard
        request={{ ...SAMPLE_REQUEST, request_id: "req-old", status: "resolved", decision: "allow_once" }}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    // feat-434 决策 3: resolved 渲染空（无独立已决卡）。
    expect(screen.queryByTestId("permission-resolved")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /allow once/i })).not.toBeInTheDocument();

    // 注意: 实际生产链路下,新 ask 会被 message-pane 用 key={request_id} 强制
    // remount —— 但即便没有 key 切换,这里也必须能正确反映 prop。
    rerender(
      <PermissionCard
        request={{ ...SAMPLE_REQUEST, request_id: "req-new", status: "pending" }}
        conversationId="conv-1"
        messageId="msg-1"
        onResolved={() => {}}
      />
    );
    expect(screen.queryByTestId("permission-resolved")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /allow once/i })).toBeEnabled();
  });
});
