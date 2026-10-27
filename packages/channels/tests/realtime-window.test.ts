import { afterEach, expect, test } from 'vitest';
import { WebSocketServer, type WebSocket } from 'ws';
import { WebRelayConnection, type ProtocolFrame } from '../src/index.js';
const cleanups: (()=>Promise<void>)[]=[];
afterEach(async()=>{for(const fn of cleanups.splice(0).reverse())await fn();});
async function setup(handle:(s:WebSocket,f:ProtocolFrame)=>void,ackTimeoutMs=60){
 const frames:ProtocolFrame[]=[];const wss=new WebSocketServer({port:0});await new Promise<void>(r=>wss.once('listening',r));
 wss.on('connection',s=>s.on('message',data=>{const f=JSON.parse(String(data));frames.push(f);if(f.type==='node.register')s.send(JSON.stringify({type:'ack',payload:{message_type:f.type,request_id:f.payload.request_id,relay_request_ids:1,work_sync_http:1}}));else handle(s,f);}));
 cleanups.push(async()=>{for(const s of wss.clients)s.terminate();await new Promise<void>(r=>wss.close(()=>r()));});
 const relay=new WebRelayConnection({url:`http://127.0.0.1:${(wss.address() as {port:number}).port}`,credentials:()=>({accessToken:'test',registration:{node_id:'n'}}),onFrame(){},ackTimeoutMs,heartbeatIntervalMs:20});cleanups.push(()=>relay.stop());await relay.start();return {relay,frames};
}
function ack(s:WebSocket,f:ProtocolFrame){s.send(JSON.stringify({type:'ack',payload:{message_type:f.type,request_id:f.payload.request_id}}));}
test('a lost business ACK leaves realtime control and heartbeat usable and a late ACK cannot settle another send',async()=>{
 let first:ProtocolFrame|undefined;let socket:WebSocket|undefined;
 const {relay,frames}=await setup((s,f)=>{socket=s;if(f.type==='agent.message'){if(!first){first=f;return;}if(f.payload.text==='second'){s.send(JSON.stringify({type:'ack',payload:{message_type:f.type,request_id:first.payload.request_id}}));return;}}ack(s,f);});
 const lost=relay.request('agent.message',{text:'first'});const rejected=expect(lost).rejects.toMatchObject({delivery:'unknown'});
 await expect(relay.request('node.delivery_receipt',{})).resolves.toMatchObject({type:'ack'});await rejected;expect(relay.ready).toBe(true);
 let settled=false;const second=relay.request('agent.message',{text:'second'}).then(()=>{settled=true;});
 await new Promise(r=>setTimeout(r,10));expect(settled).toBe(false);
 const frame=frames.find(f=>f.payload.text==='second')!;expect(frame.payload.request_id).not.toBe(first!.payload.request_id);ack(socket!,frame);await second;
 expect(frames.some(f=>f.type==='node.heartbeat')).toBe(true);expect(frames.filter(f=>f.type==='node.register')).toHaveLength(1);
});
test('six ordinary requests leave two slots for control and bound unsent queue',async()=>{
 const {relay,frames}=await setup((s,f)=>{if(f.type==='node.heartbeat'||f.type==='node.delivery_receipt')ack(s,f);});
 const pending=Array.from({length:262},(_,i)=>relay.request('agent.message',{agent_id:`a${i%3}`}));const settled=pending.map(p=>p.catch(e=>e));
 await expect(relay.request('agent.message',{})).rejects.toMatchObject({delivery:'not-sent'});
 await expect(relay.request('node.delivery_receipt',{})).resolves.toMatchObject({type:'ack'});
 expect(frames.filter(f=>f.type==='agent.message')).toHaveLength(6);await relay.stop();await Promise.all(settled);
});
test('three Agent publications rotate across a backlog using their real operation scopes',async()=>{
 let socket:WebSocket|undefined;
 const {relay,frames}=await setup((s,f)=>{socket=s;if(f.type==='node.heartbeat')ack(s,f);},1000);
 const send=(agent:string,i:number)=>relay.request('agent.message',{from_session_id:`${agent}|tool_call:${i}`,text:String(i)}).catch(e=>e);
 const requests=Array.from({length:8},(_,i)=>send('a',i));requests.push(...Array.from({length:3},(_,i)=>send('b',i)),send('c',0));
 await expect.poll(()=>frames.filter(f=>f.type==='agent.message').length).toBe(6);
 for(let i=0;i<3;i++)ack(socket!,frames.filter(f=>f.type==='agent.message')[i]!);
 await expect.poll(()=>frames.filter(f=>f.type==='agent.message').length).toBe(9);
 expect(frames.filter(f=>f.type==='agent.message').slice(6,9).map(f=>String(f.payload.from_session_id).split('|')[0])).toEqual(['b','c','a']);
 await relay.stop();await Promise.all(requests);
});
