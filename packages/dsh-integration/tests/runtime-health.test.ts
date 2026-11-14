import {afterEach, expect, it, vi} from 'vitest';
import {RuntimeHealth} from '../src/runtime-health.js';
afterEach(() => vi.useRealTimers());
it('bounds a stalled filesystem to one probe and one failure', async () => {
  vi.useFakeTimers(); const probe=vi.fn(()=>new Promise(()=>{})), fail=vi.fn();
  const health=new RuntimeHealth(probe,fail,{tickMs:10,timeoutMs:100});
  await vi.advanceTimersByTimeAsync(120);
  expect(probe).toHaveBeenCalledTimes(1);expect(fail).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1000);expect(fail).toHaveBeenCalledTimes(1);health.close();
});
it('grants an awake deadline after clock jumps without adding probes', async () => {
  vi.useFakeTimers();const probe=vi.fn(()=>new Promise(()=>{})),fail=vi.fn();
  const health=new RuntimeHealth(probe,fail,{tickMs:10,timeoutMs:100});
  await vi.advanceTimersByTimeAsync(10);vi.setSystemTime(Date.now()+3600000);
  await vi.advanceTimersByTimeAsync(90);expect(fail).not.toHaveBeenCalled();expect(probe).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(30);expect(fail).toHaveBeenCalledTimes(1);health.close();
});
it('does not confuse long model work with FS failure and stops on close', async () => {
  vi.useFakeTimers();const probe=vi.fn(async()=>({healthy:true})),fail=vi.fn();
  const health=new RuntimeHealth(probe,fail,{tickMs:10,intervalMs:30,timeoutMs:100});
  await vi.advanceTimersByTimeAsync(1000);expect(probe.mock.calls.length).toBeGreaterThan(20);expect(fail).not.toHaveBeenCalled();
  health.close();const count=probe.mock.calls.length;await vi.advanceTimersByTimeAsync(1000);expect(probe).toHaveBeenCalledTimes(count);
});

it.skipIf(process.platform==='win32')('reaps tool children that use a separate process group', async()=>{
  const {spawn}=await import('node:child_process');
  const {terminateRuntimeTree}=await import('../src/runtime-health.js');
  const child=spawn(process.execPath,['-e',`const {spawn}=require('node:child_process');const tool=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{detached:true,stdio:'ignore'});console.log(tool.pid);setInterval(()=>{},1000);`],{detached:true,stdio:['ignore','pipe','ignore']});
  const exited=new Promise(resolve=>child.once('exit',resolve));
  const tool=await new Promise<number>(resolve=>child.stdout!.once('data',data=>resolve(Number(String(data).trim()))));
  try {
    await terminateRuntimeTree(child.pid!);await exited;
    await expect.poll(()=>{try{process.kill(tool,0);return false;}catch(error){return(error as NodeJS.ErrnoException).code==='ESRCH';}}).toBe(true);
  }finally{for(const pid of [tool,child.pid!])try{process.kill(pid,'SIGKILL');}catch{}}
});
