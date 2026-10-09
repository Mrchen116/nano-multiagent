import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { prepareProfile, RuntimeClient } from "../lib/client.js";
import { approvalDefaults } from "../../product-contracts/src/approval.js";
const until = (fn: () => unknown, options = {}) =>
  expect.poll(fn, { timeout: 10000, ...options });

it("routes a background Workflow child approval to its original human parent input", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-workflow-approval-"));
  let client: RuntimeClient | undefined;
  let logs = "";
  try {
    await writeFile(
      join(home, "fixture.mjs"),
      `import {writeFile} from 'node:fs/promises';export const name='wf-approval';export const inject=['llm','tools'];
 export function apply(ctx){ctx.tools.register({name:'fixture_effect',description:'Mutate a fixture',parameters:{type:'object',properties:{}},output:{schema:{},render:()=>[{type:'text',text:'done'}]},execute:async()=>{await writeFile(process.env.DSH_HOME+'/effect','approved');return {};}});const seen=new Set();ctx.on('llm/stream',async function*(o){const input=o.messages.findLast(m=>m.role==='user'&&m.content.some(c=>c.type==='text'&&['launch','CHILD'].includes(c.text)));const text=input?.content[0]?.text;
 if(!seen.has(input.id)){seen.add(input.id);yield {type:'block-end',index:0,block:{type:'tool-call',id:input.id+'-call',name:text==='CHILD'?'fixture_effect':'workflow',arguments:text==='CHILD'?'{}':JSON.stringify({meta:{name:'approval',description:'approval'},script:'return await agent("CHILD");'})}};yield {type:'finish',reason:{kind:'tool-calls'}};return;}yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};});}`,
    );
    await prepareProfile(home, [
      { insert: [{ id: "wf-approval", name: join(home, "fixture.mjs") }] },
    ]);
    client = new RuntimeClient({ home, cwd: home, onLog: (t) => (logs += t) });
    const requests: any[] = [];
    client.rpc.onNotification((method, value) => {
      if (method === "approval.request") requests.push(value);
    });
    await client.rpc.request("initialize", {
      protocol: 1,
      agents: [
        {
          agentId: "a",
          revision: "1",
          mode: "single_thread",
          provider: "deepseek-official",
          model: "deepseek-flash",
          toolAllowlist: ["workflow", "fixture_effect"],
          approval: {
            ...approvalDefaults,
            enabled: false,
            alwaysAllowTools: ["workflow"],
            globalRoot: home,
          },
        },
      ],
      bindings: [],
    });
    await client.rpc.request("session.ensure", {
      sessionId: "approval-root",
      agentId: "a",
      revision: "1",
      ownerId: "owner",
      cwd: home,
    });
    await client.rpc.request("session.submit", {
      sessionId: "approval-root",
      inputId: "human-input",
      mode: "followup",
      content: [{ type: "text", text: "launch" }],
      source: {
        kind: "human",
        actorId: "owner",
        channel: "test",
        messageId: "human",
      },
    });
    await until(() => requests.length).toBe(1);
    expect(requests[0]).toMatchObject({
      sessionId: "approval-root",
      toolName: "fixture_effect",
      inputIds: ["human-input"],
    });
    expect(requests[0].childSessionId).not.toBe("approval-root");
    await expect(readFile(join(home, "effect"), "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
    await client.rpc.request("approval.answer", {
      requestId: requests[0].requestId,
      decision: "allowed-once",
    });
    await until(async () => {
      try {
        return await readFile(join(home, "effect"), "utf8");
      } catch {
        return "";
      }
    }).toBe("approved");
    await until(
      async () =>
        (
          (await client!.rpc.request("workflow.read", {
            sessionId: "approval-root",
          })) as any[]
        )[0]?.state,
    ).toBe("completed");
    await client.shutdown();
    client = undefined;
  } catch (error) {
    const evidence = client
      ? await client.rpc
          .request("workflow.read", { sessionId: "approval-root" })
          .catch(() => null)
      : null;
    throw new Error(
      String(error) + "\n" + logs + "\n" + JSON.stringify(evidence),
      { cause: error },
    );
  } finally {
    if (client) {
      client.process.kill("SIGKILL");
      await client.exited;
    }
    await rm(home, { recursive: true, force: true });
  }
}, 20000);
