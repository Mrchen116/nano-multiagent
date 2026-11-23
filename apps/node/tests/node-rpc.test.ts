import {expect,it,vi} from 'vitest';
import {decodeNodeInput,decodeNodeResult,type NodeHandlers} from '@nano/product-contracts/node-rpc';
import {dispatchNodeCommand} from '../src/node-rpc.js';

// The spy records all attempted business operations, including dispatch under the wrong key.
function fixture() {
  const handle = vi.fn(), send = vi.fn(async()=>{});
  const handlers:NodeHandlers = new Proxy({} as NodeHandlers,{get:()=>handle});
  return {handle,send,handlers};
}

it('rejects malformed durable inputs without confirming or performing a mutation',async()=>{
  const {handle,send,handlers} = fixture();
  for (const [command,input] of [
    ['agent.config.apply',{operation_id:'op',candidate_fingerprint:'f',expected_previous_fingerprint:'previous',agent:{agent_id:'a',features:{x:1}}}],
    ['node.cron.delete.request',{agent_id:'a',job_id:'job',operation_id:'op'}],
    ['node.cron.jobs.request',{}],
  ] as const) {
    await expect(dispatchNodeCommand(command,{...input,request_id:'request'},handlers,'node',send)).rejects.toThrow(command);
  }
  expect(handle).not.toHaveBeenCalled();
  expect(send).not.toHaveBeenCalled();
});

it('uses only command-specific failures and requires the original request ID',async()=>{
  const {handle,send,handlers} = fixture();
  await dispatchNodeCommand('node.plugins.request',{request_id:'p',action:'set_bundle',agent_id:'a',target:'t'},handlers,'local',send);
  expect(send).toHaveBeenCalledWith('node.plugins',{request_id:'p',node_id:'local',error:'Invalid plugin command'});
  await dispatchNodeCommand('node.setup.request',{request_id:'s',action:'remove'},handlers,'local',send);
  expect(send).toHaveBeenCalledWith('node.setup',{request_id:'s',node_id:'local',error_code:'setup_invalid',message:'Model setup is unavailable'});
  await expect(dispatchNodeCommand('session.fork.request',{},handlers,'local',send)).rejects.toThrow('request_id');
  expect(send).toHaveBeenCalledTimes(2);
  expect(handle).not.toHaveBeenCalled();
});

it('overrides result-supplied correlation metadata and waits for the original relay ACK',async()=>{
  const {handle,send,handlers} = fixture();
  handle.mockReturnValue({deleted:true,request_id:'foreign',node_id:'foreign'});
  const ack = Promise.withResolvers<void>();
  send.mockReturnValue(ack.promise);
  const input = {agent_id:'a',job_id:'j',operation_id:'op',actor_user_id:'u'};
  let done = false;
  const response = dispatchNodeCommand('node.cron.delete.request',{...input,request_id:'r'},handlers,'local',send).then(()=>{done=true;});
  await vi.waitFor(()=>expect(send).toHaveBeenCalledWith('node.cron.delete',{deleted:true,request_id:'r',node_id:'local'}));
  expect(handle.mock.calls[0]?.[0]).toEqual(input);
  expect(done).toBe(false);
  ack.resolve(); await response;
  expect(done).toBe(true);
});

it('checks consumed setup fields without echoing credentials or bodies in schema errors',()=>{
  expect(()=>decodeNodeInput('node.setup.request',{action:'save',api_key:'secret sample',models:[{id:42}]}))
    .toThrow('Invalid node.setup.request field models.0.id');
  expect(()=>decodeNodeResult('node.setup.request',{revision:'1',services:[{provider:'p',models:'secret sample'}]}))
    .toThrow('Invalid node.setup.request field services.0.models');
  expect(()=>decodeNodeResult('node.setup.request',{revision:'1',operation:{id:'o',state:'secret sample'}}))
    .toThrow('Invalid node.setup.request field operation.state');
  const rejected = {revision:'1',error:{code:'in_use',message:'Dependency is in use',dependencies:[{agent_id:'a',display_name:'A'}]}};
  expect(decodeNodeResult('node.setup.request',rejected)).toBe(rejected);
});

it('rejects malformed plans and accepts the old state fallback and partial configuration unchanged',()=>{
  for (const value of [{},{jobs:'unavailable'},{jobs:[null]}]) expect(()=>decodeNodeResult('node.cron.jobs.request',value)).toThrow();
  expect(decodeNodeResult('task.execution.state',{})).toEqual({});
  expect(decodeNodeResult('task.execution.state',{state:'legacy'})).toEqual({state:'legacy'});
  const receipt = {agent:{display_name:null,provider_extension:{extra:1}},operation_id:'o',extension:'kept'};
  expect(decodeNodeResult('agent.config.apply',receipt)).toBe(receipt);
});
