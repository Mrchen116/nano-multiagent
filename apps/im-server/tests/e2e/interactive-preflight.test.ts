import {expect, it} from 'vitest';
import {start, bind} from './helpers.js';

it('rejects invalid initial UI props with upstream diagnostics before publication and accepts a corrected send', async () => {
  const f=await start(), g=await bind(f);
  const created=await f.http('POST','/im/v1/conversations',{title:'UI preflight',type:'direct',participants:[{type:'agent',id:'assistant'}]},f.tokens.alice);
  expect(created.status).toBe(201);
  const id=created.body.id;
  const send=(key:string,source:string)=>g.frames.send('agent.message',{node_id:g.node,to:`conversation:${id}`,text:'UI summary',
    from_session_id:`assistant|tool_call:${key}`,interactive:{format:'openui',catalog_version:'nano-iui-1',source}});
  const invalid=await send('bad','$size = "huge"\nheading = Title("Hello", $size)\nroot = Col([heading])');
  expect(invalid).toMatchObject({type:'error',payload:{detail:{code:'invalid_interactive_source',errors:[expect.objectContaining({source:'parser',code:'type-mismatch',statementId:'heading',component:'Title',path:'/size'})]}}});
  const history=()=>f.http('GET',`/im/v1/conversations/${id}/messages?limit=100`,undefined,f.tokens.alice);
  expect((await history()).body.items).toHaveLength(0);
  expect((await send('fixed','root = Title("Hello", "md")')).type).not.toBe('error');
  expect((await history()).body.items).toHaveLength(1);
},15000);
