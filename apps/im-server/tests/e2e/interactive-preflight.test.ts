import {expect, it} from 'vitest';
import {start, bind} from './helpers.js';

it('rejects invalid initial UI props with upstream diagnostics before publication and accepts a corrected send', async () => {
  const f=await start(), g=await bind(f);
  const created=await f.http('POST','/im/v1/conversations',{title:'UI preflight',type:'direct',participants:[{type:'agent',id:'assistant'}]},f.tokens.alice);
  expect(created.status).toBe(201);
  const id=created.body.id;
  const send=(key:string,source:string)=>g.frames.send('agent.message',{node_id:g.node,to:`conversation:${id}`,text:'',
    from_session_id:`assistant|tool_call:${key}`,interactive:{format:'openui',catalog_version:'nano-iui-1',source}});
  const invalid=await send('bad','$size = "huge"\nheading = Title("Hello", $size)\nroot = Col([heading])');
  expect(invalid).toMatchObject({type:'error',payload:{detail:{code:'invalid_interactive_source',errors:[expect.objectContaining({source:'parser',code:'type-mismatch',statementId:'heading',component:'Title',path:'/size'})]}}});
  const history=()=>f.http('GET',`/im/v1/conversations/${id}/messages?limit=100`,undefined,f.tokens.alice);
  expect((await history()).body.items).toHaveLength(0);
  expect((await send('fixed','root = Title("Hello", "md")')).type).not.toBe('error');
  expect((await history()).body.items).toHaveLength(1);
},15000);

it('recovers scoped screenshot uploads and persists ordered card attachments for group readers', async () => {
  const f = await start(), g = await bind(f);
  const created = await f.http('POST', '/im/v1/conversations', {
    title:'Screenshot delivery', type:'group', visibility:'private',
    participants:[{type:'agent', id:'assistant'}, {type:'user', id:'bob'}],
  }, f.tokens.alice);
  expect(created.status).toBe(201);
  const id = created.body.id;
  const endpoint = `${f.base}/im/v1/conversations/${id}/images`;
  const query = 'agent_id=assistant&lifecycle_revision=1';
  const authorization = `Bearer ${g.token}`;
  const sharp = (await import('sharp')).default;
  const png = await sharp({create:{width:16,height:12,channels:3,background:'red'}}).png().toBuffer();
  const upload = (key: string, bytes: Uint8Array<ArrayBuffer>) => fetch(`${endpoint}?${query}&screenshot=1&file_name=demo.png`, {
    method:'POST', headers:{authorization,'content-type':'image/png','idempotency-key':key}, body:bytes,
  });
  const broken = await upload('broken', new Uint8Array(png.subarray(0, 16)));
  expect(broken.status, await broken.text()).toBe(422);
  const saved = await upload('operation:0', new Uint8Array(png));
  expect(saved.status).toBe(201);
  const image = await saved.json() as {url:string};
  const receipt = await fetch(`${endpoint}?${query}&upload_key=operation%3A0`, {headers:{authorization}});
  expect(receipt.status).toBe(200);
  expect(await receipt.json()).toEqual({attachment:image});
  const send = (attachments: {url:string}[]) => g.frames.send('agent.message', {
    node_id:g.node, to:`conversation:${id}`, from_session_id:'assistant|tool_call:operation', text:'Screenshot',
    attachments, interactive:{format:'openui',catalog_version:'nano-iui-1',source:'root = Col([AttachmentImage(1, "Demo")])'},
  });
  expect((await send([image])).type).toBe('ack');
  expect((await send([image])).type).toBe('ack');
  expect((await send([])).type).toBe('error');
  const history = await f.http('GET', `/im/v1/conversations/${id}/messages?limit=100`, undefined, f.tokens.bob);
  expect(history.body.items).toHaveLength(1);
  expect(JSON.stringify(history.body.items)).toContain(image.url);
  const read = (token:string) => fetch(`${f.base}${image.url}`, {headers:{authorization:`Bearer ${token}`}});
  const denied = await read(f.tokens.outsider);
  expect(denied.status).toBe(404);
  await denied.text();
  const allowed = await read(f.tokens.bob);
  expect(Buffer.from(await allowed.arrayBuffer())).toEqual(png);
}, 15000);
