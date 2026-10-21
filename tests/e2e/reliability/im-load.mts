/** Manual real HTTP/WS load gate. Run with tsx; defaults to two ten-minute phases. */
import {mkdtempSync,writeFileSync} from 'node:fs';
import {tmpdir,cpus,totalmem} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {openDatabase} from '../../../apps/im-server/src/db.js';
import {digest} from '../../../apps/im-server/src/identity.js';
import {WebRelayConnection} from '../../../packages/channels/src/index.js';
import {InboxStore} from '../../../packages/personal-assistant/src/inbox.js';
import {WorkSync} from '../../../packages/personal-assistant/src/work-sync.js';
const duration=Number(process.env.IM_LOAD_SECONDS??600)*1000;
const directory=mkdtempSync(join(tmpdir(),'im-reliability-load-'));
const dbPath=join(directory,'im.db'),db=openDatabase(dbPath);
const child=spawn(process.execPath,['--import','tsx','apps/im-server/src/main.ts','serve','--host','127.0.0.1','--port','0'],{cwd:process.cwd(),env:{...process.env,IM_DB_PATH:dbPath,IM_PUBLIC_URL:'http://127.0.0.1',IM_JWT_SECRET:'isolated-load-secret',IM_PUBLIC_MODE:'0'},stdio:['ignore','pipe','pipe']});
let errors='';child.stderr.on('data',chunk=>errors+=chunk);
const port=await new Promise<number>((resolve,reject)=>{const timer=setTimeout(()=>reject(Error(errors)),15000);child.stdout.on('data',chunk=>{const match=String(chunk).match(/IM listening on (\d+)/);if(match){clearTimeout(timer);resolve(Number(match[1]));}});child.once('exit',()=>{clearTimeout(timer);reject(Error(errors));});});
const url=`http://127.0.0.1:${port}`;
db.prepare("INSERT INTO users(id,username,display_name,owner_id,password_hash,membership_status,is_company_admin,created_at) VALUES('owner','load','Load','owner',?,'active',1,?)").run('$2b$12$EF/L52c0/DOIAIzztg.vLeo3btIdIuVbW5/M3UBiyztqi7ZLIfTUW',new Date().toISOString());
let token='';
async function http(path:string,body?:unknown,key?:string){const response=await fetch(url+path,{method:body===undefined?'GET':'POST',headers:{authorization:`Bearer ${token}`,...(body===undefined?{}:{'content-type':'application/json'}),...(key?{'Idempotency-Key':key}:{})},body:body===undefined?undefined:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(`${response.status} ${JSON.stringify(data)}`);return data as any;}
token=(await http('/im/v1/auth/login',{username:'load',password:'old-password'})).access_token;
const nodes:{relay:WebRelayConnection;inbox:InboxStore;sync:WorkSync;chat:string;node:string;agent:string;credential:string}[]=[];
let phase:any;const starts=new Map<string,number>();const pending=new Set<Promise<unknown>>();
for(let i=0;i<100;i++){
 const node=`load-${i}`,agent=`agent-${i}`,credential=`isolated-runtime-${i}`;
 db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES(?,'owner',?,'offline')").run(node,node);
 db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES(?,'owner',1,?)").run(node,digest(credential));
 const inbox=new InboxStore(join(directory,`${node}.db`));
 const relay=new WebRelayConnection({url,requiredCapabilities:['relay_request_ids','work_sync_http'],credentials:()=>({accessToken:credential,registration:{node_id:node,agents:[agent],agent_work_modes:{[agent]:'global'}}}),onFrame:async frame=>{
  if(frame.type!=='relay.message')return;
  const input=frame.payload as any;const key=input.message.content;inbox.acceptRelay(input,true);
  if(phase&&starts.has(key)){if(phase.received.has(key))phase.redeliveries++;else{phase.received.add(key);phase.accept.push(performance.now()-starts.get(key)!);}}
  await relay.request('node.delivery_receipt',{node_id:node,relay_task_id:input.relay_task_id,delivery_status:'sent'});
 },onError:error=>{if(phase)phase.errors.push(String(error));}});
 await relay.start();
 await relay.request('agent.session.ensure',{node_id:node,agent_id:agent,session_id:`session-${i}`});
 const chat=(await http('/im/v1/conversations',{title:`Load ${i}`,type:'direct',participants:[{type:'agent',id:agent}]})).id;
 const sync=new WorkSync({nodeId:node,inbox,url,credentials:()=>credential,onError:error=>{if(phase)phase.workErrors[String(error)]=(phase.workErrors[String(error)]??0)+1;}});
 nodes.push({relay,inbox,sync,chat,node,agent,credential});
}
const quantile=(values:number[])=>[...values].sort((a,b)=>a-b)[Math.min(values.length-1,Math.floor(values.length*.99))]??null;
function appendBatch(index:number){const n=nodes[index]!;const batch=n.inbox.journalSeq;for(let i=0;i<100;i++)n.inbox.append({event_id:`${index}-${batch+i}`,root_agent_id:n.agent,session_id:`session-${index}`,type:batch===0&&i===0?'session_registered':'recording_degraded',payload:batch===0&&i===0?{scope:'global_main'}:{reason:'load',text:'x'.repeat(i===1?106*1024:14500)},observed_at:'2026-10-21T00:00:00.000Z'});n.sync.signal();}
const summaries:any[]=[];
try{
 for(const loaded of [false,true]){
  phase={name:loaded?'with-work':'without-work',sent:0,received:new Set<string>(),save:[],accept:[],errors:[],workErrors:{},redeliveries:0};starts.clear();
  token=(await http('/im/v1/auth/login',{username:'load',password:'old-password'})).access_token;
  const start=performance.now();
  if(loaded)for(let i=0;i<20;i++){appendBatch(i);nodes[i]!.sync.start();}
  let refilling=false;const refill=setInterval(()=>{if(!loaded||refilling)return;refilling=true;void(async()=>{try{for(let i=0;i<20;i++){if(nodes[i]!.inbox.throughSeq===nodes[i]!.inbox.journalSeq)appendBatch(i);await new Promise<void>(r=>setImmediate(r));}}finally{refilling=false;}})();},500);
  const pump=()=>{
   const due=Math.min(Math.floor(duration/50),Math.floor((performance.now()-start)/50));
   while(phase.sent<due){const serial=phase.sent++,n=nodes[20+serial%80]!;const key=`${phase.name}:${serial}`;starts.set(key,performance.now());
   const task=http(`/im/v1/conversations/${n.chat}/messages`,{sender_user_id:'owner',content:key},key).then(()=>phase.save.push(performance.now()-starts.get(key)!)).catch(e=>phase.errors.push(String(e)));
   pending.add(task);void task.finally(()=>pending.delete(task));
   }
  };const send=setInterval(pump,20);
  const report=setInterval(()=>process.stdout.write(JSON.stringify({phase:phase.name,elapsed_s:Math.round((performance.now()-start)/1000),sent:phase.sent,received:phase.received.size,p99_save_ms:quantile(phase.save),p99_accept_ms:quantile(phase.accept),work_through:nodes.slice(0,20).map(n=>n.inbox.throughSeq),errors:phase.errors.slice(0,3)})+'\n'),60000);
  await new Promise(r=>setTimeout(r,duration));pump();clearInterval(send);clearInterval(refill);clearInterval(report);while(refilling)await new Promise<void>(r=>setImmediate(r));await Promise.all(pending);await new Promise(r=>setTimeout(r,1000));
  if(loaded)await Promise.all(nodes.slice(0,20).map(n=>n.sync.stop()));
  const totals=db.prepare("SELECT count(*) n FROM messages WHERE content LIKE ?").get(`${phase.name}:%`) as {n:number};
  const summary={name:phase.name,duration_ms:performance.now()-start,sent:phase.sent,stored:totals.n,received:phase.received.size,p99_save_ms:quantile(phase.save),p99_accept_ms:quantile(phase.accept),redeliveries:phase.redeliveries,errors:phase.errors,work_errors:phase.workErrors,uploaded_events:nodes.slice(0,20).reduce((s,n)=>s+n.inbox.throughSeq,0)};
  summaries.push(summary);process.stdout.write(JSON.stringify({completed:summary})+'\n');
 }
 const [base,loaded]=summaries;const pass=summaries.every(r=>r.sent===r.stored&&r.sent===r.received&&!r.errors.length&&r.redeliveries===0&&r.p99_save_ms<=1000&&r.p99_accept_ms<=2000)&&loaded.p99_save_ms-base.p99_save_ms<=500&&loaded.p99_accept_ms-base.p99_accept_ms<=500;
 const result={pass,node:process.version,cpu:cpus()[0]?.model,cpus:cpus().length,memory_bytes:totalmem(),duration_per_phase_seconds:duration/1000,nodes:100,bulk_nodes:20,messages_per_second:20,summaries};
 writeFileSync(process.env.IM_LOAD_OUTPUT??join(directory,'result.json'),JSON.stringify(result,null,2));process.stdout.write(JSON.stringify({result})+'\n');if(!pass)process.exitCode=1;
}finally{await Promise.all(nodes.map(n=>n.sync.stop()));await Promise.all(nodes.map(n=>n.relay.stop()));for(const n of nodes)n.inbox.close();child.kill('SIGTERM');await once(child,'exit');db.close();}
