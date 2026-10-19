import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { reviewPersonal } from '../lib/personal-security.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('uses owner evidence for ordinary permissions and leaves PA delivery review to its mandatory product boundary',async()=>{
 const home=await mkdtemp(join(tmpdir(),'pa-owner-approval-'));let client:RuntimeClient|undefined;
 try {
  await writeFile(join(home,'fixture.mjs'),`import{writeFile}from'node:fs/promises';
export const name='pa-owner-approval';export const inject=['tools','llm'];export function apply(ctx){
ctx.tools.register({name:'owner_action',description:'Perform an owner action',parameters:{type:'object',properties:{text:{type:'string'}},required:['text']},output:{schema:{type:'object'},render:(_a,r)=>[{type:'text',text:JSON.stringify(r)}]},execute:args=>({executed:args.text})});
ctx.on('tools/pre-execute',(exec,next)=>exec.name==='send_message'&&exec.arguments.target==='blocked'?{kind:'deny',reason:'Explicit restriction'}:next());
ctx.on('llm/stream',async function*(o){const prompt=o.messages[0].content[0].text;const allow=prompt.includes('SERVER_OWNER_CHOICE')&&!prompt.includes('FORBIDDEN_DISCLOSURE');yield{type:'block-end',index:0,block:{type:'text',text:allow?'<block>no</block>':'<block>yes</block><reason>Not authorized</reason>'}};yield{type:'finish',reason:{kind:'stop'}};});
ctx.on('agent/created',({agent})=>{if(agent.id!=='root')return;setTimeout(async()=>{const results=[];for(const text of ['Chosen reservation','FORBIDDEN_DISCLOSURE'])results.push(await ctx.tools.execute({name:'owner_action',callId:'action-'+results.length,arguments:{text},agent,signal:new AbortController().signal}));for(const target of ['peer','blocked'])results.push(await ctx.tools.execute({name:'send_message',callId:'send-'+results.length,arguments:{target,text:'Chosen reservation'},agent,signal:new AbortController().signal}));await writeFile(process.env.DSH_HOME+'/results.json',JSON.stringify(results));},0);});}`);
  await prepareProfile(home,[{insert:[{id:'pa-owner-approval',name:join(home,'fixture.mjs')}]}]);
  client=new RuntimeClient({home,cwd:home});
  const sent:string[]=[];let authorityReads=0;
  client.rpc.handle('product.call',value=>{const call=value as any;
   if(call.method==='send_message.context')return {target:'peer',sender:{type:'agent',agent_id:'pa'},recipient:{kind:'user'},channel:'web'};
   if(call.method==='pa.authorization'){authorityReads++;return {owner_messages:[{id:'owner-request',sender_id:'owner',content:'Book the selected reservation'},{id:'choice',sender_id:'owner',interaction_reply:{source_message_id:'proposal',submission:{choice:'SERVER_OWNER_CHOICE'}}}],published_proposals:[{id:'proposal',content:'Choose a reservation'}]};}
   if(call.method==='send_message'){sent.push(call.args.text);return {status:'sent',message_id:'actual'};}
   throw Error('Unexpected product call '+call.method);
  });
  const config={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'deepseek-official',model:'deepseek-flash',personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1},approval:{...approvalDefaults,globalRoot:home}};
  await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
  await client.rpc.request('session.ensure',{sessionId:'root',agentId:'pa',ownerId:'owner',revision:'1',cwd:home});
  await expect.poll(async()=>readFile(join(home,'results.json'),'utf8').catch(()=>''),{timeout:10000}).not.toBe('');
  const results=JSON.parse(await readFile(join(home,'results.json'),'utf8'));
  expect(sent).toEqual(['Chosen reservation']);expect(results[0].isError).not.toBe(true);expect(results[3].isError).toBe(true);expect(JSON.stringify(results[3])).toContain('Explicit restriction');expect(results[1].isError).toBe(true);expect(JSON.stringify(results[1])).toContain('Not authorized');expect(authorityReads).toBeGreaterThan(0);
 }finally{if(client)await client.shutdown();await rm(home,{recursive:true,force:true});}
},20000);

it('keeps the ordinary Global capability catalog and executes owner extensions and source controls',async()=>{
  const home=await mkdtemp(join(tmpdir(),'pa-global-capabilities-'));
  const catalogs: string[][]=[];
  try {
    for (const personal of [false,true]) {
      const root=join(home,personal?'personal':'global');await mkdir(root);
      const skills=join(root,'skills');await mkdir(join(skills,'owner-skill'),{recursive:true});
      await writeFile(join(skills,'owner-skill','SKILL.md'),'---\nname: owner-skill\ndescription: Owner skill\n---\nUse ordinary tools.');
      await writeFile(join(root,'extension.mjs'),`export const name='owner-extension';export const inject=['tools'];export function apply(ctx){ctx.tools.register({name:'owner_tool',description:'Owner installed tool',parameters:{type:'object',properties:{}},output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},execute:()=>({value:'OWNER_EXTENSION_EXECUTED'})});}`);
      await writeFile(join(root,'plugins.json'),JSON.stringify([{module:'./extension.mjs'}]));
      await writeFile(join(root,'fixture.mjs'),`import{writeFile}from'node:fs/promises';
export const name='capability-fixture';export const inject=['tools'];export function apply(ctx){ctx.on('agent/created',({agent})=>{if(agent.id!=='root')return;setTimeout(async()=>{const results=[];const tools=[['owner_tool',{}],['bash',{command:'printf SHELL_EXECUTED',description:'Verify ordinary shell access'}],['memory',{action:'add',target:'memory',content:'Private note survives source changes'}],...(${personal}?[['personal_sources',{action:'exclude',conversation_id:'source',source_message_id:'owner-request',expected_revision:1}],['conversations',{action:'search',target:'source',keyword:'meeting',participant_id:'owner',before:'2026-10-20',after:'2026-10-01'}],['send_message',{target:'owner',text:'Draft',interactive:{format:'openui',catalog_version:'nano-1',source:'root = TextContent("Draft")'},reply_draft:{target_conversation_id:'source',source_message_id:'source-message',field_name:'reply'}}]]:[])];for(const[name,args]of tools)results.push({name,result:await ctx.tools.execute({name,callId:'call-'+results.length,arguments:args,agent,signal:new AbortController().signal})});await writeFile(process.env.DSH_HOME+'/results.json',JSON.stringify(results));},0);});}`);
      await prepareProfile(root,[{insert:[{id:'capability-fixture',name:join(root,'fixture.mjs')}]}]);
      let logs='';const client=new RuntimeClient({home:root,cwd:root,onLog:text=>{logs+=text;}});
      const calls:any[]=[];
      client.rpc.handle('product.call',value=>{const call=value as any;calls.push(call);if(call.method==='personal_sources')return {revision:2,excluded_conversation_ids:['source']};if(call.method==='conversations')return {messages:[]};if(call.method==='send_message')return {status:'sent',message_id:'draft-message'};throw new Error('Unexpected product call '+call.method);});
      const config={agentId:'agent',revision:'1',workspace:root,mode:'global',provider:'deepseek-official',model:'deepseek-flash',
        extensions:{workspace:join(root,'plugins.json')},skillRoots:[{path:skills,source:'owner'}],features:{skill_creation:true,memory_curation:true},
        ...(personal?{personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1}}:{}),approval:{...approvalDefaults,dangerouslySkipPermissions:true,globalRoot:root}};
      try {
        await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
        await client.rpc.request('session.ensure',{sessionId:'root',agentId:'agent',ownerId:'owner',revision:'1',cwd:root});
        await expect.poll(async()=>readFile(join(root,'results.json'),'utf8').catch(()=>''),{timeout:10000}).not.toBe('');
        const results=JSON.parse(await readFile(join(root,'results.json'),'utf8'));
        expect(results.every((entry:any)=>!entry.result.isError),JSON.stringify(results)).toBe(true);
        expect(JSON.stringify(results)).toContain('OWNER_EXTENSION_EXECUTED');expect(JSON.stringify(results)).toContain('SHELL_EXECUTED');
        const catalog=await client.rpc.request('configuration.catalog',{agentId:'agent',cwd:root}) as any;
        const names=catalog.tools.map((tool:any)=>tool.name).sort();catalogs.push(names.filter((name:string)=>name!=='personal_sources'));
        for(const name of ['bash','read','write','web_search','web_fetch','skill_manage','plugin_manager','owner_tool','task_graph'])expect(names).toContain(name);
        expect(catalog.skills.map((skill:any)=>skill.name)).toContain('owner-skill');
        if(personal){
          expect(names).toContain('personal_sources');
          expect(calls.find(call=>call.method==='personal_sources').args).toEqual({action:'exclude',conversation_id:'source',source_message_id:'owner-request',expected_revision:1});
          expect(calls.find(call=>call.method==='send_message').args.reply_draft).toEqual({target_conversation_id:'source',source_message_id:'source-message',field_name:'reply'});
          expect(await readFile(join(root,'.nanoassistant','memory','MEMORY.md'),'utf8')).toContain('Private note survives source changes');
          expect(await client.rpc.request('pa.evidence',{agentId:'agent',sessionId:'root'})).toHaveProperty('contexts');
        }
      }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}
      finally {await client.shutdown();}
    }
    expect(catalogs[1]).toEqual(catalogs[0]);
  }finally{await rm(home,{recursive:true,force:true});}
},30000);

// DeepSeek declares high/max, while other reviewers support low or no reasoning.
it.each([['high','max'],['low','high'],[]])('uses a supported independent-review effort: %j',async (...efforts:string[])=>{
  let request:any;
  const ctx={llm:{resolveModelInfo:async()=>({reasoning:efforts.length?{efforts:efforts.map(id=>({id})),defaultEffort:efforts[0]}:undefined}),stream:async function*(options:any){request=options;yield{type:'block-end',index:0,block:{type:'text',text:'{"decision":"allow","reason":"public lookup"}'}};yield{type:'finish',reason:{kind:'stop'}};}}};
  const result=await reviewPersonal(ctx as any,{personal:{bindingId:'b'},provider:'p',model:'m'} as any,'action',{query:'public'});
  expect(result.decision).toBe('allow');expect(request.reasoningEffort).toBe(efforts.includes('low')?'low':efforts[0]);
  expect(request.tools).toBeUndefined();expect(request.sessionId).toBeUndefined();
});
