import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {DatabaseSync} from 'node:sqlite';
import {expect,it} from 'vitest';
import {migrateNode} from '../src/migration.js';
import {InboxStore,NodeStore} from '@nano/personal-assistant';
it('converts exact unread fragments, earliest binding, dedup identity and pending-operation gate without changing source',async()=>{
 const root=await mkdtemp(join(tmpdir(),'nano-migrate-'));const out=root+'-converted';
 try {
  await writeFile(join(root,'config.yaml'),JSON.stringify({node:{node_id:'test',user_id:'owner'},im_service:{url:'http://127.0.0.1:1',token:'fixture'},agents:[{agent_id:'a',workspace_root:root,tool_allowlist:['agent','Workflow']},{agent_id:'g',workspace_root:root,work_mode:'global'}],llm:{default_model:'test',providers:[{name:'test',base_url:'http://127.0.0.1:1',models:[{name:'test'}]}]}}));
  const b=new DatabaseSync(join(root,'session_bindings.sqlite3'));
  b.exec('CREATE TABLE session_bindings(session_key TEXT,kernel_session_id TEXT,reply_context_json TEXT,created_at TEXT); CREATE TABLE gateway_pending_external_control_deliveries(operation_id TEXT,state TEXT)');
  for(const [id,date] of [['later','2026-02-01'],['earliest','2026-01-01']])b.prepare('INSERT INTO session_bindings VALUES(?,?,?,?)').run(`web_relay:${id}:a`,`old-${id}`,JSON.stringify({channel_name:'web_relay',target_chat_id:id,metadata:{conversation_type:'direct'}}),date!);
  b.prepare('INSERT INTO gateway_pending_external_control_deliveries VALUES(?,?)').run('uncertain','outbound_handed_off');b.close();
  const g=new DatabaseSync(join(root,'global_agent.sqlite3'));g.exec('CREATE TABLE inbox_entries(agent_id TEXT,seq INTEGER,ingress_key TEXT,target TEXT,data TEXT,requires_attention INTEGER,consumed_at TEXT); CREATE TABLE inbox_consumed_parts(agent_id TEXT,entry_seq INTEGER,part_key TEXT)');
  const data={message_id:'human-source',sender:{kind:'user',id:'owner'},source:{conversation_id:'chat'},parts:[{part_key:'0:text:0',content:[{type:'text',text:'already read'}]},{part_key:'0:text:24000',content:[{type:'text',text:'still unread'}]}]};
  g.prepare('INSERT INTO inbox_entries VALUES(?,?,?,?,?,?,NULL)').run('g',7,'ingress','chat',JSON.stringify(data),1);g.prepare('INSERT INTO inbox_consumed_parts VALUES(?,?,?)').run('g',7,'0:text:0');g.close();
  const d=new DatabaseSync(join(root,'relay_dedup.sqlite3'));d.exec('CREATE TABLE relay_deduplication_keys(idempotency_key TEXT,expires_at REAL,seen_at REAL)');d.prepare('INSERT INTO relay_deduplication_keys VALUES(?,?,?)').run('prior',Date.now()/1000+1000,1);d.close();
  const before=await readFile(join(root,'config.yaml'));const report=await migrateNode(root,out);
  expect(report.readyForCutover).toBe(false);expect(report.blockers[0]).toContain('uncertain');expect(await readFile(join(root,'config.yaml'))).toEqual(before);
  const home=join(out,'.dsh-runtime/test'), node=new NodeStore(join(home,'node.sqlite3'),'owner');
  expect(node.canonical('a')?.conversationId).toBe('earliest');expect(node.priorRelay('prior')).toBe(true);expect(node.bindings().every(binding=>!binding.sessionId.startsWith('old-'))).toBe(true);node.close();
  const inbox=new InboxStore(join(home,'global.sqlite3'));expect(inbox.wakePending('g')).toBeDefined();const page=inbox.read('g','new','call',{target:'chat'}) as any;
  expect(page.messages).toHaveLength(1);expect(page.messages[0]).toMatchObject({id:'human-source',sender:{id:'owner',type:'user'},content:[{text:'still unread'}]});
  expect(inbox.commitRead('new','call',[{type:'text',text:JSON.stringify(page)}],false,1)).toBe(true);expect(inbox.check('g').sources).toEqual([]);inbox.close();
  await expect(migrateNode(root,out)).rejects.toThrow('Destination already exists');
 }finally{await rm(root,{recursive:true,force:true});await rm(out,{recursive:true,force:true});}
});
