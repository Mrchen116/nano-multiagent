import { createServer } from "node:http";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { prepareProfile, RuntimeClient } from "@nano/dsh-integration/client";
import { NodeConfiguration } from "../src/configuration.js";
import { providerProfiles } from "../src/providers.js";

it("sends adaptive thinking and selectable proxy effort through the actual native Anthropic HTTP adapter", async () => {
  const bodies: Record<string, any>[] = [];
  const server = createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;
    bodies.push(JSON.parse(body));
    res.writeHead(200, { "content-type": "text/event-stream" });
    for (const event of [
      {
        type: "message_start",
        message: {
          id: "wire-message",
          type: "message",
          role: "assistant",
          model: bodies.at(-1)!.model,
          content: [],
          usage: { input_tokens: 4, output_tokens: 0 },
        },
      },
      {
        type: "content_block_start",
        index: 0,
        content_block: { type: "text", text: "" },
      },
      {
        type: "content_block_delta",
        index: 0,
        delta: { type: "text_delta", text: "wire reply" },
      },
      { type: "content_block_stop", index: 0 },
      {
        type: "message_delta",
        delta: { stop_reason: "end_turn", stop_sequence: null },
        usage: { output_tokens: 2 },
      },
      { type: "message_stop" },
    ])
      res.write(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
    res.end();
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const home = await mkdtemp(join(tmpdir(), "nano-provider-"));
  let client: RuntimeClient | undefined;
  let logs = "";
  try {
    const path = join(home, "node.json");
    await writeFile(
      path,
      JSON.stringify({
        node: {},
        agents: [],
        llm: {
          default_model: "proxy-adaptive",
          providers: [
            {
              name: "anthropic",
              base_url: `http://127.0.0.1:${(server.address() as { port: number }).port}`,
              models: [
                {
                  name: "proxy-adaptive",
                  context_window: 100000,
                  extra_request_body: { thinking: { type: "adaptive" } },
                },
                {
                  name: "proxy-selectable",
                  context_window: 200000,
                  reasoning: {
                    default: "high",
                    levels: ["none", "high", "xhigh", "max"],
                  },
                },
              ],
            },
          ],
        },
      }),
    );
    const config = await NodeConfiguration.read(path);
    const profile = providerProfiles(config.value.llm);
    await prepareProfile(home, [
      { id: "llm-pi-ai", config: { providers: profile.providers } },
    ]);
    client = new RuntimeClient({
      home,
      cwd: home,
      env: profile.env,
      onLog: (value) => {
        logs += value;
      },
    });
    const agents = [
      config.runtime({
        agent_id: "adaptive",
        workspace_root: home,
        tool_allowlist: [],
      }),
      ...["high", "max", "none"].map((effort) =>
        config.runtime({
          agent_id: effort,
          workspace_root: home,
          default_model: "proxy-selectable",
          reasoning_effort: effort,
          tool_allowlist: [],
        }),
      ),
    ];
    await client.rpc.request("initialize", {
      protocol: 1,
      agents,
      bindings: [],
    });
    for (const agent of agents) {
      const sessionId = agent.agentId;
      await client.rpc.request("session.ensure", {
        sessionId,
        agentId: agent.agentId,
        revision: agent.revision,
        ownerId: "owner",
        cwd: home,
      });
      await client.rpc.request("session.submit", {
        sessionId,
        inputId: sessionId,
        mode: "followup",
        content: [{ type: "text", text: "hello" }],
        source: {
          kind: "human",
          actorId: "owner",
          channel: "test",
          messageId: sessionId,
        },
      });
      await expect
        .poll(
          async () =>
            (
              (await client!.rpc.request("session.lookup", {
                sessionId,
                inputId: sessionId,
              })) as { terminal?: { kind: string } }
            ).terminal?.kind,
        )
        .toBe("completed");
    }
    expect(bodies).toHaveLength(4);
    expect(bodies[0]!.thinking).toMatchObject({ type: "adaptive" });
    expect(bodies[1]!.output_config).toMatchObject({ effort: "high" });
    expect(bodies[2]!.output_config).toMatchObject({ effort: "max" });
    expect(bodies[2]!.thinking.type).toBe("adaptive");
    expect(bodies[3]!.thinking?.type).not.toBe("adaptive");
    await client.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    if (client) {
      client.process.kill("SIGKILL");
      await client.exited;
    }
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 20_000);
