import { expect, it } from "vitest";
import { ConversationHistory } from "../src/history.js";
import { NodeStore } from "../src/store.js";
import type { AgentConfiguration } from "@nano/product-contracts";
const config: AgentConfiguration = {
  agentId: "a",
  workspace: "/workspace",
  revision: "2",
  mode: "single_thread",
  provider: "p",
  model: "m",
};

it("binds only a successful native branch, preserves aliases and lets retry reuse the operation", async () => {
  const store = new NodeStore(":memory:", "owner");
  store.bind({
    sessionId: "source",
    conversationId: "external:a:feishu:app:dm:owner",
    agentId: "a",
    ownerId: "owner",
    cwd: "/workspace",
    revision: "1",
  });
  store.aliasConversation("a", "shadow", "external:a:feishu:app:dm:owner");
  const calls: unknown[] = [];
  let fail = true;
  const history = new ConversationHistory({
    store,
    agents: [config],
    runtime: {
      onNotification: () => () => {},
      request: async (method, value) => {
        calls.push([method, value]);
        if (method === "session.ensure") return {};
        if (fail) throw new Error("No native point");
        return {
          sessionId: "branch",
          revision: "1",
          idMap: { point: "point" },
        };
      },
    },
  });
  const request = {
    agent_id: "a",
    source_conversation_id: "shadow",
    new_conversation_id: "new",
    fork_point: { message_id: "point" },
  };
  try {
    expect(await history.fork(request)).toMatchObject({ ok: false });
    expect(store.bindingFor("a", "new")).toBeUndefined();
    fail = false;
    expect(await history.fork(request)).toMatchObject({
      ok: true,
      new_session_id: "branch",
    });
    expect(store.bindingFor("a", "new")?.sessionId).toBe("branch");
    expect(await history.fork(request)).toMatchObject({
      ok: true,
      new_session_id: "branch",
    });
    expect(calls).toContainEqual([
      "session.fork",
      { sessionId: "source", messageId: "point", operationId: "fork:a:new" },
    ]);
    expect(store.bindingFor("a", "shadow")?.sessionId).toBe("source");
  } finally {
    store.close();
  }
});

it("resolves every export before returning an ordinary Skill prompt without starting execution", async () => {
  const store = new NodeStore(":memory:", "owner");
  for (const name of ["one", "two"])
    store.bind({
      sessionId: name,
      conversationId: name,
      agentId: "a",
      ownerId: "owner",
      cwd: "/workspace",
      revision: "1",
    });
  const calls: string[] = [];
  let fail = true;
  let selected = true;
  const history = new ConversationHistory({
    store,
    agents: [config],
    runtime: {
      onNotification: () => () => {},
      request: async (method, value) => {
        calls.push(method);
        if (method === "configuration.selection")
          return {
            tools: ["skill"],
            skills: selected ? [{ name: "conversation-skill-distiller" }] : [],
          };
        if (method !== "session.export")
          throw new Error("Distill must not start execution");
        if (fail && (value as { sessionId: string }).sessionId === "two")
          throw new Error("Missing export");
        return {
          path: `/exports/${(value as { sessionId: string }).sessionId}.jsonl`,
        };
      },
    },
  });
  const request = {
    execution_agent_id: "a",
    target_scope: "global",
    sources: ["one", "two"].map((conversation_id) => ({
      conversation_id,
      source_agent_id: "a",
    })),
  };
  try {
    expect(await history.distill(request)).toMatchObject({
      error_code: "source_unavailable",
    });
    fail = false;
    const result = await history.distill(request);
    expect(result.prompt).toContain(
      "/skill:conversation-skill-distiller\nsource_jsonl_paths:\n  /exports/one.jsonl\n  /exports/two.jsonl\nexecution_agent_id: a\ntarget_scope: global",
    );
    expect(new Set(calls)).toEqual(
      new Set(["configuration.selection", "session.export"]),
    );
    selected = false;
    expect(await history.distill(request)).toMatchObject({
      error_code: "distiller_unavailable",
    });
  } finally {
    store.close();
  }
});
