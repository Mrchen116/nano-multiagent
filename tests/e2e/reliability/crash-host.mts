/** Manual crash checkpoint host. Uses the production PA and public official DSH client.
 * Run after stopping the isolated Node: node --import tsx tests/e2e/reliability/crash-host.mts <config> <before-submit|after-submit|after-receipt|after-publication>.
 * The selected boundary freezes this host with SIGSTOP; capture SQLite state, then SIGKILL the recorded host/runtime PIDs and restart the normal Node with the same config.
 * Never use a production config. No database state is written outside the production owners. */
import {writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname,join} from 'node:path';
import {NodeConfiguration} from '../../../apps/node/lib/configuration.js';
import {providerProfiles} from '../../../apps/node/lib/providers.js';
import {applyGatewayEnvironment} from '../../../apps/node/lib/lifecycle.js';
import {createRequire} from 'node:module';
const nodeRequire=createRequire(new URL('../../../apps/node/package.json',import.meta.url));
const {RuntimeSupervisor,prepareProfile}=await import(nodeRequire.resolve('@nano/dsh-integration/client'));
import {WebRelayConnection} from '../../../packages/channels/lib/index.js';
import {GlobalAgent,NodeStore,InboxStore} from '../../../packages/personal-assistant/lib/index.js';
const configPath=resolve(process.argv[2]??'.gateway-config.yaml'),configuration=await NodeConfiguration.read(configPath),config=configuration.value;
applyGatewayEnvironment(config);
const home=join(dirname(configPath),'.dsh-runtime',config.node.node_id),mode=process.argv[3]??'none';
const agents=config.agents.map(a=>configuration.runtime(a)),store=new NodeStore(join(home,'node.sqlite3'),config.node.user_id),inbox=new InboxStore(join(home,'global.sqlite3'));
let product:GlobalAgent,armed=mode==='after-submit-recovery';
function freeze(checkpoint:string,detail:unknown){writeFileSync('.e2e-crash-checkpoint.json',JSON.stringify({checkpoint,detail,host_pid:process.pid,runtime_pid:supervisor.process!.pid,at:new Date().toISOString()}));process.kill(process.pid,'SIGSTOP');return new Promise<never>(()=>{});}
const {providers,env}=providerProfiles(config.llm);await prepareProfile(home,[{id:'llm-pi-ai',config:{providers}}]);
const supervisor=new RuntimeSupervisor({home,cwd:home,env,onLog:s=>process.stderr.write(s),initialize:async rpc=>{await rpc.request('initialize',{protocol:1,agents,providers,bindings:store.bindings().map(({conversationId:_,...b})=>b)});},onReady:async()=>{},onError:e=>console.error(e)});
const runtime={get available(){return supervisor.available;},onNotification:(f:any)=>supervisor.onNotification(f),request:async(method:string,params:any)=>{
 if(armed&&method==='session.submit'&&(mode==='before-submit'||mode==='after-receipt')){if(mode==='before-submit')return freeze(mode,{method,params});return new Promise<never>(()=>{});}
 const result=await supervisor.request(method,params);
 if(armed&&method==='session.submit'&&mode.startsWith('after-submit'))return freeze(mode,{method,params,result});
 return result;
}};
const connection=new WebRelayConnection({url:config.im_service.url,requiredCapabilities:['relay_request_ids','work_sync_http'],credentials:()=>({accessToken:config.im_service.token,registration:{node_id:config.node.node_id,agents:agents.map(a=>a.agentId),agent_work_modes:Object.fromEntries(agents.map(a=>[a.agentId,a.mode]))}}),onFrame:async frame=>{if(frame.type==='relay.message'&&frame.payload.agent_id==='e2e-fixture'){armed=String((frame.payload.message as any).content).includes('CRASH630');await product.receive(frame.payload as any);}},onError:e=>console.error(e)});
const relay={get ready(){return connection.ready;},request:async(type:string,payload:any)=>{const result=await connection.request(type,payload);if(armed&&((type==='node.delivery_receipt'&&mode==='after-receipt')||(type==='agent.message'&&mode==='after-publication')))return freeze(mode,{type,payload,result});return result;}};
product=new GlobalAgent({nodeId:config.node.node_id,ownerId:config.node.user_id,agents,store,inbox,runtime,relay,image:async()=>{throw Error('No image in crash fixture');},onError:e=>console.error(e),authorityEpoch:()=>connection.registration?.node_epoch});
supervisor.handle('product.call',call=>product.call(call as any));
await supervisor.start();await connection.start();await product.recover();writeFileSync('.e2e-crash-host.json',JSON.stringify({host_pid:process.pid,runtime_pid:supervisor.process!.pid,mode,ready:true}));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,async()=>{await product.stop();await connection.stop();await supervisor.shutdown();inbox.close();store.close();process.exit();});
setInterval(()=>{},1000);
