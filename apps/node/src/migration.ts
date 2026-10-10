/** One-time, offline conversion. Sources are opened read-only and never activated. */
import {DatabaseSync, backup} from 'node:sqlite';
import {readFile, writeFile, mkdir, copyFile, rename, rm, access, chmod, readdir} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {load, dump} from 'js-yaml';
import {NodeStore, InboxStore, ExternalStore} from '@nano/personal-assistant';
import {agentConfigurationFingerprint, type SessionBinding, type RelayInput} from '@nano/product-contracts';
import type {NodeConfigurationFile} from './configuration.js';
type Row = Record<string, any>;
const json = (value: unknown) => JSON.stringify(value);
const exists = async (path: string) => access(path).then(()=>true,()=>false);
const toolMap: Record<string,string[]> = {agent:['subagent','subagent_fork','send_message','list_agents'],task_stop:['interrupt_agent','job_kill','job_list','job_output'],skill_view:['skill'],Workflow:['workflow'],cron:['schedule_create','schedule_list','schedule_update','schedule_delete','schedule_run','schedule_history']};

export async function migrateNode(sourceRoot: string, destination: string) {
  sourceRoot=resolve(sourceRoot); destination=resolve(destination);
  if(sourceRoot===destination)throw new Error('Migration requires a separate empty destination');
  const configText=await readFile(join(sourceRoot,'config.yaml'),'utf8');
  const sourceHash=createHash('sha256').update(configText).digest('hex');
  if(await exists(destination))throw new Error('Destination already exists; keep it as a completed rehearsal or choose a new empty directory');
  const config=load(configText) as NodeConfigurationFile;
  if(!config.node.user_id)throw new Error('Source node has no bound owner');
  const staging=destination+'.staging-'+randomUUID();await mkdir(staging,{recursive:true,mode:0o700});
  const archive=join(staging,'migration-source');await mkdir(archive,{mode:0o700});
  const home=join(staging,'.dsh-runtime',config.node.node_id);await mkdir(home,{recursive:true,mode:0o700});
  const tables: Record<string,Row[]>={};const counts:Record<string,number>={};
  const blockers:string[]=[];const mappings:Row[]=[];
  try {
    for(const name of ['global_agent.sqlite3','session_bindings.sqlite3','group_context_buffer.sqlite3','relay_dedup.sqlite3','external_shadow_sagas.sqlite3']) {
      const path=join(sourceRoot,name);if(!await exists(path))continue;
      const db=new DatabaseSync(path,{readOnly:true});
      try {
        await backup(db,join(archive,name));
        const snapshot=new DatabaseSync(join(archive,name),{readOnly:true});
        try {for(const row of snapshot.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").all() as {name:string}[]) {
          tables[row.name]=snapshot.prepare(`SELECT * FROM "${row.name}"`).all() as Row[];counts[row.name]=tables[row.name]!.length;
        }}finally{snapshot.close();}
      }finally{db.close();}
    }
    for(const name of ['config.yaml','config-apply-receipts-v1.json','channel-manifest-v1.json','channel-credentials-v1.pem','heartbeat-state.json','device-binding-operation.json']) {
      if(await exists(join(sourceRoot,name))){await copyFile(join(sourceRoot,name),join(archive,name));await chmod(join(archive,name),0o600);}
    }
    if(await exists(join(sourceRoot,'device-binding-operation.json')))blockers.push('Device binding operation must be reconciled before cutover');
    for(const row of tables.gateway_pending_external_control_deliveries??[])blockers.push(`External control ${row.operation_id}: ${row.state}; retain original dispatch identity and reconcile its actual outcome`);
    for(const row of tables.external_shadow_bubbles??[])if(row.state!=='reconciled')blockers.push(`Shadow bubble ${row.shadow_message_id}: ${row.state}`);
    for(const row of tables.gateway_control_operations??[])if(row.status!=='completed')blockers.push(`Control ${row.operation_id}: ${row.status}`);
    for(const row of tables.agent_config_boundary_outbox??[])blockers.push(`Configuration boundary ${row.boundary_id} is pending`);
    for(const row of tables.agent_config_pending_shadow_boundaries??[])blockers.push(`Pending shadow boundary for ${row.agent_id}`);
    const node=new NodeStore(join(home,'node.sqlite3'),config.node.user_id);node.close();
    const inbox=new InboxStore(join(home,'global.sqlite3'));inbox.close();
    const external=new ExternalStore(join(home,'external.sqlite3'));external.close();
    const n=new DatabaseSync(join(home,'node.sqlite3')), g=new DatabaseSync(join(home,'global.sqlite3')), e=new DatabaseSync(join(home,'external.sqlite3'));
    try {
      n.exec('CREATE TABLE migration_bindings(old_session_id TEXT,session_key TEXT PRIMARY KEY,new_session_id TEXT,created_at TEXT,reply_context TEXT)');
      const agents=new Map(config.agents.map(a=>[a.agent_id,a]));
      for(const a of config.agents) {
        a.workspace_root=resolve(a.workspace_root??join(sourceRoot,'workspaces',a.agent_id));
        if(Array.isArray(a.tool_allowlist))a.tool_allowlist=[...new Set(a.tool_allowlist.flatMap(name=>toolMap[String(name)]??[String(name)]))];
        const cron=join(a.workspace_root,'.nanoassistant/cron/jobs.json');
        if(await exists(cron)) {
          const jobs=JSON.parse(await readFile(cron,'utf8'));await writeFile(join(archive,`cron-${a.agent_id}.json`),json(jobs),{mode:0o600});
          if(Array.isArray(jobs)&&jobs.length)blockers.push(`Agent ${a.agent_id} has ${jobs.length} legacy Cron definitions requiring an explicit native schedule import`);
        }
      }
      const byConversation=new Map<string,SessionBinding>();
      const bind=(agentId:string,conversationId:string,oldSessionId:string,sessionKey:string,createdAt:string,reply:Row={})=>{
        const a=agents.get(agentId);if(!a)return;
        const key=agentId+'\0'+conversationId;
        let b=byConversation.get(key);
        if(!b){b={agentId,conversationId,sessionId:randomUUID(),ownerId:config.node.user_id,cwd:a.workspace_root,revision:agentConfigurationFingerprint({...a,display_name:a.title??a.display_name})};byConversation.set(key,b);n.prepare('INSERT INTO sessions VALUES(?,?,?,?)').run(b.sessionId,agentId,conversationId,json(b));}
        n.prepare('INSERT OR IGNORE INTO migration_bindings VALUES(?,?,?,?,?)').run(oldSessionId,sessionKey,b.sessionId,createdAt,json(reply));
        mappings.push({agentId,oldSessionId,sessionKey,newSessionId:b.sessionId,createdAt,conversationId});
        if(reply.metadata?.conversation_type==='direct'&&reply.channel_name==='web_relay')n.prepare('INSERT OR IGNORE INTO canonical_sessions VALUES(?,?)').run(agentId,b.sessionId);
        return b;
      };
      for(const row of [...(tables.session_bindings??[])].sort((a,b)=>String(a.created_at).localeCompare(String(b.created_at)))) {
        const agentId=String(row.session_key).split(':').at(-1)!;const a=agents.get(agentId);if(!a||a.work_mode==='global')continue;
        const reply=JSON.parse(row.reply_context_json);const sk=String(row.session_key);
        const conversation=sk.startsWith('feishu:')?`external:${agentId}:${sk.slice(7,-agentId.length-1)}`:reply.target_chat_id;
        bind(agentId,conversation,row.kernel_session_id,sk,row.created_at,reply);
        if(sk.startsWith('feishu:')&&reply.metadata?.conversation_id)n.prepare('INSERT OR REPLACE INTO conversation_aliases VALUES(?,?,?)').run(agentId,reply.metadata.conversation_id,conversation);
      }
      for(const a of config.agents.filter(a=>a.work_mode==='global')){
        const old=(tables.global_sessions??[]).find(row=>row.agent_id===a.agent_id);bind(a.agent_id,`global:${a.agent_id}`,old?.session_id??'',`global:${a.agent_id}`,'');
      }
      for(const row of tables.relay_deduplication_keys??[])n.prepare('INSERT INTO migration_relay_keys VALUES(?,?,?)').run(row.idempotency_key,row.expires_at,row.seen_at);
      for(const row of tables.group_context_buffer??[]) {
        const [agentId,channel,...target]=String(row.buf_key).split(':');if(!agents.has(agentId!))continue;
        const metadata=JSON.parse(row.metadata_json??'{}');const conversationId=channel==='web_relay'?target.join(':'):`external:${agentId}:${target.join(':')}`;
        const id=metadata._im_source_reference?.message_id??`migration-group:${row.id}`;
        const input:RelayInput={agent_id:agentId!,conversation_id:conversationId,relay_task_id:`migration-group:${row.id}`,idempotency_key:`migration-group:${row.id}`,metadata:{...metadata,context_only:true,conversation_type:'group',source_time:new Date(row.ts*1000).toISOString()},message:{id,content:row.text,sender_type:metadata.sender_type??'user',sender_user_id:row.sender,attachments:[]}};
        n.prepare('INSERT OR IGNORE INTO group_background VALUES(?,?,?,?)').run(`${agentId}:${id}`,agentId!,conversationId,json(input));
      }
      const targetMap=new Map<string,string>();
      for(const row of tables.inbox_targets??[]) {
        const data=JSON.parse(row.data);const target=['web','web_relay'].includes(data.channel)?data.conversation_id??row.target:`external:${row.agent_id}:${row.target.replace(/^feishu:/,'')}`;
        targetMap.set(row.agent_id+'\0'+row.target,target);g.prepare('INSERT OR REPLACE INTO targets VALUES(?,?,?)').run(row.agent_id,target,data.name??target);
      }
      for(const row of tables.inbox_entries??[]) {
        if(!agents.has(row.agent_id))continue;
        const data=JSON.parse(row.data);const target=targetMap.get(row.agent_id+'\0'+row.target)??data.source?.conversation_id??row.target;
        const id=data.message_id??row.ingress_key;const parts=data.parts as {part_key:string;content:Row[]}[];
        const input:RelayInput={agent_id:row.agent_id,conversation_id:target,relay_task_id:row.ingress_key,idempotency_key:row.ingress_key,metadata:{source_time:data.source_time,created_at:data.received_at,sender_name:data.sender?.name,migration_source:{seq:row.seq,ingress_key:row.ingress_key}},message:{id,content:parts.flatMap(p=>p.content).filter(p=>p.type==='text').map(p=>p.text??'').join(''),sender_type:data.sender?.kind??data.sender?.type??'system',sender_user_id:data.sender?.id??'',attachments:[]}};
        const seq=Number(g.prepare('INSERT INTO inbox(agent_id,target,message_id,payload,attention,consumed) VALUES(?,?,?,?,?,?)').run(row.agent_id,target,id,json(input),row.requires_attention,row.consumed_at?1:0).lastInsertRowid);
        parts.forEach((part,index)=>{g.prepare('INSERT INTO imported_parts VALUES(?,?,?)').run(seq,index,json(part.content));if(row.consumed_at||(tables.inbox_consumed_parts??[]).some(c=>c.agent_id===row.agent_id&&c.entry_seq===row.seq&&c.part_key===part.part_key))g.prepare('INSERT INTO fragments VALUES(?,?)').run(seq,index);});

      }
      for(const agent of config.agents) {
        const pending=g.prepare('SELECT 1 FROM inbox WHERE agent_id=? AND attention=1 AND consumed=0').get(agent.agent_id);
        if(!pending){const max=g.prepare('SELECT coalesce(max(seq),0) AS seq FROM inbox WHERE agent_id=?').get(agent.agent_id) as {seq:number};g.prepare('INSERT INTO wakes VALUES(?,?)').run(agent.agent_id,max.seq);}
      }
      for(const row of tables.external_shadow_sagas??[]) {
        if(!agents.has(row.agent_id))continue;
        const original=JSON.parse(row.canonical_inbound_json), reply=JSON.parse(row.reply_context_json);const sourceId=row.external_chat_id;
        const appId=String(sourceId).split(':')[1];if(!appId)throw new Error('External source has no connector identity');
        const chatId=`external:${row.agent_id}:${sourceId}`, eventId=`external:${row.agent_id}:${appId}:${row.provider_event_id}`;
        const message={messageId:row.provider_event_id,chatId:reply.target_chat_id,senderId:original.external_user_id,isGroup:original.is_group,mentioned:false,time:0,parts:[{type:'text',text:original.text??''}]};
        const chat={id:chatId,agentId:row.agent_id,appId,chatId:reply.target_chat_id,sourceId,isGroup:original.is_group,shadowId:row.conversation_id};
        e.prepare('INSERT OR REPLACE INTO chats VALUES(?,?,?)').run(chatId,row.agent_id,json(chat));
        const input={agent_id:row.agent_id,conversation_id:chatId,relay_task_id:eventId,idempotency_key:eventId,metadata:{channel:'feishu',external_reply:eventId},message:{id:eventId,content:original.text??'',sender_type:'user',sender_user_id:original.external_user_id,attachments:[]}};
        e.prepare('INSERT OR IGNORE INTO inbound(id,chat_id,body,accepted,mirror) VALUES(?,?,?,1,?)').run(eventId,chatId,json({message,input}),row.im_message_id);
        if(row.conversation_id)n.prepare('INSERT OR REPLACE INTO conversation_aliases VALUES(?,?,?)').run(row.agent_id,row.conversation_id,chatId);
        if(!row.im_message_id)blockers.push(`External input ${row.saga_id} lacks its IM mirror; reconcile before activation`);
      }
    }finally{n.close();g.close();e.close();}
    if(await exists(join(sourceRoot,'channel-credentials-v1.pem')))await copyFile(join(sourceRoot,'channel-credentials-v1.pem'),join(staging,'channel-credentials-v1.pem'));
    const manifestPath=join(sourceRoot,'channel-manifest-v1.json');
    if(await exists(manifestPath)) {
      const legacy=JSON.parse(await readFile(manifestPath,'utf8'));const db=new DatabaseSync(join(home,'channels.sqlite3'));
      try {db.exec('CREATE TABLE state(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT,type TEXT NOT NULL,payload TEXT NOT NULL)');if(legacy.manifest)db.prepare('INSERT INTO state VALUES(?,?)').run('manifest',json({...legacy.manifest,request_id:randomUUID()}));}finally{db.close();}
      if(legacy.outbox?.head||Object.keys(legacy.outbox?.removal_outcomes??{}).length)blockers.push('Channel removal/control acknowledgement is pending');
      if(legacy.retry_manifest)blockers.push('Channel reconciliation has a pending retry manifest');
      if(Object.values(legacy.status_outbox??{}).some((entry:any)=>entry.inflight||entry.latest||entry.barrier))blockers.push('Channel status receipt is pending');
    }
    const hb=new DatabaseSync(join(home,'heartbeat.sqlite3'));
    try {hb.exec('CREATE TABLE due(agent TEXT,task TEXT,time INTEGER,PRIMARY KEY(agent,task)); CREATE TABLE pending(agent TEXT PRIMARY KEY,intent TEXT NOT NULL)');
      if(await exists(join(sourceRoot,'heartbeat-state.json'))){const state=JSON.parse(await readFile(join(sourceRoot,'heartbeat-state.json'),'utf8'));for(const [agent,value] of Object.entries(state.agents??{}) as [string,Row][]) {for(const [task,time] of Object.entries(value.per_task_last_due??{}))hb.prepare('INSERT INTO due VALUES(?,?,?)').run(agent,task,Date.parse(String(time)));if(value.last_due_at)hb.prepare('INSERT OR IGNORE INTO due VALUES(?,?,?)').run(agent,'default',Date.parse(value.last_due_at));}}
    }finally{hb.close();}
    const pluginsPath=join(sourceRoot,'plugins.json');
    const plugins: Row[]=await exists(pluginsPath)?JSON.parse(await readFile(pluginsPath,'utf8')):[];
    const toolsRoot=join(sourceRoot,'tools');
    if(await exists(toolsRoot))for(const name of await readdir(toolsRoot))if(name.endsWith('.py')) {
      const body=await readFile(join(toolsRoot,name));const hash=createHash('sha256').update(body).digest('hex');
      await writeFile(join(archive,name),body,{mode:0o600});
      if(hash==='10eda4f535768fbca5fe2fdf91293ef7413de7e89ee7b41d6575cdccab860067') {
        if(!plugins.some(p=>p.module==='@nano/dsh-integration/assets/social-tools'))plugins.push({module:'@nano/dsh-integration/assets/social-tools'});
      }else if(hash==='50e5feab4050cd9228fd953cf19908fc69f958cf75b23321e5a708ca05407482') {
        await writeFile(join(staging,'owner-echo.mjs'),`export const name='user-plugin-reviewer';
export const inject=['tools'];
export function apply(ctx){ctx.tools.register({name:'user_plugin_reviewer',description:'User-level plugin test tool — confirms owner plugin discovery.',parameters:{type:'object',properties:{msg:{type:'string'}},additionalProperties:false},output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},async execute(args){return 'User plugin discovered! msg='+(args.msg??'none');}});}
`,{mode:0o600});
        if(!plugins.some(p=>p.module==='./owner-echo.mjs'))plugins.push({module:'./owner-echo.mjs'});
      }else blockers.push(`Unconverted owner tool ${name} (${hash})`);
    }
    if(plugins.length)await writeFile(join(staging,'plugins.json'),json(plugins),{mode:0o600});
    for(const root of [join(sourceRoot,'hooks'),...config.agents.flatMap(a=>[join(a.workspace_root,'.nanoassistant/tools'),join(a.workspace_root,'.nanoassistant/hooks')])]) {
      if(await exists(root))for(const name of await readdir(root))if(name.endsWith('.py'))blockers.push(`Unconverted workspace tool or hook: ${join(root,name)}`);
    }
    config.gateway={...config.gateway,autostart:false};
    await writeFile(join(staging,'config.yaml'),dump(config,{noRefs:true}),{mode:0o600});
    const report={version:1,sourceRoot,sourceConfigHash:sourceHash,nodeId:config.node.node_id,createdAt:new Date().toISOString(),counts,mappings,blockers,readyForCutover:blockers.length===0,notes:['Source databases and operation facts retained in migration-source; old transcripts stay in their original owner root.','New DSH Sessions and Work journal have distinct identities; prior consent is not imported.','No service started. Rehearsal does not establish that production ingress was drained.']};
    await writeFile(join(staging,'migration-report.json'),json(report),{mode:0o600});await rename(staging,destination);return report;
  }catch(error){await rm(staging,{recursive:true,force:true});throw error;}
}
