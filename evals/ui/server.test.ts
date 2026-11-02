import {it,expect} from 'vitest';import {catalog} from './catalog.js';import {startViewer} from './server.js';
it('keeps private archive APIs behind a local capability and serves registered reference images',async()=>{
 let stopped=false;const calls:unknown[]=[];
 const viewer=await startViewer({suites:await catalog(),archive:{sessions:[],async request(input){calls.push(input);return {read:true}},async close(){stopped=true}}});
 try{
  const origin=new URL(viewer.url).origin;const token=new URL(viewer.url).pathname.split('/')[1];
  expect((await fetch(origin+'/api/catalog')).status).toBe(403);
  expect((await fetch(viewer.url)).status).toBe(200);
  const h={'x-viewer-token':token};expect((await(await fetch(origin+'/api/catalog',{headers:h})).json() as any).suites).toHaveLength(2);
  expect((await fetch(origin+'/api/reference?name=hotel-reference.jpg',{headers:h})).headers.get('content-type')).toBe('image/jpeg');
  expect((await fetch(origin+'/api/reference?name=../private',{headers:h})).status).toBe(400);
  expect((await fetch(origin+'/api/trajectory',{method:'POST',headers:h,body:JSON.stringify({type:'prepare',sessionId:'known'})})).ok).toBe(true);expect(calls).toEqual([{type:'prepare',sessionId:'known'}]);
 }finally{await viewer.close()}
 expect(stopped).toBe(true);
});
