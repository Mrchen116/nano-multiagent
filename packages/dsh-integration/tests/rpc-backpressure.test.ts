import { PassThrough, Writable } from 'node:stream';
import { expect, it } from 'vitest';
import { RpcPeer } from '../src/rpc.js';

const frame=(id:number,method:string)=>JSON.stringify({jsonrpc:'2.0',id,method})+'\n';

it('does not produce or serialize a second Work page before drain; controls dispatch independently', async () => {
  const input=new PassThrough();
  const frames:unknown[]=[];
  let release: (()=>void)|undefined;
  const output=new Writable({highWaterMark:16,write(chunk,_encoding,callback){
    frames.push(JSON.parse(String(chunk)));release=callback;
  }});
  const peer=new RpcPeer(input,output);
  let generated=0,controls=0,rootPages=0,serialized=0;
  peer.handle('work',()=>{generated++;return {page:'x'.repeat(1024)};},{pull:'children'});
  peer.handle('control',()=>{controls++;return 'cancelled';});
  peer.handle('root',()=>{rootPages++;return {root:true};},{pull:'root'});
  try {
    input.write(frame(1,'work')+frame(2,'work'));
    await expect.poll(()=>output.writableNeedDrain).toBe(true);
    const before=output.writableLength;
    peer.notify('hint',{toJSON(){serialized++;return {changed:true};}});
    input.write(frame(3,'control')+frame(4,'root'));
    await expect.poll(()=>controls).toBe(1);
    await expect.poll(()=>rootPages).toBe(1);
    expect(generated).toBe(1);
    expect(serialized).toBe(0);
    expect(output.writableLength).toBe(before);
    release!();
    await expect.poll(()=>frames.length).toBe(2);
    expect(serialized).toBe(1);
    release!();
    await expect.poll(()=>frames.length).toBe(3);
    release!();
    await expect.poll(()=>frames.length).toBe(4);
    release!();
    await expect.poll(()=>frames.length).toBe(5);
    expect(frames.map(value=>(value as {id?:number}).id)).toEqual([1,undefined,3,4,2]);
    release!();
  } finally {peer.close();input.destroy();output.destroy();}
});

it('fails outstanding calls and releases a waiting page producer on output error',async()=>{
  const input=new PassThrough(),output=new Writable({highWaterMark:1,write(){}});
  const failures:Error[]=[];
  const peer=new RpcPeer(input,output,error=>failures.push(error));
  let generated=0;
  peer.handle('work',()=>++generated,{pull:'children'});
  try {
    const pending=peer.request('reverse',{});
    const failed=expect(pending).rejects.toThrow('pipe lost');
    input.write(frame(1,'work')+frame(2,'work'));
    await expect.poll(()=>generated).toBe(1);
    output.destroy(new Error('pipe lost'));
    await failed;
    expect(failures).toHaveLength(1);
    expect(generated).toBe(1);
  } finally {peer.close();input.destroy();output.destroy();}
});
