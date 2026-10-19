import assert from 'node:assert/strict';
import { mkdtemp,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { createRequire } from 'node:module';
const { createServer } = await import(process.cwd()+'/apps/im-server/src/server.ts');
const { digest } = await import(process.cwd()+'/apps/im-server/src/identity.ts');
import { createServer as controlServer } from 'node:http';
const req=createRequire(process.cwd()+'/apps/im-server/package.json');
const WebSocket=req('ws');
const dir=await mkdtemp(join(tmpdir(),'nano-issue128-audit-'));let app;const sockets=[];let control;
try {
 app=await createServer({dbPath:join(dir,'im.sqlite'),publicUrl:'http://127.0.0.1:53186',jwtSecret:'isolated-issue128-audit-secret'});
 const db=app.im.db;
 const hash='$2b$12$EF/L52c0/DOIAIzztg.vLeo3btIdIuVbW5/M3UBiyztqi7ZLIfTUW';
 for(const id of ['alice','bob','charlie'])db.prepare("INSERT INTO users(id,username,display_name,owner_id,password_hash,membership_status,is_company_admin,personal_space_enabled,created_at) VALUES(?,?,?,?,?,'active',1,1,datetime('now'))").run(id,id,id,id,hash);
 for(const owner of ['alice','bob']){
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES(?,?,?,'offline')").run(owner+'-node',owner,owner+' node');
  db.prepare('INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES(?,?,1,?)').run(owner+'-node',owner,digest(owner+'-runtime-secret'));
 }
 for(const [id,owner,space] of [['alpha','alice','company:default'],['beta','alice','company:default'],['gamma','bob','company:default'],['palpha','alice','personal:alice'],['pbeta','alice','personal:alice']]){
  db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,work_mode,space_id,created_at,updated_at) VALUES(?,?,?,?,'global',?,datetime('now'),datetime('now'))").run(id,owner,owner+'-node',id,space);app.im.messaging.agentUser(id);
 }
 const base=await app.listen({port:58054,host:'127.0.0.1'});const tokens={};
 async function http(method,path,user='alice',body){const r=await fetch(base+path,{method,headers:{'content-type':'application/json',...(tokens[user]?{authorization:'Bearer '+tokens[user]}:{})},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,body:await r.json()};}
 for(const user of ['alice','bob']){const r=await http('POST','/im/v1/auth/login',user,{username:user,password:'old-password'});assert.equal(r.status,200,JSON.stringify(r));tokens[user]=r.body.access_token;}
 async function node(owner,agents){
  const socket=new WebSocket(base.replace('http:','ws:')+'/im/ws/gateway',{headers:{authorization:'Bearer '+owner+'-runtime-secret'}});sockets.push(socket);let waiting;
  socket.on('message',raw=>{const f=JSON.parse(raw.toString());if(waiting&&(f.type==='error'||f.type==='ack'&&f.payload.message_type===waiting.type||f.type==='agent.work.ack'&&waiting.type==='agent.work.append')){const w=waiting;waiting=undefined;clearTimeout(w.timer);w.resolve(f);}});
  await once(socket,'open');
  async function send(type,payload){const r=await new Promise((resolve,reject)=>{waiting={type,resolve,reject,timer:setTimeout(()=>{waiting=undefined;reject(Error('timeout '+type));},4000)};socket.send(JSON.stringify({type,payload:{node_id:owner+'-node',...payload}}));});assert.notEqual(r.type,'error',JSON.stringify(r));return r.payload;}
  await send('node.register',{agents});return send;
 }
 const alice=await node('alice',['alpha','beta','palpha','pbeta']);const bob=await node('bob',['gamma']);const outputs=[];
 const group=await http('POST','/im/v1/conversations','alice',{title:'发布计划协作',type:'group',participants:[{type:'agent',id:'alpha'},{type:'agent',id:'beta'}]});
 assert.equal(group.status,201,JSON.stringify(group));
 await alice('agent.message',{from_session_id:'alpha|tool_call:baseline-one',to:'conversation:'+group.body.id,text:'我已整理发布清单。Scout，请复核数据库迁移和回滚步骤。'});
 await alice('agent.message',{from_session_id:'beta|tool_call:baseline-two',to:'conversation:'+group.body.id,text:'已核对：迁移可以回滚。建议在发布前保留最近一份数据库备份。'});
 console.log(JSON.stringify({base,chat:group.body.id,username:'alice',password:'old-password'}));
 control=controlServer(async(request,response)=>{
  try{
   if(request.url==='/send') await alice('agent.message',{from_session_id:'alpha|tool_call:'+Date.now(),to:'agent:gamma',text:'新进展：备份已经完成，发布清单已更新。'});
   else if(request.url==='/seed') {
    await alice('agent.message',{from_session_id:'alpha|tool_call:cross-history',to:'agent:gamma',text:'跨 owner 协作：请复核发布清单。'});
    await bob('agent.message',{from_session_id:'gamma|tool_call:cross-reply',to:'agent:alpha',text:'已复核，回滚步骤完整。'});
    await alice('agent.message',{from_session_id:'alpha|tool_call:same-history',to:'agent:beta',text:'同 owner 协作历史。'});
    await alice('agent.message',{from_session_id:'palpha|tool_call:personal-history',to:'agent:pbeta',text:'私人空间协作历史。'});
   } else if(request.url==='/revoke') db.prepare("UPDATE agent_profiles SET owner_id='bob' WHERE agent_id='alpha'").run();
   else if(request.url==='/restore') db.prepare("UPDATE agent_profiles SET owner_id='alice' WHERE agent_id='alpha'").run();
   else {response.writeHead(404);response.end();return;}
   response.end('ok');
  }catch(e){response.writeHead(500);response.end(String(e));}
 });
 control.listen(58055,'127.0.0.1');
 await new Promise(resolve=>process.once('SIGTERM',resolve));
}finally{control?.close();for(const s of sockets)s.terminate();if(app)await app.close();await rm(dir,{recursive:true,force:true});}
