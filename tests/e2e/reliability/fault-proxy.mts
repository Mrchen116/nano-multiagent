/** Isolated real HTTP/WS fault proxy; POST /__fault controls Work503 and ACK loss. */
import http from 'node:http';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../../../packages/channels/package.json',import.meta.url));
const {default:WebSocket,WebSocketServer}=await import(require.resolve('ws'));
import {writeFileSync} from 'node:fs';
const target=new URL(process.argv[2]);let workDown=false,dropPublicationAck=0,dropReceiptAck=0;
const server=http.createServer((request,response)=>{
 if(request.url==='/__fault'){let body='';request.on('data',c=>body+=c);request.on('end',()=>{const p=JSON.parse(body||'{}');if('work_down'in p)workDown=p.work_down;if('publication_ack'in p)dropPublicationAck=p.publication_ack;if('receipt_ack'in p)dropReceiptAck=p.receipt_ack;response.end(JSON.stringify({workDown,dropPublicationAck,dropReceiptAck}));});return;}
 if(workDown&&request.url.startsWith('/im/v1/gateway/work-sync/')){request.resume();response.writeHead(503,{'content-type':'application/json','retry-after':'1'});response.end('{"detail":"isolated_work_outage"}');return;}
 const upstream=http.request(new URL(request.url,target),{method:request.method,headers:{...request.headers,host:target.host}},res=>{response.writeHead(res.statusCode,res.headers);res.pipe(response);});upstream.on('error',()=>{response.writeHead(502);response.end();});request.pipe(upstream);
});
const wss=new WebSocketServer({noServer:true});server.on('upgrade',(req,socket,head)=>wss.handleUpgrade(req,socket,head,client=>{
 const upstream=new WebSocket(new URL(req.url,target.href.replace('http','ws')),{headers:req.headers.authorization?{authorization:req.headers.authorization}:{}});const queue=[];
 client.on('message',(data,binary)=>{if(upstream.readyState===WebSocket.OPEN)upstream.send(data,{binary});else queue.push([data,binary]);});
 upstream.on('open',()=>{for(const [data,binary]of queue)upstream.send(data,{binary});queue.length=0;});
 upstream.on('message',(data,binary)=>{const frame=JSON.parse(String(data));if(frame.type==='ack'&&frame.payload.message_type==='agent.message'&&dropPublicationAck>0){dropPublicationAck--;return;}if(frame.type==='ack'&&frame.payload.message_type==='node.delivery_receipt'&&dropReceiptAck>0){dropReceiptAck--;return;}if(client.readyState===WebSocket.OPEN)client.send(data,{binary});});
 upstream.on('close',(code,reason)=>{if(client.readyState===WebSocket.OPEN)client.close(code===1006?1012:code,reason);});client.on('close',()=>upstream.terminate());upstream.on('error',()=>client.terminate());
}));
await new Promise(r=>server.listen(0,'127.0.0.1',r));const url=`http://127.0.0.1:${server.address().port}`;writeFileSync('.e2e-proxy.json',JSON.stringify({url,pid:process.pid}));console.log(url);
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{for(const c of wss.clients)c.terminate();server.closeAllConnections();server.close(()=>process.exit());});
