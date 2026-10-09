import { mkdtemp, writeFile, readFile, rm, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { prepareProfile, RuntimeClient } from "../lib/client.js";

const until = (fn: () => unknown, options = {}) =>
  expect.poll(fn, { timeout: 10000, ...options });

it("controls real PTC and child lifetimes through pause, restart, stop, nested calls and cold interruption", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-workflow-lifecycle-"));
  let client: RuntimeClient | undefined;
  let logs = "";
  try {
    await writeFile(
      join(home, "fixture.mjs"),
      `import {appendFile,access} from 'node:fs/promises';import {setTimeout} from 'node:timers/promises';
export const name='workflow-life-fixture';export const inject=['llm'];
export function apply(ctx){const seen=new Set();ctx.on('llm/stream',async function*(o){
 const input=o.messages.findLast(m=>m.role==='user'&&m.content.some(c=>c.type==='text'&&(c.text.startsWith('WF_LAUNCH:')||c.text.startsWith('CHILD:'))));const text=input?.content.find(c=>c.type==='text')?.text||'';
 if(text.startsWith('CHILD:')){await appendFile(process.env.DSH_HOME+'/starts',text+'\\n');
  try {while(text.includes('BLOCK')){o.signal?.throwIfAborted();try{await access(process.env.DSH_HOME+'/release');break;}catch{}await setTimeout(10,undefined,{signal:o.signal});}
   yield {type:'block-end',index:0,block:{type:'text',text}};yield {type:'usage',usage:{inputTokens:0,outputTokens:3,cacheReadTokens:0,cacheWriteTokens:0}};yield {type:'finish',reason:{kind:'stop'}};
  } finally {await appendFile(process.env.DSH_HOME+'/ends',text+'\\n');}return;
 }
 if(text.startsWith('WF_LAUNCH:')&&!seen.has(input.id)){seen.add(input.id);yield {type:'block-end',index:0,block:{type:'tool-call',id:input.id+'-call',name:'workflow',arguments:text.slice(10)}};yield {type:'finish',reason:{kind:'tool-calls'}};return;}
 yield {type:'block-end',index:0,block:{type:'text',text:'Started'}};yield {type:'finish',reason:{kind:'stop'}};
});}
`,
    );
    await prepareProfile(home, [
      {
        insert: [
          { id: "workflow-life-fixture", name: join(home, "fixture.mjs") },
        ],
      },
    ]);
    const binding = {
      sessionId: "workflow-life",
      agentId: "a",
      revision: "1",
      ownerId: "owner",
      cwd: home,
    };
    const init = async (bindings: unknown[]) => {
      client = new RuntimeClient({
        home,
        cwd: home,
        env: { NANO_OWNER_CONFIG_ROOT: join(home, "owner") },
        onLog: (t) => (logs += t),
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
          },
        ],
        bindings,
      });
    };
    const records = () =>
      client!.rpc.request("workflow.read", {
        sessionId: binding.sessionId,
      }) as Promise<any[]>;
    const find = async (name: string) =>
      (await records()).find((r) => r.meta.name === name);
    const launch = async (name: string, script: string) => {
      await client!.rpc.request("session.submit", {
        sessionId: binding.sessionId,
        inputId: name,
        mode: "followup",
        content: [
          {
            type: "text",
            text:
              "WF_LAUNCH:" +
              JSON.stringify({ meta: { name, description: name }, script }),
          },
        ],
        source: {
          kind: "human",
          actorId: "owner",
          channel: "test",
          messageId: name,
        },
      });
      await until(async () => (await find(name))?.id).toBeTruthy();
      return (await find(name)).id as string;
    };
    const control = (runId: string, action: string, ordinal?: number) =>
      client!.rpc.request("workflow.control", {
        sessionId: binding.sessionId,
        runId,
        action,
        ordinal,
      });
    await init([]);
    await client!.rpc.request("session.ensure", binding);
    const first = await launch(
      "restart",
      `const a=await agent('CHILD:BLOCK');return [a,await agent('CHILD:NEXT')];`,
    );
    await until(async () => (await find("restart")).calls[0]?.state).toBe(
      "running",
    );
    await control(first, "pause");
    await control(first, "restart_child", 1);
    expect(
      (await readFile(join(home, "starts"), "utf8")).trim().split("\n"),
    ).toHaveLength(1);
    expect(
      (await readFile(join(home, "ends"), "utf8")).trim().split("\n"),
    ).toHaveLength(1);
    await control(first, "resume");
    await until(
      async () => (await find("restart")).calls[0].attempts.length,
    ).toBe(2);
    await writeFile(join(home, "release"), "yes");
    await until(async () => (await find("restart")).state).toBe("completed");
    expect((await find("restart")).result.value).toEqual([
      "CHILD:BLOCK",
      "CHILD:NEXT",
    ]);
    await rm(join(home, "release"));
    const stopped = await launch(
      "stop",
      `return await parallel(Array.from({length:10},()=>()=>agent('CHILD:BLOCK')));`,
    );
    await until(
      async () =>
        (await find("stop")).calls.filter((c: any) => c.state === "running")
          .length,
    ).toBe(8);
    await control(stopped, "pause");
    await control(stopped, "stop");
    expect((await find("stop")).state).toBe("cancelled");
    const nestedFile = join(home, "nested.js");
    await writeFile(
      nestedFile,
      '// nano-workflow: {"name":"nested","description":"nested"}\nreturn await agent("CHILD:"+args.value);',
    );
    await launch(
      "nested",
      `return await workflow(${JSON.stringify(nestedFile)},{value:'NESTED'});`,
    );
    await until(async () => (await find("nested")).state).toBe("completed");
    expect((await find("nested")).result.value).toBe("CHILD:NESTED");
    await writeFile(
      nestedFile,
      '// nano-workflow: {"name":"nested","description":"nested"}\nreturn await workflow(' +
        JSON.stringify(nestedFile) +
        ");",
    );
    await launch(
      "too-deep",
      `return await workflow(${JSON.stringify(nestedFile)});`,
    );
    await until(async () => (await find("too-deep")).state).toBe("error");
    expect((await find("too-deep")).result.error).toContain("one level");
    const interrupted = await launch(
      "cold",
      `await agent('CHILD:FAST');return await agent('CHILD:BLOCK');`,
    );
    await until(async () => (await find("cold")).calls[1]?.state).toBe(
      "running",
    );
    const before = (await readFile(join(home, "starts"), "utf8"))
      .trim()
      .split("\n").length;
    client!.process.kill("SIGKILL");
    await client!.exited;
    client = undefined;
    await init([binding]);
    expect((await find("cold")).state).toBe("interrupted");
    expect(
      (await readFile(join(home, "starts"), "utf8")).trim().split("\n"),
    ).toHaveLength(before);
    await writeFile(join(home, "release"), "yes");
    const resumed = (await control(interrupted, "resume")) as { runId: string };
    await until(
      async () => (await records()).find((r) => r.id === resumed.runId)?.state,
    ).toBe("completed");
    const after = (await records()).find((r) => r.id === resumed.runId)!;
    expect(after.calls[0].replayed).toBe(true);
    expect(after.calls[1].replayed).not.toBe(true);
    expect(
      (await readFile(join(home, "starts"), "utf8")).trim().split("\n"),
    ).toHaveLength(before + 1);
    await client!.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(String(error) + "\n" + logs, { cause: error });
  } finally {
    if (client) {
      client.process.kill("SIGKILL");
      await client.exited;
    }
    await rm(home, { recursive: true, force: true });
  }
}, 40000);
