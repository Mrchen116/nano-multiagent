import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { deriveTurnTokenUsage } from "@deepseek-ai/dsh-token-meter/client";
import { outputTokens } from "../src/workflow/budget.js";
import { prepareProfile, RuntimeClient } from "../lib/client.js";

const until = (fn: () => unknown, options = {}) =>
  expect.poll(fn, { timeout: 10000, ...options });

it("executes native JavaScript and children, recovers durable prefixes, and keeps shared budget ownership", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-workflow-"));
  let client: RuntimeClient | undefined;
  let logs = "";
  const meta = {
    name: "acceptance",
    description: "Native workflow acceptance",
  };
  const script = `await phase('work'); const values = await pipeline(['A','B'], (value,item,index)=>agent('WF_CHILD_'+item,{label:item,schema:{type:'object',properties:{text:{type:'string'}},required:['text'],additionalProperties:false}}), (value,item,index)=>agent('WF_CHILD_'+value.text+'_next')); await log('finished'); return {values,spent:await budget.spent(),remaining:await budget.remaining()};`;
  try {
    await writeFile(
      join(home, "fixture.mjs"),
      `import {appendFile} from 'node:fs/promises';
export const name='workflow-fixture'; export const inject=['llm'];
export function apply(ctx) {
 const seen=new Set();
 ctx.on('llm/stream',async function*(o) {
   const input=o.messages.findLast(m=>m.role==='user'&&m.content.some(c=>c.type==='text'&&(c.text.startsWith('WF_CHILD_')||c.text==='launch')));
   const saved=o.messages.findLast(m=>m.source?.kind==='nano-workflow-invocation');
   if(saved&&!seen.has(saved.id)){seen.add(saved.id);const args=JSON.parse(saved.content[0].text.match(/with (.*)\\. Preserve/)[1]);yield {type:'block-end',index:0,block:{type:'tool-call',id:saved.id+'-launch',name:'workflow',arguments:JSON.stringify(args)}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
   const text=input?.content.find(c=>c.type==='text')?.text||'';
   if(text.startsWith('WF_CHILD_')) {
     await appendFile(process.env.DSH_HOME+'/children.jsonl',JSON.stringify({text,provider:o.provider,model:o.model,tools:o.tools?.map(t=>t.name)})+'\\n');
     if(o.tools?.some(tool=>tool.name==='structured_output'))yield {type:'block-end',index:0,block:{type:'tool-call',id:input.id+'-structured',name:'structured_output',arguments:JSON.stringify({text:text.slice(9)})}};else yield {type:'block-end',index:0,block:{type:'text',text:text.slice(9)}};
     yield {type:'usage',usage:{inputTokens:0,outputTokens:3,cacheReadTokens:0,cacheWriteTokens:0}};
     yield {type:'finish',reason:{kind:o.tools?.some(tool=>tool.name==='structured_output')?'tool-calls':'stop'}}; return;
   }
   if(text==='launch'&&!seen.has(input.id)) { seen.add(input.id); yield {type:'block-end',index:0,block:{type:'tool-call',id:'workflow-call',name:'workflow',arguments:JSON.stringify({script:${JSON.stringify(script)},meta:${JSON.stringify(meta)}})}}; yield {type:'usage',usage:{inputTokens:0,outputTokens:2,cacheReadTokens:0,cacheWriteTokens:0}}; yield {type:'finish',reason:{kind:'tool-calls'}}; return; }
   if(text==='launch'&&!seen.has('read')){seen.add('read');yield {type:'block-end',index:0,block:{type:'tool-call',id:'workflow-read',name:'workflow',arguments:JSON.stringify({action:'read'})}};yield{type:'usage',usage:{inputTokens:0,outputTokens:0,cacheReadTokens:0,cacheWriteTokens:0}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
   yield {type:'block-end',index:0,block:{type:'text',text:'Started'}}; yield {type:'usage',usage:{inputTokens:0,outputTokens:1,cacheReadTokens:0,cacheWriteTokens:0}};yield {type:'finish',reason:{kind:'stop'}};
 });
}`,
    );
    await prepareProfile(home, [
      { insert: [{ id: "workflow-fixture", name: join(home, "fixture.mjs") }] },
    ]);
    const binding = {
      sessionId: "workflow",
      agentId: "a",
      revision: "1",
      ownerId: "owner",
      cwd: home,
    };
    const initialize = async (bindings: unknown[]) => {
      client = new RuntimeClient({
        home,
        cwd: home,
        env: { NANO_OWNER_CONFIG_ROOT: join(home, "owner") },
        onLog: (text) => (logs += text),
      });
      await client.rpc.request("initialize", {
        protocol: 1,
        agents: [
          {
            agentId: "a",
            revision: "1",
            provider: "deepseek-official",
            model: "deepseek-flash",
            toolAllowlist: ["workflow", "read"],
            workflow: { outputTokenTarget: 100 },
          },
        ],
        bindings,
      });
    };
    await initialize([]);
    await client!.rpc.request("session.ensure", binding);
    await client!.rpc.request("session.submit", {
      sessionId: "workflow",
      inputId: "launch",
      mode: "followup",
      content: [{ type: "text", text: "launch" }],
      source: {
        kind: "human",
        actorId: "owner",
        channel: "test",
        messageId: "launch",
      },
    });
    const read = () =>
      client!.rpc.request("workflow.read", {
        sessionId: "workflow",
      }) as Promise<any[]>;
    await until(async () => (await read())[0]?.state, { timeout: 15000 }).toBe(
      "completed",
    );
    const parentObservation = (await client!.rpc.request("session.observe", {
      sessionId: "workflow",
    })) as { events: import("@deepseek-ai/dsh-session").SessionEvent[] };
    expect(parentObservation.events.find((event: any) => event.type === 'tool/result' && event.data.message.toolCallId === 'workflow-read')).toMatchObject({data:{message:{isError:false}}});
    expect(
      deriveTurnTokenUsage(
        parentObservation.events.slice(
          parentObservation.events.findIndex(
            (event) => event.type === "turn/start",
          ),
          parentObservation.events.findIndex(
            (event) => event.type === "turn/end",
          ) + 1,
        ),
      )?.outputTokens,
    ).toBe(outputTokens(parentObservation.events));
    const usage = await client!.rpc.request('usage.read', {sessionId: 'workflow'}) as {sessionId: string;turn: number;usage: {total_tokens: number}}[];
    expect(new Set(usage.map(item => item.sessionId)).size).toBe(5);
    expect(usage.reduce((sum, item) => sum + item.usage.total_tokens, 0)).toBe(15);
    const first = (await read())[0]!;
    expect(first.result.value.values).toEqual(["A_next", "B_next"]);
    expect(first.calls).toHaveLength(4);
    expect(first.result.value.spent).toBe(15);
    const children = (await readFile(join(home, "children.jsonl"), "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    expect(children).toHaveLength(4);
    for (const child of children) {
      expect(child.model).toBe("deepseek-flash");
      expect(child.tools).not.toContain("workflow");
    }
    await client!.shutdown();
    client = undefined;
    await initialize([binding]);
    expect(await client!.rpc.request('usage.read', {sessionId: 'workflow'})).toEqual(usage);
    const replay = (await client!.rpc.request("workflow.control", {
      sessionId: "workflow",
      runId: first.id,
      action: "resume",
    })) as { runId: string };
    await until(
      async () => (await read()).find((r) => r.id === replay.runId)?.state,
      { timeout: 15000 },
    ).toBe("completed");
    const second = (await read()).find((r) => r.id === replay.runId)!;
    expect(second.calls.every((call: any) => call.replayed)).toBe(true);
    expect(
      (await readFile(join(home, "children.jsonl"), "utf8")).trim().split("\n"),
    ).toHaveLength(4);
    expect(second.result.value.values).toEqual(first.result.value.values);
    const saved = (await client!.rpc.request("session.command", {
      sessionId: "workflow",
      id: "save-workflow",
      action: "workflows",
      argument: first.id + " save personal saved-acceptance",
    })) as { text: string };
    expect(JSON.parse(saved.text).name).toBe("saved-acceptance");
    await client!.rpc.request("session.submit", {
      sessionId: "workflow",
      inputId: "saved-invocation",
      mode: "followup",
      content: [
        { type: "text", text: '/saved-acceptance {"topic":"from slash"}' },
      ],
      source: {
        kind: "human",
        actorId: "owner",
        channel: "test",
        messageId: "saved-invocation",
      },
    });
    await until(
      async () =>
        (await read()).find((r) => r.meta.name === "saved-acceptance")?.state,
      { timeout: 15000 },
    ).toBe("completed");
    const invoked = (await read()).filter(
      (r) => r.meta.name === "saved-acceptance",
    );
    expect(invoked).toHaveLength(1);
    expect(invoked[0].args).toEqual({ topic: "from slash" });
    await client!.shutdown();
    client = undefined;
  } catch (error) {
    const evidence = client
      ? await client.rpc
          .request("session.observe", { sessionId: "workflow" })
          .catch(() => null)
      : null;
    throw new Error(
      String(error) +
        "\n" +
        logs +
        "\n" +
        JSON.stringify(
          evidence?.events?.filter((event: any) =>
            [
              "agent/error",
              "turn/end",
              "tool/call",
              "tool/result",
              "error",
            ].includes(event.type),
          ),
        ),
      { cause: error },
    );
  } finally {
    if (client) {
      client.process.kill("SIGKILL");
      await client.exited;
    }
    await rm(home, { recursive: true, force: true });
  }
}, 40000);
