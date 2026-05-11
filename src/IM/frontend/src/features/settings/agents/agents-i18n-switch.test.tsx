import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { setLanguage } from "../../../i18n";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

beforeEach(() => {
  setLanguage("zh");
});

afterEach(() => {
  fetchMock.mockReset();
  setLanguage("en");
});

describe("agents pages i18n zh switch", () => {
  it("lists agents with Chinese header, retry CTA, and empty state copy", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/agents") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url === "/im/v1/nodes") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    expect(await screen.findByText("还没有 Agent")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "前往节点" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Agents" })).toBeInTheDocument();
  });

  it("renders detail page with Chinese card titles and Save button", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return new Response(
          JSON.stringify([
            {
              node_id: "node-1",
              owner_id: "owner-1",
              node_name: "MacBook",
              status: "online",
              last_heartbeat_at: "2026-03-13T10:00:00Z",
              agent_count: 1,
              version: "1.0.0"
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url === "/im/v1/agents/agent-zh-1/capabilities") {
        return new Response(
          JSON.stringify({
            node_id: "node-1",
            node_name: "MacBook",
            node_status: "online",
            capabilities_updated_at: "2026-03-13T10:00:00Z",
            skills: [],
            tools: [],
            model_options: ["codex_oauth:gpt-5.4"],
            platform_default_model: "codex_oauth:gpt-5.4",
            default_system_prompt: ""
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url === "/im/v1/agents/agent-zh-1/config") {
        return new Response(
          JSON.stringify({
            agent_id: "agent-zh-1",
            owner_id: "owner-1",
            display_name: "中文 Agent",
            description: "",
            system_prompt: "你是一个 Agent。",
            skills: [],
            tool_allowlist: [],
            group_reply_policy: "MENTION",
            default_model: "codex_oauth:gpt-5.4",
            workspace_root: "/tmp/agent-zh-1",
            workspace_is_default: true,
            profile_version: 1,
            bound_nodes: ["node-1"],
            updated_at: "2026-03-13T10:00:00Z"
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents/agent-zh-1"] });

    await screen.findByRole("heading", { name: "中文 Agent" });
    expect(screen.getByRole("heading", { name: "身份" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "行为" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "访问与模型" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "工作区与运行时" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /打开聊天/ })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "保存" })).toBeInTheDocument();
    });
  });

  it("renders create page with Chinese title, three cards, and Cancel/Create buttons", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes") {
        return new Response(
          JSON.stringify([
            {
              node_id: "node-1",
              owner_id: "owner-1",
              node_name: "MacBook",
              status: "online",
              last_heartbeat_at: "2026-03-13T10:00:00Z",
              agent_count: 0,
              version: "1.0.0"
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url === "/im/v1/nodes/node-1/capabilities") {
        return new Response(
          JSON.stringify({
            node_id: "node-1",
            node_name: "MacBook",
            node_status: "online",
            capabilities_updated_at: "2026-03-13T10:00:00Z",
            skills: [],
            tools: [],
            model_options: ["codex_oauth:gpt-5.4"],
            platform_default_model: "codex_oauth:gpt-5.4",
            default_system_prompt: ""
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(null, { status: 404 });
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes/node-1/agents/new"] });

    expect(await screen.findByRole("heading", { name: "新建 Agent" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "身份" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "行为" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "访问与模型" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /工作区/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "取消" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建 Agent" })).toBeInTheDocument();
  });
});
