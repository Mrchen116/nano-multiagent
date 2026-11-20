import { cliWorkerRuntimes } from '@nano/product-contracts/worker-runtimes';
import { expect, it } from 'vitest';
import type { CliWorkerOptions } from '../src/local-workers/drivers.js';
import { details, fakeCli, onEnd, onReport, turnTotals } from './helpers/local-worker-cli.js';

// Each fixture speaks the CLI's native protocol. The same assertions run through the real driver.
const protocolPeers = {
  codex: `
    const answer = result => emit({id:m.id, result});
    const notify = (method, params) => emit({method, params:{threadId:'saved', ...params}});
    if(m.method==='initialize') answer({});
    if(m.method==='thread/resume' && m.params.threadId==='saved') answer({thread:{id:'saved'}});
    if(m.method==='turn/start' && m.params.threadId==='saved') {
      const id=m.params.input[0].text;
      answer({turn:{id}});
      if(id==='inspect') {
        emit({id:761,method:'item/commandExecution/requestApproval',params:{threadId:'saved',turnId:id,itemId:'other',command:'restricted-command'}});
        const item={type:'commandExecution',id:'read',command:'pwd',status:'completed',aggregatedOutput:'fixture-directory',exitCode:0};
        notify('item/completed',{turnId:id,item});
        notify('thread/tokenUsage/updated',{turnId:id,tokenUsage:{total:{totalTokens:8},last:{totalTokens:8}}});
        const message={type:'agentMessage',id:'answer',phase:'final_answer',text:'inspection complete'};
        notify('item/completed',{turnId:id,item:message});
        notify('turn/completed',{turn:{id,status:'completed',items:[message]}});
      }
    }
    if(m.method==='turn/interrupt' && m.params.turnId==='follow up') {
      answer({});notify('turn/completed',{turn:{id:m.params.turnId,status:'interrupted'}});
    }
  `,
  claude: `
    if(m.type==='control_request') emit({type:'control_response',response:{subtype:'success',request_id:m.request_id}});
    if(m.type==='user' && m.session_id==='saved' && process.argv.includes('--resume')) {
      emit({type:'user',isReplay:true,uuid:m.uuid});
      if(m.message.content==='inspect') {
        emit({type:'control_request',request_id:'approve',request:{subtype:'can_use_tool',tool_use_id:'other',tool_name:'Bash',input:{command:'restricted-command'}}});
        emit({type:'assistant',uuid:'call',message:{content:[{type:'tool_use',id:'read',name:'Bash',input:{command:'pwd'}}]}});
        emit({type:'user',message:{content:[{type:'tool_result',tool_use_id:'read',content:'fixture-directory'}]}});
        emit({type:'result',session_id:'saved',uuid:'answer',subtype:'success',result:'inspection complete',usage:{input_tokens:6,output_tokens:2}});
      }
    }
  `,
} satisfies Record<CliWorkerOptions['runtime'], string>;

it.each(cliWorkerRuntimes)('%s resumes the assigned session, records input and usage, and stops a follow-up', async (runtime) => {
  const peer = protocolPeers[runtime];
  expect(peer, `Missing native protocol fixture for ${runtime}`).toBeTypeOf('string');
  const worker = await fakeCli(runtime, peer, 'saved');
  expect(worker.sessionId).toBe('saved');
  await worker.send('inspect');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  expect(onEnd.mock.calls[0]).toEqual([expect.any(String), 'completed', 'inspection complete']);
  expect(onReport.mock.calls).toEqual([[expect.any(String), expect.stringContaining('restricted-command')]]);
  const facts = details().map(({fact}) => fact);
  expect(facts.find(fact => fact.type === 'tool_start')?.payload).toMatchObject({call_id:'read', arguments:{command:'pwd'}});
  const result = facts.find(fact => fact.type === 'tool_end');
  expect(result?.payload).toMatchObject({call_id:'read', is_error:false});
  expect(JSON.stringify(result?.payload.presentation)).toContain('fixture-directory');
  await worker.send('follow up');
  await worker.stop();
  expect(onEnd.mock.calls.map(([, state]) => state)).toEqual(['completed', 'interrupted']);
  const inputs = details().flatMap(({fact, turnId}) =>
    fact.type === 'message' && fact.payload.role === 'user' ? [{turnId, text:fact.payload.text}] : []);
  expect(inputs.map(input => input.text)).toEqual(['inspect', 'follow up']);
  expect(inputs[1]!.turnId).not.toBe(inputs[0]!.turnId);
  expect(turnTotals()).toEqual([[inputs[0]!.turnId, 8], [inputs[1]!.turnId, null]]);
});
