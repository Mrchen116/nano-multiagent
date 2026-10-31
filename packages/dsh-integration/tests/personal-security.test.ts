import { mkdtemp, mkdir, readFile, writeFile, rm, cp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { reviewPersonal } from '../lib/personal-security.js';
import { personalReviewAction } from '../src/personal-security.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it.each(['nano', 'codex'] as const)('keeps %s ordinary approval inside effective history while PA delivery retains its product boundary',async(rules)=>{
 const home=await mkdtemp(join(tmpdir(),'pa-owner-approval-'));let client:RuntimeClient|undefined;let logs='';
 try {
  await writeFile(join(home,'fixture.mjs'),`import{appendFile}from'node:fs/promises';
export const name='pa-owner-approval';export const inject=['tools','llm'];export function apply(ctx){
const steps=new Set();
ctx.tools.register({name:'owner_action',description:'Perform an owner action',parameters:{type:'object',properties:{text:{type:'string'}},required:['text']},output:{schema:{type:'object'},render:(_a,r)=>[{type:'text',text:JSON.stringify(r)}]},execute:args=>({executed:args.text})});
ctx.on('tools/pre-execute',(exec,next)=>['send_message','send_user_message'].includes(exec.name)&&exec.arguments.target==='blocked'?{kind:'deny',reason:'Explicit restriction'}:next());
ctx.on('llm/stream',async function*(o){
 if(o.model==='review'){
  const prompt=JSON.stringify(o.messages);await appendFile(process.env.DSH_HOME+'/review-input.jsonl',prompt+'\\n');
  const latest=o.messages.findLast(m=>m.role==='user');const input=latest.content.filter(c=>c.type==='text').map(c=>c.text).join('');const pending=input.includes('<planned_action>')?input.split('<planned_action>').at(-1):input.trim().split('\\n').filter(line=>line.startsWith('{')).at(-1);const allow=prompt.includes('CURRENT_OWNER_CHOICE')&&!pending.includes('FORBIDDEN_DISCLOSURE');
  yield{type:'block-end',index:0,block:{type:'text',text:${rules==='codex'?`JSON.stringify({outcome:allow?'allow':'deny',risk_level:allow?'low':'high',user_authorization:'high',rationale:'Not authorized'})`:`allow?'<block>no</block>':'<block>yes</block><reason>Not authorized</reason>'`}}};yield{type:'finish',reason:{kind:'stop'}};return;
 }
 await appendFile(process.env.DSH_HOME+'/main-input.jsonl',JSON.stringify(o)+'\\n');
 const human=o.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&'actorId'in m.source);
 if(!steps.has(human.id)){steps.add(human.id);const call=JSON.parse(human.content[0].text);yield{type:'block-end',index:0,block:{type:'tool-call',id:'call-'+human.id,name:call.name,arguments:JSON.stringify(call.args)}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
 yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
});}`);
  await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'main',contextWindow:100000},{id:'review',contextWindow:100000,reasoningEfforts:{low:'low'}}]}}}},{insert:[{id:'pa-owner-approval',name:join(home,'fixture.mjs')}]}]);
  client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
  registerNoopTaskHosts(client);
  const sent:string[]=[];let authorityReads=0;
  client.rpc.handle('product.call',value=>{const call=value as any;
   if(call.method==='send_message.context')return {target:'peer',sender:{type:'agent',agent_id:'pa'},recipient:{kind:'user'},channel:'web'};
   if(call.method==='pa.authorization'){authorityReads++;return {owner_messages:[{content:'DATABASE_HISTORY_NOT_IN_EFFECTIVE_CONTEXT'.repeat(50000)}]};}
   if(['send_message','send_user_message'].includes(call.method)){if(call.args.text==='OWNER_REPRESENTATION')expect(call.args.interactive).toEqual({source:'root = TextContent("Confirmed")',format:'openui',catalog_version:'nano-1'});sent.push(call.args.text);return {status:'sent',message_id:'actual'};}
   throw Error('Unexpected product call '+call.method);
  });
  const config={agentId:'pa',revision:'1',workspace:home,mode:'global',provider:'fixture',model:'main',personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1},approval:{...approvalDefaults,globalRoot:home,rules,alwaysAllowTools:['send_user_message'],reviewer:{provider:'fixture',model:'review'}}};
  await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
  await client.rpc.request('session.ensure',{sessionId:'root',agentId:'pa',ownerId:'owner',revision:'1',cwd:home});
  for(const [index,call] of [
   {name:'owner_action',args:{text:'CURRENT_OWNER_CHOICE chosen reservation'}},
   {name:'owner_action',args:{text:'FORBIDDEN_DISCLOSURE'}},
   {name:'send_message',args:{target:'peer',text:'CURRENT_OWNER_CHOICE chosen reservation'}},
   {name:'send_message',args:{target:'blocked',text:'Chosen reservation'}},
   {name:'send_user_message',args:{target:'peer',text:'OWNER_REPRESENTATION',interactive:{source:'root = TextContent("Confirmed")'}}},
   {name:'send_user_message',args:{target:'blocked',text:'Not sent'}},
   {name:'send_user_message',args:{target:'peer',text:'Invalid identity',send_as:'owner'}},
   {name:'send_message',args:{target:'peer',text:'Invalid protocol',interactive:{source:'root = TextContent("Legacy")',format:'openui',catalog_version:'nano-1'}}},
  ].entries()){
   const id=String(index);
   await client.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',content:[{type:'text',text:JSON.stringify(call)}],source:{kind:'human',actorId:'owner',channel:'test',messageId:id}});
   await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal,{timeout:10000}).toBeTruthy();
  }
  const observation=await client.rpc.request('session.observe',{sessionId:'root'}) as any;
  expect(observation.approvals.find((row:any)=>row.callId==='call-4')).toMatchObject({source:'product_disclosure_gate'});
  const results=observation.events.filter((event:any)=>event.type==='tool/result').map((event:any)=>event.data.message);
  expect(sent,JSON.stringify(results)).toEqual(['CURRENT_OWNER_CHOICE chosen reservation','OWNER_REPRESENTATION']);expect(results[4].isError).not.toBe(true);expect(results[5].isError).toBe(true);expect(results[6].isError).toBe(true);expect(results[7].isError).toBe(true);expect(results[0].isError).not.toBe(true);expect(results[3].isError).toBe(true);expect(JSON.stringify(results[3])).toContain('Explicit restriction');expect(results[1].isError).toBe(true);expect(JSON.stringify(results[1])).toContain('Not authorized');expect(authorityReads).toBe(0);
  const mainInput=await readFile(join(home,'main-input.jsonl'),'utf8');
  expect(mainInput).toContain('Only Dreaming');
  expect(mainInput.includes('Immediately correct affected current pages')).toBe(false);
  expect(mainInput.includes('checkpoint the current generation')).toBe(false);
  const prompt=await readFile(join(home,'review-input.jsonl'),'utf8');expect(prompt).toContain('CURRENT_OWNER_CHOICE');expect(prompt).not.toContain('DATABASE_HISTORY_NOT_IN_EFFECTIVE_CONTEXT');expect(prompt).not.toContain('nano_personal_authorization');
 }catch(error){throw new Error(`${error}\n${logs}`,{cause:error});}finally{if(client)await client.shutdown().catch(()=>{});await rm(home,{recursive:true,force:true});}
},20000);

it('keeps the ordinary Global capability catalog and executes owner extensions and source controls',async()=>{
  const home=await mkdtemp(join(tmpdir(),'pa-global-capabilities-'));
  const catalogs: string[][]=[];
  try {
    for (const personal of [false,true]) {
      const root=join(home,personal?'personal':'global');await mkdir(root);
      const skills=join(root,'skills');await mkdir(join(skills,'owner-skill'),{recursive:true});
      await cp(new URL('../../personal-assistant/assets/skills/nano-ongoing-work/',import.meta.url),join(skills,'nano-ongoing-work'),{recursive:true});
      await writeFile(join(skills,'owner-skill','SKILL.md'),'---\nname: owner-skill\ndescription: Owner skill\n---\nUse ordinary tools.');
      await writeFile(join(root,'extension.mjs'),`export const name='owner-extension';export const inject=['tools'];export function apply(ctx){ctx.tools.register({name:'owner_tool',description:'Owner installed tool',parameters:{type:'object',properties:{}},output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},execute:()=>({value:'OWNER_EXTENSION_EXECUTED'})});}`);
      await writeFile(join(root,'plugins.json'),JSON.stringify([{module:'./extension.mjs'}]));
      await writeFile(join(root,'fixture.mjs'),`import{writeFile}from'node:fs/promises';
export const name='capability-fixture';export const inject=['tools'];export function apply(ctx){ctx.on('agent/created',({agent})=>{if(agent.id!=='root')return;setTimeout(async()=>{const results=[];const tools=[['skill',{name:'nano-ongoing-work'}],['owner_tool',{}],['bash',{command:'printf SHELL_EXECUTED',description:'Verify ordinary shell access'}],['memory',{action:'add',target:'memory',content:'Private note survives source changes'}],...(${personal}?[['personal_sources',{action:'exclude',conversation_id:'source',source_message_id:'owner-request',expected_revision:1}],['conversations',{action:'search',target:'source',keyword:'meeting',participant_id:'owner',before:'2026-10-20',after:'2026-10-01'}],['send_message',{target:'owner',text:'Draft',interactive:{source:'root = TextContent("Draft")'}}]]:[])];for(const[name,args]of tools)results.push({name,result:await ctx.tools.execute({name,callId:'call-'+results.length,arguments:args,agent,signal:new AbortController().signal})});await writeFile(process.env.DSH_HOME+'/results.json',JSON.stringify(results));},0);});}`);
      await prepareProfile(root,[{insert:[{id:'capability-fixture',name:join(root,'fixture.mjs')}]}]);
      let logs='';const client=new RuntimeClient({home:root,cwd:root,onLog:text=>{logs+=text;}});
      registerNoopTaskHosts(client);
      const calls:any[]=[];
      client.rpc.handle('product.call',value=>{const call=value as any;calls.push(call);if(call.method==='personal_sources')return {revision:2,excluded_conversation_ids:['source']};if(call.method==='conversations')return {messages:[]};if(call.method==='send_message')return {status:'sent',message_id:'draft-message'};throw new Error('Unexpected product call '+call.method);});
      const config={agentId:'agent',knowledge:{memoryMode:'legacy'},revision:'1',workspace:root,mode:'global',provider:'deepseek-official',model:'deepseek-flash',
        systemPrompt:'OWNER_EDITABLE_GUIDANCE',extensions:{workspace:join(root,'plugins.json')},skillRoots:[{path:skills,source:'owner'}],features:{intelligent_ui:false,task_graph:false,skill_creation:true,memory_curation:true},
        ...(personal?{personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1}}:{}),approval:{...approvalDefaults,dangerouslySkipPermissions:true,globalRoot:root}};
      try {
        await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[]});
        await client.rpc.request('session.ensure',{sessionId:'root',agentId:'agent',ownerId:'owner',revision:'1',cwd:root});
        await expect.poll(async()=>readFile(join(root,'results.json'),'utf8').catch(()=>''),{timeout:10000}).not.toBe('');
        const results=JSON.parse(await readFile(join(root,'results.json'),'utf8'));
        expect(results.every((entry:any)=>!entry.result.isError),JSON.stringify(results)).toBe(true);
        expect(JSON.stringify(results)).toContain('OWNER_EXTENSION_EXECUTED');expect(JSON.stringify(results)).toContain('SHELL_EXECUTED');
        const catalog=await client.rpc.request('configuration.catalog',{agentId:'agent',cwd:root}) as any;
        const names=catalog.tools.map((tool:any)=>tool.name).sort();catalogs.push(names.filter((name:string)=>!['personal_sources','send_user_message'].includes(name)));
        for(const name of ['bash','read','write','web_search','web_fetch','skill_manage','plugin_manager','owner_tool','task_graph'])expect(names).toContain(name);
        expect(catalog.skills.map((skill:any)=>skill.name)).toEqual(expect.arrayContaining(['owner-skill','nano-ongoing-work']));
        expect(JSON.stringify(results.find((entry:any)=>entry.name==='skill'))).toContain('持续推进已交办的工作');
        const before=await client.rpc.request('session.capabilities',{sessionId:'root'}) as any;
        expect(JSON.stringify(before.prompt)).toContain('OWNER_EDITABLE_GUIDANCE');
        await client.rpc.request('configuration.apply',{...config,revision:'2',systemPrompt:'',skillSelection:{mode:'explicit_denylist',names:['nano-ongoing-work']}});
        const after=await client.rpc.request('session.capabilities',{sessionId:'root'}) as any;
        expect(JSON.stringify(after.prompt)).not.toContain('OWNER_EDITABLE_GUIDANCE');
        expect(after.skills.map((skill:any)=>skill.name)).not.toContain('nano-ongoing-work');
        expect(after.skills.map((skill:any)=>skill.name)).toContain('owner-skill');
        if(personal)expect(JSON.stringify(after.prompt)).toContain('nano-personal-agent');
        if(personal){
          expect(names).toContain('personal_sources');
          expect(calls.find(call=>call.method==='personal_sources').args).toEqual({action:'exclude',conversation_id:'source',source_message_id:'owner-request',expected_revision:1});
          expect(calls.find(call=>call.method==='send_message').args.interactive).toEqual({format:'openui',catalog_version:'nano-1',source:'root = TextContent("Draft")'});
          expect(names).toContain('send_user_message');
          const send = catalog.tools.find((tool:any)=>tool.name==='send_user_message');
          expect(Object.keys(send.parameters.properties)).toEqual(['target','text','interactive']);
          expect(Object.keys(send.parameters.properties.interactive.properties)).toEqual(['source','supersedes_message_id','source_mode']);
          expect(await readFile(join(root,'.nanoassistant','memory-legacy','MEMORY.md'),'utf8')).toContain('Private note survives source changes');
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
  const result=await reviewPersonal(ctx as any,{personal:{bindingId:'b'},provider:'p',model:'m'} as any,'input',{query:'public'});
  expect(result.decision).toBe('allow');expect(request.reasoningEffort).toBe(efforts.includes('low')?'low':efforts[0]);
  expect(request.tools).toBeUndefined();expect(request.sessionId).toBeUndefined();
});


it('projects the exact frozen disclosure and complete audience without backend guards or read-history bookkeeping',()=>{
 const text='<mention type="user" target_id="q"/> <mention type="user" target_id="e"/> 请汇报当前进展';
 const members=[['owner','Owner','user'],['p','P','agent'],['q','Q','agent'],['e','E','agent']].map(([id,name,type])=>({id:`actor-${id}`,user_id:id,display_name:name,type,is_stale:null}));
 const frozen:any={owner_user_id:'owner',agent_profile_version:'internal',owner_guard:'freshness',last_owner_message_id:'old-group-message',
  recipient:{conversation_id:'group',name:'Development',conversation_type:'group',channel:'web',members},recipient_ids:['owner','p','q','e'],
  policy:{revision:12,excluded_conversation_ids:[]},sources:[{conversation_id:'old-read-chat',allowed:true}],recipient_risks:[],external_destination:null,
  payload:{content:text,attachments:[],attachment_snapshots:[]}};
 const original=JSON.stringify(frozen);
 expect(personalReviewAction(frozen)).toEqual({tool:'send_message',representation:'self',arguments:{target:'group',text},audience:{name:'Development',type:'group',channel:'web',members:[
  {id:'owner',name:'Owner',type:'user',is_owner:true},{id:'p',name:'P',type:'agent'},{id:'q',name:'Q',type:'agent'},{id:'e',name:'E',type:'agent'}]}});
 expect(JSON.stringify(frozen)).toBe(original);
 frozen.payload.representation='owner';
 expect(personalReviewAction(frozen)).toMatchObject({tool:'send_user_message',representation:'owner',arguments:{target:'group',text}});
 const interactive={format:'openui',source:'root = TextContent("Full visible text")'};
 const attachment={url:'/file',text:'Actual full attachment body',sha256:'content-hash'};
 frozen.payload={...frozen.payload,interactive,attachments:[{url:'/file'}],attachment_snapshots:[attachment]};
 expect(personalReviewAction(frozen).arguments).toEqual({target:'group',text,interactive,attachments:[attachment]});
 frozen.payload={content:'Shared task change',task:{action:'apply',arguments:{graph_id:'graph',base_revision:7,operations:[{op:'update_task',patch:{result:'Full shared task result'}}]},source_message_id:'source'}};
 expect(personalReviewAction(frozen)).toMatchObject({tool:'task_graph',arguments:{...frozen.payload.task.arguments,action:'apply',source_message_id:'source'}});
});

it('keeps current restrictions, external visibility and fixed-notice authority explicit, including unknown access facts',()=>{
 const frozen:any={owner_user_id:'owner',recipient:{conversation_id:'mirror',name:'External contact',conversation_type:'direct',channel:'feishu',members:[]},
  policy:{revision:2,excluded_conversation_ids:['excluded']},sources:[{conversation_id:'allowed',allowed:true},{conversation_id:'revoked',allowed:false},{conversation_id:'unknown'}],
  recipient_risks:[{actor_id:'blocked-contact',status:'blocked',reason:'Actual current restriction'}],
  security_notice:{content:'Exact fixed refusal',owner_notice_message_id:'confirmed-notice'},
  payload:{content:'Exact fixed refusal',attachments:[],attachment_snapshots:[],transport:{kind:'feishu',channel_revision:4,destination:{app_id:'app',source_id:'feishu:app:dm:sender',chat_id:'external-chat'},card:{body:'Full public card'}}}};
 const result=personalReviewAction(frozen);
 expect(result).toMatchObject({arguments:{text:'Exact fixed refusal',card:{body:'Full public card'}},audience:{channel:'feishu',type:'direct',members:[{id:'feishu:app:dm:sender',type:'external'}],destination:frozen.payload.transport.destination},security_notice:frozen.security_notice,
  restrictions:{excluded_conversation_ids:['excluded'],source_access:[{conversation_id:'revoked',access:'denied'},{conversation_id:'unknown',access:'unknown'}],contacts:frozen.recipient_risks}});
 expect(JSON.stringify(result)).not.toContain('channel_revision');
 delete frozen.policy;delete frozen.sources;delete frozen.recipient_risks;
 expect(personalReviewAction(frozen).restrictions).toEqual({source_exclusions:'unknown',source_access:'unknown',contacts:'unknown'});
});
