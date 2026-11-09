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
