import {afterEach,expect,it,vi} from 'vitest';

afterEach(()=>{document.getElementById('nano-page-bootstrap')?.remove();vi.useRealTimers();});

it('consumes server page reads only once and only for the authenticated document token',async()=>{
  vi.resetModules();
  const element=document.createElement('script');
  element.id='nano-page-bootstrap';element.type='application/json';
  element.textContent=JSON.stringify({session:{access_token:'document-token',user:{id:'user-a'}},data:{'/saved':{value:'private'}}});
  document.body.append(element);
  const {readPageBootstrap,takePageRead}=await import('./page-bootstrap');
  expect(readPageBootstrap()?.session.user.id).toBe('user-a');
  expect(document.getElementById('nano-page-bootstrap')).toBeNull();
  expect(takePageRead('/saved','other-account-token')).toBeUndefined();
  expect(await takePageRead('/saved','document-token')!.json()).toEqual({value:'private'});
  expect(takePageRead('/saved','document-token')).toBeUndefined();
});

it('expires unconsumed document reads instead of serving them during a later revisit',async()=>{
  vi.resetModules();vi.useFakeTimers();
  const element=document.createElement('script');element.id='nano-page-bootstrap';element.type='application/json';
  element.textContent=JSON.stringify({session:{access_token:'token',user:{id:'user-a'}},data:{'/saved':{}}});
  document.body.append(element);
  const {readPageBootstrap,takePageRead}=await import('./page-bootstrap');
  readPageBootstrap();vi.advanceTimersByTime(5001);
  expect(takePageRead('/saved','token')).toBeUndefined();
});
