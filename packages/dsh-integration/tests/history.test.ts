import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { prepareProfile, RuntimeClient } from "../lib/client.js";

it("forks a native message with its configuration and compacted prefix, independently and across restart", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-history-"));
  let client: RuntimeClient | undefined;
  let logs = "";
  await writeFile(
    join(home, "fixture.mjs"),
    `import {appendFile}from'node:fs/promises';export const name='history-fixture';export const inject=['llm','subagents'];export function apply(ctx){
    ctx.on('agent/pre-step',async({agent,messages,signal},next)=>{if(agent.session.header.origin!=='subagent'&&messages.some(m=>m.content.some(b=>b.type==='text'&&b.text.startsWith('fork-only')))){const run=await ctx.subagents.start('fork',{parent:agent,signal,label:'history-child',prompt:[{type:'text',text:'CHILD_FROM_HISTORY'}],toolFilter:{allow:[]}});try{await run.result;}finally{await run.dispose();}}return next();});
    ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({purpose:o.purpose,model:o.model,messages:o.messages,system:o.system})+'\\n');yield{type:'block-end',index:0,block:{type:'text',text:o.purpose==='compaction'?'HISTORY_SUMMARY':'Useful answer. '.repeat(100)}};yield{type:'finish',reason:{kind:'stop'},usage:{inputTokens:100,outputTokens:20}};});}`,
  );
  let config = {
    agentId: "a",
    revision: "1",
    provider: "fixture",
    model: "test",
    systemPrompt: "ORIGINAL_PERSONA",
    features: { memory_curation: false, skill_creation: false },
    toolAllowlist: ["read"],
  };
  const binding = {
    sessionId: "history-source",
    agentId: "a",
    revision: "1",
    ownerId: "owner",
    cwd: home,
  };
  const bindings = [binding];
  try {
    await prepareProfile(home, [
      {
        id: "llm-pi-ai",
        config: {
          providers: {
            fixture: {
              api: "openai-completions",
              baseURL: "http://127.0.0.1:9",
              apiKeyEnv: "NANO_TEST_KEY",
              models: [
                { id: "test", contextWindow: 100000 },
                { id: "next", contextWindow: 100000 },
              ],
            },
          },
        },
      },
      {
        id: "nano-compaction",
        config: { retainTokens: 0, headroomTokens: 100, maxTokens: 256 },
      },
      { insert: [{ id: "history-fixture", name: join(home, "fixture.mjs") }] },
    ]);
    const start = async () => {
      client = new RuntimeClient({
        home,
        cwd: home,
        env: { NANO_TEST_KEY: "fixture" },
        onLog: (text) => {
          logs += text;
        },
      });
      await client.rpc.request("initialize", {
        protocol: 1,
        agents: [config],
        bindings,
      });
      for (const b of bindings) await client.rpc.request("session.ensure", b);
    };
    await start();
    const submit = async (sessionId: string, id: string) => {
      await client!.rpc.request("session.submit", {
        sessionId,
        inputId: id,
        mode: "followup",
        content: [
          { type: "text", text: id + " Remember these facts. ".repeat(100) },
        ],
        source: {
          kind: "human",
          actorId: "owner",
          channel: "test",
          messageId: id,
        },
      });
      await expect
        .poll(
          async () =>
            (
              (await client!.rpc.request("session.lookup", {
                sessionId,
                inputId: id,
              })) as { terminal?: unknown }
            ).terminal,
        )
        .toBeTruthy();
      const evidence = (await client!.rpc.request("session.lookup", {
        sessionId,
        inputId: id,
      })) as { terminal: unknown };
      expect(evidence.terminal, JSON.stringify(evidence)).toMatchObject({
        kind: "completed",
      });
    };
    const observe = async (sessionId: string) =>
      (
        (await client!.rpc.request("session.observe", { sessionId })) as {
          events: { type: string; seq: number; data: any }[];
        }
      ).events;
    await submit(binding.sessionId, "one");
    await submit(binding.sessionId, "two");
    expect(
      await client!.rpc.request("session.command", {
        sessionId: binding.sessionId,
        id: "compact-history",
        action: "compact",
      }),
    ).toMatchObject({ success: true });
    await submit(binding.sessionId, "three");
    const point = (await observe(binding.sessionId)).findLast(
      (event) => event.type === "assistant/message",
    )!;
    config = {
      ...config,
      revision: "2",
      model: "next",
      systemPrompt: "NEW_PERSONA",
      toolAllowlist: ["write"],
    };
    await client!.rpc.request("configuration.apply", config);
    await submit(binding.sessionId, "after-point");
    const request = {
      sessionId: binding.sessionId,
      messageId: point.data.message.id,
      operationId: "new-conversation",
    };
    const fork = (await client!.rpc.request("session.fork", request)) as {
      sessionId: string;
      revision: string;
      idMap: Record<string, string>;
    };
    expect(await client!.rpc.request("session.fork", request)).toEqual(fork);
    expect(fork.idMap[point.data.message.id]).toBe(point.data.message.id);
    bindings.push({
      ...binding,
      sessionId: fork.sessionId,
      revision: fork.revision,
    });
    const forkEvents = await observe(fork.sessionId);
    expect(forkEvents.some((e) => e.type === "compaction/end")).toBe(true);
    expect(JSON.stringify(forkEvents)).not.toContain("after-point");
    const capabilities = async (id: string) =>
      client!.rpc.request("session.capabilities", { sessionId: id });
    expect(await capabilities(fork.sessionId)).toMatchObject({
      tools: ["read"],
    });
    expect(JSON.stringify(await capabilities(fork.sessionId))).toContain(
      "ORIGINAL_PERSONA",
    );
    await submit(fork.sessionId, "fork-only");
    expect(JSON.stringify(await observe(binding.sessionId))).not.toContain(
      "fork-only",
    );
    const requests = (await readFile(join(home, "requests.jsonl"), "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    const childRequest = requests.find((request) =>
      JSON.stringify(request.messages).includes("CHILD_FROM_HISTORY"),
    );
    expect(childRequest?.model).toBe("test");
    expect(JSON.stringify(childRequest)).toContain("ORIGINAL_PERSONA");
    expect(requests.at(-1).model).toBe("test");
    expect(JSON.stringify(requests.at(-1).messages)).toContain(
      "HISTORY_SUMMARY",
    );
    expect(JSON.stringify(requests.at(-1).messages)).not.toContain(
      "after-point",
    );
    const exportResult = (await client!.rpc.request("session.export", {
      sessionId: fork.sessionId,
    })) as { path: string };
    expect(await readFile(exportResult.path, "utf8")).toContain("fork-only");
    const readable = await readFile(
      join(home, ".nanoassistant/chat_history", `${fork.sessionId}.jsonl`),
      "utf8",
    );
    expect(readable).toContain("fork-only");
    expect(readable).not.toContain("after-point");
    await client!.shutdown();
    client = undefined;
    await start();
    expect(await capabilities(fork.sessionId)).toMatchObject({
      tools: ["read"],
    });
    expect(JSON.stringify(await capabilities(fork.sessionId))).toContain(
      "ORIGINAL_PERSONA",
    );
    await submit(fork.sessionId, "cold-fork");
    expect(await client!.rpc.request("session.fork", request)).toEqual(fork);
    config = { ...config, revision: "3" };
    await client!.rpc.request("configuration.apply", config);
    expect(await capabilities(fork.sessionId)).toMatchObject({
      tools: ["write"],
    });
    expect(JSON.stringify(await capabilities(fork.sessionId))).toContain(
      "NEW_PERSONA",
    );
    await client!.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    if (client) {
      client.process.kill("SIGKILL");
      await client.exited;
    }
    await rm(home, { recursive: true, force: true });
  }
}, 25000);
