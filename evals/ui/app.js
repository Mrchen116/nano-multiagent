import {mountNative} from './native.js';
import {mountDag} from './dag.js';
const token=location.pathname.split('/')[1];
async function api(path,body){const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'x-viewer-token':token,...(body?{'content-type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});const value=await response.json();if(!response.ok)throw new Error(value.error||'读取失败');return value}
const {suites}=await api('catalog');let release,referenceUrl,generation=0;
const nav=document.querySelector('#cases'),body=document.querySelector('#body'),viewer=document.querySelector('#viewer'),status=document.querySelector('#status');
const text=(tag,value)=>{const node=document.createElement(tag);node.textContent=value;return node};
for(const suite of suites){
 nav.append(text('h2',suite.title));
 if(!suite.cases.length)nav.append(text('small','未挂接本地归档'));
 let experiment;
 for(const c of suite.cases){
  if(c.experiment?.id!==experiment){experiment=c.experiment?.id;if(experiment)nav.append(text('small',c.experiment.title))}
  const button=document.createElement('button');button.dataset.case=c.id;button.textContent=c.title;button.onclick=()=>show(c);nav.append(button);
  const stages=c.stages.filter(s=>s.kind==='native');if(stages.length){const group=document.createElement('details');group.append(text('summary',`阶段与批次（${stages.length}）`));for(const s of stages){const b=document.createElement('button');b.className='stage';b.textContent=s.title;b.onclick=()=>stage(c,s);group.append(b)}nav.append(group)}
 }
}
async function clear(){const close=release;release=null;viewer.replaceChildren();viewer.style.display='none';body.style.display='block';body.replaceChildren();if(referenceUrl){URL.revokeObjectURL(referenceUrl);referenceUrl=null}await close?.()}
async function show(c){
 const gen=++generation;await clear();if(gen!==generation)return;document.querySelector('#title').textContent=c.title;document.querySelector('#identity').textContent=(c.experiment?.title?c.experiment.title+' / ':'')+c.id;document.querySelector('#notice').textContent=c.notice;status.textContent=c.stages.length?'材料与证据':'未运行';
 for(const b of nav.querySelectorAll('[data-case]'))b.classList.toggle('active',b.dataset.case===c.id);
 history.replaceState(null,'','#'+c.id);
 if(c.context){body.append(text('h3','上下文起点'),text('p',c.context))}
 if(c.graph){mountDag(body,c);return}
 if(c.prompt){body.append(text('h3','固定输入'),text('pre',c.prompt))}
 if(c.attachments?.length||c.workspaceFiles?.length){body.append(text('h3',c.workspaceFiles?.length?'工作区文件（运行前放入 Agent 工作区）':'输入附件'));for(const name of [...(c.attachments??[]),...(c.workspaceFiles??[])]){const button=text('button','下载 '+name);button.onclick=async()=>{try{const response=await fetch('/api/attachment?name='+encodeURIComponent(name),{headers:{'x-viewer-token':token}});if(!response.ok)throw new Error('附件读取失败');const url=URL.createObjectURL(await response.blob());const link=text('a',name);link.href=url;link.download=name;body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(error){button.textContent=error.message}};body.append(button)}}
 if(c.photoUrls?.length){body.append(text('h3','演示照片素材'));const list=document.createElement('ul');c.photoUrls.forEach(url=>list.append(text('li',url)));body.append(list)}
 if(c.steps?.length){body.append(text('h3','操作步骤'));const list=document.createElement('ol');c.steps.forEach(s=>list.append(text('li',s)));body.append(list)}
 if(c.criteria?.length){body.append(text('h3','判定标准'));const list=document.createElement('ul');c.criteria.forEach(s=>list.append(text('li',s.title)));body.append(list)}
 if(c.reference){
  body.append(text('h3','参考图'));const response=await fetch('/api/reference?name='+encodeURIComponent(c.reference),{headers:{'x-viewer-token':token}});
  if(!response.ok){body.append(text('p','参考图读取失败'));return}
  const blob=await response.blob();if(gen!==generation)return;referenceUrl=URL.createObjectURL(blob);const image=document.createElement('img');image.id='reference';image.alt=c.title+'参考图';image.src=referenceUrl;body.append(image);
 }
 for(const s of c.stages){
  if(s.kind==='native'){const b=document.createElement('button');b.textContent='查看 '+s.title;b.onclick=()=>stage(c,s);body.append(b)}
  else if(s.url){const url=new URL(s.url);if(!['http:','https:'].includes(url.protocol))continue;const a=text('a','打开已有独立复测现场 ↗');a.href=url.href;a.target='_blank';a.rel='noopener';body.append(a)}
 }
}
async function stage(c,s,targetRunId){
 const gen=++generation;await clear();if(gen!==generation)return;history.replaceState(null,'','#'+c.id);for(const b of nav.querySelectorAll('[data-case]'))b.classList.toggle('active',b.dataset.case===c.id);document.querySelector('#title').textContent=c.title+' / '+s.title;document.querySelector('#identity').textContent=s.sessionId;document.querySelector('#notice').textContent=c.notice;body.style.display='none';viewer.style.display='block';status.textContent='加载中';
 try{const close=await mountNative({container:viewer,session:s,api,status:value=>{if(gen===generation)status.textContent=value},active:()=>gen===generation,targetRunId,navigate:(id,runId)=>{const next=c.stages.find(s=>s.sessionId===id);if(next)void stage(c,next,runId)}});if(gen!==generation)await close?.();else release=close}catch(error){if(gen===generation)status.textContent=error.message}
}
document.querySelector('#toggle').onclick=()=>{const wide=document.body.classList.toggle('wide');document.querySelector('#toggle').textContent=wide?'显示目录':'收起目录'};
document.querySelector('#report-toggle').onclick=async()=>{document.querySelector('#report pre').textContent=(await api('report')).text;document.querySelector('#report').showModal()};document.querySelector('#report .close').onclick=()=>document.querySelector('#report').close();
window.addEventListener('pagehide',()=>{void release?.()});
const all=suites.flatMap(s=>s.cases);const initial=all.find(c=>c.id===location.hash.slice(1))??all.find(c=>c.id==='hotel')??all[0];if(initial)await show(initial);
