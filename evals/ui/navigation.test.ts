import {readFile} from 'node:fs/promises';
import {runInContext} from 'node:vm';
import {JSDOM} from 'jsdom';
import {expect,it,vi} from 'vitest';

it('keeps the latest case visible when an old native observer closes late',async()=>{
  const html=await readFile(new URL('./index.html',import.meta.url),'utf8');
  const source=(await readFile(new URL('./app.js',import.meta.url),'utf8')).replace("import {mountNative} from './native.js';",'');
  const dom=new JSDOM(html,{url:'http://localhost/token/',runScripts:'outside-only'});
  let finishClose!:()=>void;
  const closing=new Promise<void>(done=>{finishClose=done});
  const mountNative=vi.fn(async()=>async()=>closing);
  Object.assign(dom.getInternalVMContext(),{mountNative,fetch:async()=>({ok:true,json:async()=>({suites:[{title:'Memory',cases:[{id:'memory',title:'Memory case',notice:'archived',stages:[{kind:'native',title:'S',sessionId:'s'},{kind:'native',title:'T',sessionId:'t'}]},{id:'hotel',title:'Hotel',notice:'unrun',prompt:'Fixed hotel input',stages:[]}]}]})})});
  const settle=()=>new Promise(done=>setImmediate(done));
  const click=(label:string)=>{const button=[...dom.window.document.querySelectorAll('button')].find(b=>b.textContent===label)!;button.click()};
  try{
    await runInContext('(async()=>{'+source+'})()',dom.getInternalVMContext());
    click('S');await settle();expect(mountNative).toHaveBeenCalledTimes(1);
    click('T');await settle();click('Hotel');await settle();
    finishClose();await settle();
    expect(dom.window.document.querySelector('#title')!.textContent).toBe('Hotel');
    expect(dom.window.document.querySelector('#body')!.textContent).toContain('Fixed hotel input');
    expect(mountNative).toHaveBeenCalledTimes(1);
  }finally{dom.window.close()}
});
