/** Deterministic Anthropic SSE fixture for the real DSH process and known workspace tool effects. */
import {randomUUID} from 'node:crypto';
import http from 'node:http';
import {writeFileSync,appendFileSync} from 'node:fs';
const tools=body=>body.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(c=>c.type==='tool_use');
function results(body){const out=[];for(const m of body.messages)for(const c of Array.isArray(m.content)?m.content:[])if(c.type==='tool_result'){const chunks=typeof c.content==='string'?[c.content]:(c.content??[]).filter(x=>x.type==='text').map(x=>x.text);for(const text of chunks)try{out.push(JSON.parse(text));}catch{}}return out;}
const server=http.createServer(async(req,res)=>{
 let raw='';for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw),blocks=[];const boundary=body.messages.findLastIndex(m=>m.role==='user'&&JSON.stringify(m.content).includes('New messages are waiting in your Inbox'));const window={messages:body.messages.slice(Math.max(0,boundary))};const used=tools(window),facts=results(window),lastRead=facts.findLast(x=>Array.isArray(x.messages)&&x.target),lastCheck=facts.findLast(x=>Array.isArray(x.sources));
 const lastUse=used.at(-1);const marker=lastRead?.messages.flatMap(m=>(m.content??[]).filter(c=>c.type==='text').map(c=>c.text)).join('\n')??'';
 appendFileSync('.e2e-provider-requests.jsonl',JSON.stringify({at:new Date().toISOString(),session:req.headers['x-session-id'],lastUse:lastUse?.name,facts:facts.map(f=>Object.keys(f)),marker:marker.slice(0,500),tools:body.tools?.map(t=>({name:t.name,input_schema:t.input_schema}))})+'\n');
 const tool=(name,input)=>blocks.push({type:'tool_use',id:`fixture-${randomUUID()}`,name,input});
 if(lastUse?.name==='send_message')blocks.push({type:'text',text:'NO_REPLY'});
 else if(!lastUse || !lastCheck)tool('inbox',{action:'check'});
 else if(lastUse.name==='inbox'&&lastUse.input.action==='check'){
  const source=lastCheck?.sources?.[0];if(source)tool('inbox',{action:'read',target:source.target});else blocks.push({type:'text',text:'NO_REPLY'});
 }else if(lastRead){
  if(marker.includes('BULK630')&&!used.some(t=>t.name==='write'&&String(t.input.file_path).includes('bulk630'))){
   for(let i=0;i<48;i++)tool('write',{file_path:`bulk630-${i}.txt`,content:'x'.repeat(i===0?106*1024:30000)});
  }else if(marker.includes('FOUR630')&&!used.some(t=>t.name==='write'&&String(t.input.file_path).includes('four630'))){
   tool('write',{file_path:'four630.txt',content:'F'.repeat(4*1024*1024)});
  }else if(marker.includes('CRASH630')&&!used.some(t=>t.name==='write')){tool('write',{file_path:'crash630-effect-'+marker.split(/\s+/)[1]+'.txt',content:marker});}else tool('send_message',{target:lastRead.target,text:marker.includes('BULK630')?'BULK630_DONE':marker.includes('FOUR630')?'FOUR630_DONE':marker.includes('CRASH630')?'CRASH630_DONE':'FIXTURE630_OK'});
 }else blocks.push({type:'text',text:'NO_REPLY'});
 const toolUse=blocks.some(b=>b.type==='tool_use');res.writeHead(200,{'content-type':'text/event-stream'});
 const emit=(type,data)=>res.write(`event: ${type}\ndata: ${JSON.stringify({type,...data})}\n\n`);
 emit('message_start',{message:{id:`fixture-${randomUUID()}`,type:'message',role:'assistant',model:'fixture-model',content:[],stop_reason:null,usage:{input_tokens:20,output_tokens:0}}});
 for(const [index,block]of blocks.entries()){
  emit('content_block_start',{index,content_block:block.type==='tool_use'?{...block,input:{}}:block});
  if(block.type==='tool_use')emit('content_block_delta',{index,delta:{type:'input_json_delta',partial_json:JSON.stringify(block.input)}});
  emit('content_block_stop',{index});
 }
 emit('message_delta',{delta:{stop_reason:toolUse?'tool_use':'end_turn',stop_sequence:null},usage:{output_tokens:5}});emit('message_stop',{});res.end();
});
await new Promise(r=>server.listen(Number(process.argv[2]??0),'127.0.0.1',r));const url=`http://127.0.0.1:${server.address().port}`;writeFileSync('.e2e-provider.json',JSON.stringify({url,pid:process.pid}));console.log(url);
process.on('SIGTERM',()=>{server.closeAllConnections();server.close(()=>process.exit());});
