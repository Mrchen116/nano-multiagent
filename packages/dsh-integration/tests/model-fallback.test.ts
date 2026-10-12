import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { expect, it } from 'vitest';
import { approvalDefaults } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
const require = createRequire(import.meta.url);

it('continues one admitted input on the backup and restores successful sticky selection after restart', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-fallback-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  const config = {
    agentId: 'a',
    revision: '1',
    provider: 'fixture',
    model: 'primary',
    reasoningEffort: 'high',
    modelFallbacks: [{ provider: 'fixture', model: 'backup', reasoningEffort: 'low' }],
    toolAllowlist: [],
    features: {},
  };
  const binding = { sessionId: 'fallback-session', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  await writeFile(
    join(home, 'fixture.mjs'),
    `import {LlmError} from ${JSON.stringify(require.resolve('@deepseek-ai/dsh-llm'))};import {appendFile}from'node:fs/promises';export const name='fallback-fixture';export const inject=['llm'];export function apply(ctx){ctx.on('llm/stream',async function*(o){await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({model:o.model,effort:o.reasoningEffort,messages:o.messages,system:o.system})+'\\n');if(o.model==='primary')throw new LlmError('primary unavailable','AUTH',{status:401});yield{type:'block-end',index:0,block:{type:'text',text:'Backup completed the original request.'}};yield{type:'finish',reason:{kind:'stop'},usage:{inputTokens:10,outputTokens:5}};});}`,
  );
  try {
    await prepareProfile(home, [
      {
        id: 'llm-pi-ai',
        config: {
          providers: {
            fixture: {
              api: 'openai-completions',
              baseURL: 'http://127.0.0.1:9',
              apiKeyEnv: 'NANO_TEST_KEY',
              models: ['primary', 'backup'].map((id) => ({
                id,
                contextWindow: 100000,
                reasoningEfforts: { low: 'low', high: 'high' },
              })),
            },
          },
        },
      },
      { insert: [{ id: 'fallback-fixture', name: join(home, 'fixture.mjs') }] },
    ]);
    const start = async () => {
      client = new RuntimeClient({
        home,
        cwd: home,
        env: { NANO_TEST_KEY: 'fixture' },
        onLog: (text) => {
          logs += text;
        },
      });
      client.rpc.handle('model.check', () => ({ published: false }));
      await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
      await client.rpc.request('session.ensure', binding);
    };
    const submit = async (id: string) => {
      await client!.rpc.request('session.submit', {
        sessionId: binding.sessionId,
        inputId: id,
        mode: 'followup',
        content: [{ type: 'text', text: 'Complete the original task.' }],
        source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id },
      });
      let result: any;
      await expect
        .poll(async () => {
          result = await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: id });
          return result.terminal;
        })
        .toBeTruthy();
      return result;
    };
    await start();
    expect((await submit('one')).terminal).toMatchObject({ kind: 'completed' });
    const events = ((await client!.rpc.request('session.observe', { sessionId: binding.sessionId })) as any).events;
    expect(events.filter((event: any) => event.type === 'user/message' && event.data.id === 'one')).toHaveLength(1);
    expect(
      events.filter((event: any) => event.type === 'user/message' && event.data.source.kind === 'nano-fallback'),
    ).toHaveLength(1);
    await client!.shutdown();
    client = undefined;
    await start();
    expect((await submit('two')).terminal).toMatchObject({ kind: 'completed' });
    config.revision = '2';
    await client!.rpc.request('configuration.apply', { ...config, systemPrompt: 'Updated prompt, same routes' });
    expect((await submit('three')).terminal).toMatchObject({ kind: 'completed' });
    config.revision = '3';
    config.modelFallbacks.push({ provider: 'fixture', model: 'primary', reasoningEffort: 'high' });
    await client!.rpc.request('configuration.apply', config);
    expect((await submit('four')).terminal).toMatchObject({ kind: 'completed' });
    const requests = (await readFile(join(home, 'requests.jsonl'), 'utf8'))
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line));
    expect(requests.map((r) => r.model)).toEqual(['primary', 'backup', 'backup', 'backup', 'primary', 'backup']);
    expect(requests[1].effort).toBe('low');
    await client!.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    if (client) {
      client.process.kill('SIGKILL');
      await client.exited;
    }
    await rm(home, { recursive: true, force: true });
  }
}, 20000);

it.each([
  'prepare',
  'finish',
  'exhausted',
  'context',
  'published',
  'tool',
  'cancel',
  'new-input',
  'restart',
  'pre-step',
] as const)(
  'honors native fallback boundary: %s',
  async (scenario) => {
    const home = await mkdtemp(join(tmpdir(), 'nano-fallback-boundary-'));
    let client: RuntimeClient | undefined;
    let logs = '';
    const config = {
      agentId: 'a',
      revision: '1',
      provider: 'fixture-boundary',
      model: 'primary',
      reasoningEffort: 'high',
      modelFallbacks: [{ provider: 'fixture-boundary', model: 'backup' }],
      toolAllowlist: scenario === 'tool' ? ['fixture_read'] : [],
      features: {},
      approval: { ...approvalDefaults, globalRoot: home, dangerouslySkipPermissions: true },
    };
    const binding = { sessionId: 'boundary', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
    await writeFile(
      join(home, 'fixture.mjs'),
      `import {LlmError,LlmAdapter,resolveRetryPolicy}from ${JSON.stringify(require.resolve('@deepseek-ai/dsh-llm'))};import{appendFile,access}from'node:fs/promises';
export const name='boundary-fixture';export const inject=['llm','tools'];export function apply(ctx){let step=0;const scenario=${JSON.stringify(scenario)};
if(scenario==='pre-step')ctx.on('agent/pre-step',async(p,next)=>{if(p.turn===2){await appendFile(process.env.DSH_HOME+'/gate-entered','yes');while(!await access(process.env.DSH_HOME+'/release').then(()=>true,()=>false)){p.signal.throwIfAborted();await new Promise(r=>setTimeout(r,5));}}return next();});
ctx.tools.register({name:'fixture_read',description:'Read fixture',parameters:{type:'object',properties:{}},output:{schema:{},render:()=>[{type:'text',text:'read'}]},execute:async()=>{await appendFile(process.env.DSH_HOME+'/effects','read');return{};}});
class Fixture extends LlmAdapter{
 providerRetryPolicy(){return resolveRetryPolicy({mode:'normal',maxRetries:0},'fixture');}
 async resolveModel(provider,id){return{provider,id,name:id,context:{contextWindow:id==='primary'?100000:70000},defaultMaxTokens:1000,reasoning:{efforts:[{id:'low',name:'Low'},{id:'high',name:'High'}],defaultEffort:id==='primary'?'high':'low'}};}
 async prepareCall(provider,model,signal){if(scenario==='prepare'&&model==='primary')throw new LlmError('preparation auth failed','AUTH',{status:401});return super.prepareCall(provider,model,signal);}
 async *stream(o){await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({model:o.model,effort:o.reasoningEffort,messages:o.messages})+'\\n');
 if(o.model==='primary'&&(!['new-input','pre-step'].includes(scenario)||o.messages.findLast(m=>m.role==='user'&&m.source.kind==='nano-human')?.id==='one')){
  if(scenario==='tool'&&step++===0){yield{type:'block-end',index:0,block:{type:'tool-call',id:'read-once',name:'fixture_read',arguments:'{}'}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
  if(scenario==='finish'){yield{type:'finish',reason:{kind:'error',failure:{code:'AUTH',message:'terminal auth failure',status:401}},usage:{inputTokens:7,outputTokens:0}};return;}
  throw new LlmError('candidate failed',scenario==='context'?'CONTEXT_WINDOW_EXCEEDED':'AUTH',{status:scenario==='context'?400:401});
 }
 if(scenario==='exhausted')throw new LlmError('backup failed','AUTH',{status:401});
 yield{type:'block-end',index:0,block:{type:'text',text:'Recovered.'}};yield{type:'finish',reason:{kind:'stop'},usage:{inputTokens:10,outputTokens:5}};
 }}ctx.llm.registerAdapter(['fixture-boundary'],new Fixture());}`,
    );
    try {
      await prepareProfile(home, [{ insert: [{ id: 'boundary-fixture', name: join(home, 'fixture.mjs') }] }]);
      client = new RuntimeClient({
        home,
        cwd: home,
        onLog: (text) => {
          logs += text;
        },
      });
      let checked = 0;
      let release: () => void = () => {};
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      client.rpc.handle('model.check', async () => {
        checked++;
        if (scenario === 'cancel' || scenario === 'new-input' || scenario === 'restart') await gate;
        return { published: scenario === 'published' };
      });
      await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
      await client.rpc.request('session.ensure', binding);
      const submit = (id: string) =>
        client!.rpc.request('session.submit', {
          sessionId: binding.sessionId,
          inputId: id,
          mode: 'followup',
          content: [{ type: 'text', text: 'Complete task ' + id }],
          source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id },
        });
      await submit('one');
      if (scenario === 'pre-step') {
        await expect.poll(() => readFile(join(home, 'gate-entered'), 'utf8').catch(() => undefined)).toBe('yes');
        await submit('two');
        await writeFile(join(home, 'release'), 'yes');
      }
      if (scenario === 'restart') {
        await expect.poll(() => checked).toBe(1);
        client.process.kill('SIGKILL');
        await client.exited;
        release();
        client = new RuntimeClient({
          home,
          cwd: home,
          onLog: (text) => {
            logs += text;
          },
        });
        client.rpc.handle('model.check', () => ({ published: false }));
        await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
        await client.rpc.request('session.ensure', binding);
      }
      if (scenario === 'cancel' || scenario === 'new-input') {
        await expect.poll(() => checked).toBe(1);
        if (scenario === 'cancel') {
          const stopping = client.rpc.request('session.cancel', { sessionId: binding.sessionId });
          await expect
            .poll(
              async () =>
                ((await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: 'one' })) as any)
                  .terminal?.kind,
            )
            .toBe('cancelled');
          release();
          await stopping;
        } else {
          await submit('two');
          release();
        }
      }
      let result: any;
      await expect
        .poll(async () => {
          result = await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: 'one' });
          return result.terminal;
        })
        .toBeTruthy();
      const success = ['prepare', 'finish', 'restart'].includes(scenario);
      expect(result.terminal.kind, JSON.stringify(result)).toBe(
        success
          ? 'completed'
          : scenario === 'cancel' || scenario === 'new-input' || scenario === 'pre-step'
            ? 'cancelled'
            : 'error',
      );
      if (scenario === 'new-input' || scenario === 'pre-step')
        await expect
          .poll(
            async () =>
              ((await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: 'two' })) as any)
                .terminal?.kind,
          )
          .toBe('completed');
      const read = (await client.rpc.request('session.observe', { sessionId: binding.sessionId })) as any;
      const models = read.modelRuns.flatMap((run: any) => run.attempts.map((a: any) => a.route.model));
      expect(models.includes('backup')).toBe(success || scenario === 'exhausted' || scenario === 'pre-step');
      if (scenario === 'pre-step')
        expect((await readFile(join(home, 'requests.jsonl'), 'utf8')).includes('\"model\":\"backup\"')).toBe(false);
      if (scenario === 'prepare')
        expect(read.events.filter((e: any) => e.type === 'user/message' && e.data.id === 'one')).toHaveLength(1);
      if (success) {
        const headers = read.events.filter((e: any) => e.type === 'request/context');
        expect(headers.at(-1).data.contextWindow).toBe(70000);
        const requests = (await readFile(join(home, 'requests.jsonl'), 'utf8'))
          .trim()
          .split('\n')
          .map((line) => JSON.parse(line));
        expect(requests.at(-1).effort).toBe('low');
      }
      if (scenario === 'tool') expect(await readFile(join(home, 'effects'), 'utf8')).toBe('read');
      await client.shutdown();
      client = undefined;
    } catch (error) {
      if (client) {
        const state = (await client.rpc.request('session.observe', { sessionId: binding.sessionId })) as any;
        logs += JSON.stringify({
          status: state.status,
          runs: state.modelRuns,
          events: state.events.filter((e: any) =>
            ['turn/start', 'turn/end', 'agent/inbox/spliced', 'step/start', 'user/message'].includes(e.type),
          ),
        });
      }
      throw new Error(`${scenario}: ${String(error)}\n${logs}`, { cause: error });
    } finally {
      if (client) {
        client.process.kill('SIGKILL');
        await client.exited;
      }
      await rm(home, { recursive: true, force: true });
    }
  },
  20000,
);
