import {afterEach, expect, it, vi} from 'vitest';
import {NodeRpc} from '../src/node-rpc.js';

afterEach(() => vi.useRealTimers());
function fixture() {
  const connection = {};
  const sent: {type:string; payload:object}[] = [];
  const transport = {current: () => connection, updating: () => false, send: (_node:string, frame:{type:string;payload:object}) => {sent.push(frame); return true;}};
  const rpc = new NodeRpc(transport);
  return {connection, sent, transport, rpc};
}

it('correlates by command and connection and preserves receipt metadata', async () => {
  const {rpc, connection, sent} = fixture();
  const result = rpc.request('node', 'agent.config.apply', {request_id:'request',operation_id:'operation',candidate_fingerprint:'fingerprint',expected_previous_fingerprint:'previous',agent:{agent_id:'agent'}});
  expect(sent[0]).toMatchObject({type:'agent.config.apply',payload:{request_id:'request',operation_id:'operation'}});
  const receipt = {request_id:'request',operation_id:'operation',candidate_fingerprint:'fingerprint',status:'applied',agent:{agent_id:'agent',custom_prompt:'职责'},extension:{future:true}};
  expect(rpc.accept({}, 'agent.config.apply.result', receipt)).toBe(false);
  expect(rpc.accept(connection, 'agent.created', receipt)).toBe(false);
  expect(rpc.accept(connection, 'agent.config.apply.result', receipt)).toBe(true);
  expect(await result).toBe(receipt);
  expect(rpc.accept(connection, 'agent.config.apply.result', receipt)).toBe(false);
  rpc.close();
});

it('rejects malformed consumed fields but accepts old partial configuration snapshots', async () => {
  const {rpc, connection} = fixture();
  const invalid = rpc.request('node','agent.config.apply',{request_id:'bad',operation_id:'operation',candidate_fingerprint:'f',expected_previous_fingerprint:null,agent:{agent_id:'agent'}});
  const failed = expect(invalid).rejects.toMatchObject({statusCode:502});
  expect(rpc.accept(connection,'agent.config.apply.result',{request_id:'bad',status:'applied',agent:{skills:42}})).toBe(true);
  await failed;
  const old = rpc.request('node','agent.config.get',{request_id:'old',agent_id:'agent'});
  rpc.accept(connection,'agent.config',{request_id:'old',agent:{skills:['old-skill']}});
  expect(await old).toMatchObject({agent:{skills:['old-skill']}});
  rpc.close();
});

it('preserves offline, update, timeout and shutdown outcomes and ignores late replies', async () => {
  vi.useFakeTimers();
  const {rpc, transport, connection} = fixture();
  transport.updating = () => true;
  await expect(rpc.request('node','agent.config.get',{agent_id:'agent'})).rejects.toMatchObject({statusCode:409});
  transport.updating = () => false;
  transport.send = () => false;
  await expect(rpc.request('node','agent.config.get',{agent_id:'agent'})).rejects.toMatchObject({statusCode:503});
  transport.send = () => true;
  const timed = expect(rpc.request('node','agent.config.get',{request_id:'timed',agent_id:'agent'})).rejects.toMatchObject({statusCode:504});
  await vi.advanceTimersByTimeAsync(10000);
  await timed;
  expect(rpc.accept(connection,'agent.config',{request_id:'timed',agent:{}})).toBe(false);
  const stopped = expect(rpc.request('node','agent.config.get',{agent_id:'agent'})).rejects.toThrow('server stopped');
  rpc.close();
  await stopped;
  expect(vi.getTimerCount()).toBe(0);
});

it('bounds and cancels only inspections, and consumes only inspection late replies',async()=>{
  vi.useFakeTimers(); const {rpc,connection,sent}=fixture();
  const failed=expect(rpc.request('node','agent.capabilities.resolve',{request_id:'catalog',agent_id:'agent'})).rejects.toMatchObject({statusCode:504});
  expect(sent[0]).toMatchObject({payload:{deadline_at:Date.now()+9000}});
  await vi.advanceTimersByTimeAsync(9000); await failed;
  expect(sent[1]).toEqual({type:'node.request.cancel',payload:{target_request_id:'catalog'}});
  expect(rpc.accept(connection,'agent.capabilities',{request_id:'catalog',capabilities:{}})).toBe(true);
  expect(rpc.accept(connection,'agent.config.apply.result',{request_id:'old'})).toBe(false);
  const controller=new AbortController();
  const aborted=expect(rpc.request('node','node.capabilities.resolve',{request_id:'aborted'},controller.signal)).rejects.toMatchObject({statusCode:503});
  controller.abort(); await aborted;
  expect(sent.at(-1)).toEqual({type:'node.request.cancel',payload:{target_request_id:'aborted'}});
  rpc.close(); expect(vi.getTimerCount()).toBe(0);
});

it('never sends cancellation to a replacement connection or cancels durable mutation',async()=>{
  const {rpc,transport,sent}=fixture(),controller=new AbortController();
  const canceled=expect(rpc.request('node','node.capabilities.resolve',{},controller.signal)).rejects.toThrow();
  transport.current=()=>({});controller.abort();await canceled;expect(sent).toHaveLength(1);
  const durable=rpc.request('node','agent.config.get',{agent_id:'agent'},controller.signal);
  const stopped=expect(durable).rejects.toThrow('server stopped');rpc.close();await stopped;
  expect(sent.every(frame=>frame.type!=='node.request.cancel')).toBe(true);
});

it('maps inspection error codes and cancels active inspections on disconnect and shutdown',async()=>{
  const {rpc,connection,sent}=fixture();
  const failed=expect(rpc.request('node','node.capabilities.resolve',{request_id:'failed'})).rejects.toMatchObject({statusCode:504});
  rpc.accept(connection,'node.capabilities',{request_id:'failed',error_code:'catalog_timeout'});await failed;
  const disconnected=expect(rpc.request('node','node.capabilities.resolve',{request_id:'gone'})).rejects.toMatchObject({statusCode:503});
  rpc.disconnect(connection);await disconnected;
  expect(sent.at(-1)).toEqual({type:'node.request.cancel',payload:{target_request_id:'gone'}});
  const stopped=expect(rpc.request('node','node.capabilities.resolve',{request_id:'closed'})).rejects.toThrow('server stopped');
  rpc.close();await stopped;
  expect(sent.at(-1)).toEqual({type:'node.request.cancel',payload:{target_request_id:'closed'}});
});
