import { mkdtemp, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it.each([false, true])('assembles the role agreement and protects formal memory (PA=%s)', async personal => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'nano-document-runtime-')); let client: InstanceType<typeof RuntimeClient> | undefined; let logs = '';
  const workspace = await realpath(home);
  const rolePath = join(workspace, '.nanoassistant/ROLE.md');
  const entry = join(home, '.nanoassistant/memory/MEMORY.md');
  const page = join(home, '.nanoassistant/memory/knowledge/preferences.md');
  const alias = join(home, 'memory-alias');
  const calls = [['read', { file_path: page }], ['write', { file_path: page, content: 'Forbidden replacement' }], ['edit', { file_path: join(alias, 'knowledge/preferences.md'), old_string: 'Public', new_string: 'Private' }], ['memory_maintenance', { action: 'checkpoint', generation: 0, request_ref: 'learn' }]];
  const {Context}=await import('@deepseek-ai/cordis');
  const {LocalFileSystem}=await import('@deepseek-ai/dsh-fs-local');
  const {MemoryDocuments}=await import('../src/knowledge/memory-documents.js');
  const seed=await MemoryDocuments.open(home,'expert',new LocalFileSystem(new Context(),{cwd:home,diffBasisMaxBytes:10485760}));
  await seed.apply({operationId:'unrelated',path:'knowledge/unrelated.md',beforeHash:null,content:'An unrelated already verified topic.'});
  await seed.apply({operationId:'preferences',path:'knowledge/preferences.md',beforeHash:null,content:'Public updates only.'});
  await symlink(join(home, '.nanoassistant/memory'), alias);
  await seed.checkpoint(await seed.versions(),0); await seed.close();
  await writeFile(join(home, 'fixture.mjs'), `import {appendFileSync} from 'node:fs'; export const name='memory-fixture'; export const inject=['llm']; export function apply(ctx) { const steps=new Map(); ctx.on('llm/stream',async function*(o) { appendFileSync(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify(o)+'\\n'); const last=o.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&m.source.actorId);const n=steps.get(last?.id)||0;steps.set(last?.id,n+1);const input=last?.content.find(b=>b.type==='text')?.text;const calls=input==='learn'?${JSON.stringify(calls)}:input==='check-unreadable-role'?[['read',{file_path:${JSON.stringify(rolePath)}}]]:[];if(n<calls.length){const [name,args]=calls[n];yield {type:'block-end',index:0,block:{type:'tool-call',id:last.id+'-'+n,name,arguments:JSON.stringify(args)}};yield {type:'finish',reason:{kind:'tool-calls'}};}else{yield {type:'block-end',index:0,block:{type:'text',text:'done'}};yield {type:'finish',reason:{kind:'stop'}};} }); }`);
  try {
    await prepareProfile(home, [{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'test'}]}}}}, {insert:[{id:'memory-fixture',name:join(home,'fixture.mjs')}]}]);
    client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    registerNoopTaskHosts(client);
    client.rpc.handle('knowledge.role.workspace', () => ({workspace}));
    const binding={sessionId:'memory-root',agentId:'a',ownerId:'owner',cwd:home,revision:'1'};
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',workspace:home,revision:'1',provider:'fixture',model:'test',
      ...(personal?{mode:'global',personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1}}:{}),
      features:{dreaming:false,memory_curation:false,skill_creation:false},toolAllowlist:['read','write','edit','memory','memory_maintenance']}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
    const submit = async (id: string, actorId = 'owner', roleAccountId?: string) => {
      await client!.rpc.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',content:[{type:'text',text:id}],source:{kind:'human',actorId,roleAccountId,channel:roleAccountId?'feishu':'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:binding.sessionId,inputId:id}) as {terminal?:unknown}).terminal,{timeout:8000}).toBeTruthy();
    };
    await submit('learn');
    const observed=await client.rpc.request('session.observe',{sessionId:binding.sessionId}) as {events:any[]};
    expect(observed.events.find(event => event.type === 'user/message' && event.data.id === 'learn')?.data.content.filter((block: {contextItemId?: string}) => !block.contextItemId))
      .toEqual([{type:'text',text:'learn'}]);
    for (const id of ['learn-1', 'learn-2', 'learn-3']) {
      expect(observed.events.find(e=>e.type==='tool/result'&&e.data.message.toolCallId===id)?.data.message.isError).toBe(true);
    }
    expect(await readFile(page,'utf8')).toBe('Public updates only.');
    expect(await readFile(rolePath,'utf8')).toContain('ask the user');
    const role = await client.rpc.request('configuration.role',{agentId:'a',workspace}) as {content:string;version:string};
    expect(role.content).toBe('');
    expect(await client.rpc.request('configuration.role',{agentId:'a',workspace,update:{content:'Coordinate delivery. Use {{customer_name}} in templates.',version:role.version}}))
      .toMatchObject({content:'Coordinate delivery. Use {{customer_name}} in templates.'});
    await writeFile(page,'Never interrupt, including urgent incidents.');
    await writeFile(entry,'# Expert memory\n[Preferences](knowledge/preferences.md)');
    await submit('use-new-memory', 'collaborator');
    const requests=(await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
    const confirmer = personal ? 'owner' : 'bound administrator';
    expect(JSON.stringify(requests[0].messages)).toContain(`Contact your ${confirmer} immediately`);
    expect(JSON.stringify(requests[0].messages)).toContain('You must ask every time you speak with them');
    expect(JSON.stringify(requests[0].messages)).not.toContain('Host-verified role agreement sender');
    const latest=requests.at(-1);
    const savedAgreement = latest.messages.flatMap((message: {content?: Array<{text?: string}>}) => message.content ?? [])
      .findLast((block: {text?: string}) => block.text?.includes('<role_content>'))?.text;
    expect(savedAgreement).toContain(`Contents of ${rolePath} — your confirmed role agreement:\n<role_content>\nCoordinate delivery. Use {{customer_name}} in templates.\n</role_content>`);
    expect(savedAgreement).toContain(personal ? 'how your owner wants you to help over time' : 'what you need to deliver');
    expect(savedAgreement).toContain(`Before establishing ROLE.md or discussing changes requested by your ${confirmer} ("owner") or proposed by you, load and follow the nano-role-agreement skill.`);
    expect(savedAgreement).not.toContain('Verify their identity using');
    expect(savedAgreement).not.toContain('Save only after sending them the exact Markdown');
    expect(savedAgreement).not.toContain('You must ask every time');
    expect(savedAgreement).not.toContain('read the saved file again');
    expect(JSON.stringify(latest.messages)).not.toContain('Host-verified role agreement sender');
    const control = latest.tools.find((tool:any)=>tool.name==='memory_maintenance');
    expect(control.parameters.properties.action.enum).toEqual(['status', 'run']);
    expect(control.parameters.properties).not.toHaveProperty('paths');
    expect(control.parameters.properties).not.toHaveProperty('sources');
    expect(JSON.stringify(control)).not.toContain('checkpoint');
    expect(JSON.stringify(control)).toContain('importLegacy');
    expect(latest.tools.map((tool:any)=>tool.name)).not.toContain('memory');
    expect(JSON.stringify(latest.messages)).not.toContain('entry_basis_stale');
    expect(JSON.stringify(latest.messages)).toContain('# Expert memory');
    expect(JSON.stringify(latest.messages)).not.toContain('Source generation:');
    expect(JSON.stringify(latest.messages)).not.toContain('fs-observation-policy');
    expect(JSON.stringify(latest.messages)).toContain('knowledge/preferences.md');
    expect(JSON.stringify(latest.messages)).toContain('verified errors or missing steps');
    await submit('external-owner', 'feishu-open-id', 'owner');
    const external = JSON.parse((await readFile(join(home,'requests.jsonl'),'utf8')).trim().split('\n').at(-1)!);
    const externalInput = external.messages.find((message: {id:string}) => message.id === 'external-owner');
    expect(externalInput.source.actorId).toBe('feishu-open-id');
    expect(externalInput.source.roleAccountId).toBe('owner');
    expect(external.messages.some((message: {source?: {channel?: string}}) => message.source?.channel === 'role-agreement-source')).toBe(false);
    const currentContext = async (fragment: string) => {
      const request = JSON.parse((await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').at(-1)!);
      return request.messages.flatMap((message: {content?: Array<{text?: string}>}) => message.content ?? [])
        .findLast((block: {text?: string}) => block.text?.includes(fragment))?.text;
    };
    const oversized = 'OVERSIZED_ROLE_BODY ' + '💡'.repeat(1000);
    await writeFile(rolePath, oversized);
    await submit('check-oversized-role', 'collaborator');
    const tooLong = await currentContext('Role agreement file:');
    expect(tooLong).toContain('exceeds the 2000 UTF-16 code unit limit');
    expect(tooLong).toContain('Draft a shorter version that preserves the original meaning and send it privately');
    expect(tooLong).toContain('Save only after they explicitly confirm the exact text');
    expect(tooLong).toContain('read the saved file again');
    expect(tooLong).toContain('Read the complete original first');
    expect(tooLong).toContain('send_message to "user:owner"');
    expect(tooLong).not.toContain('OVERSIZED_ROLE_BODY');
    expect(tooLong).not.toContain('Role agreement is unset');
    expect(await readFile(rolePath, 'utf8')).toBe(oversized);

    await rm(rolePath);
    const unrelated = join(home, 'unrelated-role-target.md');
    await writeFile(unrelated, 'UNRELATED_ROLE_LINK_TARGET');
    await symlink(unrelated, rolePath);
    await submit('check-unreadable-role');
    const unavailable = await currentContext('Role agreement file:');
    expect(unavailable).toContain('could not read the saved role file');
    expect(unavailable).toContain('restore a readable regular file');
    expect(unavailable).not.toContain('Draft a shorter version');
    expect(unavailable).toContain('Check it with the ordinary read tool first');
    expect(unavailable).toContain('send_message to "user:owner"');
    expect(unavailable).not.toContain('Role agreement is unset');
    const checked = await client.rpc.request('session.observe', {sessionId: binding.sessionId}) as {events: any[]};
    const diagnostic = checked.events.find(event => event.type === 'tool/result' && event.data.message.toolCallId === 'check-unreadable-role-0')?.data.message;
    expect(diagnostic).toMatchObject({isError: true});
    expect(JSON.stringify(diagnostic.content)).toContain('The role path is not a regular file in the assigned workspace.');
    expect(JSON.stringify(diagnostic.content)).not.toContain('UNRELATED_ROLE_LINK_TARGET');
    const beginning = '# Key memory\n\nUse {{customer_name}} in templates.\nStill the first paragraph.\n\n';
    const firstItem = `- ${'💡'.repeat(3500)}\n  Continuation of the first item.\n  - Nested item.`;
    const omitted = '\n- OMITTED_ITEM\n  ';
    const prefix = beginning + firstItem + omitted;
    const oversizedEntry = prefix + 'x'.repeat(9461 - prefix.length);
    await writeFile(entry, oversizedEntry);
    expect(await client.rpc.request('session.command', {sessionId:binding.sessionId,id:'compact-before-preview',action:'compact'})).toMatchObject({success:true});
    await submit('preview-oversized-memory');
    const preview = await currentContext('Memory directory:');
    expect(preview).toContain(`<memory_content>\n${beginning}${firstItem}\n</memory_content>`);
    expect(preview).toContain('Later content is omitted');
    expect(preview).toContain(join(workspace, '.nanoassistant/memory/MEMORY.md'));
    expect(preview).not.toContain('OMITTED_ITEM');
    expect(await readFile(entry, 'utf8')).toBe(oversizedEntry);

    const exactLimit = '💡'.repeat(4000);
    await writeFile(entry, exactLimit);
    expect(await client.rpc.request('session.command', {sessionId:binding.sessionId,id:'compact-before-limit',action:'compact'})).toMatchObject({success:true});
    await submit('load-at-memory-limit');
    const fullMemory = await currentContext('Memory directory:');
    expect(fullMemory).toContain(`<memory_content>\n${exactLimit}\n</memory_content>`);
    expect(fullMemory).not.toContain('Later content is omitted');
    expect((await client.rpc.request('knowledge.facts',{}) as {reviews:unknown[]}).reviews).toEqual([]);
    await client.shutdown();client=undefined;
  } catch(error) { throw new Error(`${String(error)}\n${logs}`,{cause:error}); }
  finally { if(client){client.process.kill('SIGKILL');await client.exited;} await rm(home,{recursive:true,force:true}); }
},20000);
