import {expect, it} from 'vitest';
import {apply} from '../src/context-order.js';

it('places only native runtime/catalog updates before this step input without changing messages', async () => {
  let listener: any;
  apply({on: (event: string, callback: unknown, options: unknown) => {
    expect(event).toBe('agent/pre-step'); expect(options).toEqual({prepend: true}); listener = callback;
  }} as any);
  const message = (id: string, kind: string) => Object.freeze({id, source: Object.freeze({kind}), content: Object.freeze([{type:'text',text:id}])});
  const wake = message('wake','nano-system'), skill = message('skill','skill-catalog');
  const runtime = message('runtime','runtime-context'), invocation = message('invoked','skill-invocation');
  const another = message('later-input','user'), update = message('catalog-clear','skill-catalog');
  const original = [wake,skill,runtime,invocation,another,update];
  const decision = {kind:'enter',messages:original,startsRequestSeries:true};
  const result = await listener({}, async () => decision);
  expect(result).toEqual({...decision,messages:[runtime,skill,update,wake,invocation,another]});
  expect(decision.messages).toBe(original);
  for (const entry of result.messages) expect(original).toContain(entry);
  expect(await listener({}, async () => ({kind:'reject'}))).toEqual({kind:'reject'});
  const unchanged = {kind:'enter',messages:[invocation,another]};
  expect(await listener({}, async () => unchanged)).toBe(unchanged);
});
