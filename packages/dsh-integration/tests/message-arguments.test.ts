import {expect, it} from 'vitest';
import {normalizeMessageArguments} from '../src/message-arguments.js';

it.each([undefined, '', 'Supplementary text'])('normalizes public UI delivery with optional text %j', text => {
  const interactive={source:'root = Col([Text("必要说明")])'};
  expect(normalizeMessageArguments({target:'current',...(text===undefined?{}:{text}),interactive})).toEqual({
    target:'current',text:text??'',interactive:{...interactive,format:'openui',catalog_version:'nano-iui-1'},
  });
});
it('requires public content and does not admit malformed text or internal addressing', () => {
  expect(()=>normalizeMessageArguments({target:'current'})).toThrow();
  expect(()=>normalizeMessageArguments({target:'current',text:null,interactive:{source:'root = Col([])'}})).toThrow();
  expect(()=>normalizeMessageArguments({agent_id:'child',message:'Report'})).toThrow();
});

it('admits local screenshots only in self-authored sends and keeps receipt checks read-only', () => {
  const local = {target:'current', text:'Comparison', local_images:['/tmp/before.png']};
  expect(normalizeMessageArguments(local,true)).toEqual(local);
  expect(()=>normalizeMessageArguments(local)).toThrow();
  expect(()=>normalizeMessageArguments({...local,local_images:['../outside.png']},true)).toThrow();
  expect(()=>normalizeMessageArguments({...local,local_images:Array(5).fill('/tmp/before.png'),attachments:[{url:'/attached'}]},true)).toThrow();
  expect(normalizeMessageArguments({target:'current',receipt_of:'original'},true)).toEqual({target:'current',receipt_of:'original'});
  expect(()=>normalizeMessageArguments({...local,receipt_of:'original'},true)).toThrow();
});
