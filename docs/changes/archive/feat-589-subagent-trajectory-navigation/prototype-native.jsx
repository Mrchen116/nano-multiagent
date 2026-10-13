import * as React from 'react';
import * as Jsx from 'react/jsx-runtime';
import { createRoot } from 'react-dom/client';
import * as Cordis from '@deepseek-ai/cordis';
import * as Store from '@deepseek-ai/dsh-client-store';
import * as Primitives from '@deepseek-ai/dsh-client-ui-primitives';
import { TrajectoryView } from '../../trajectory-ui/src/client/TrajectoryView.tsx';
import { zh } from '../../trajectory-ui/src/client/locales.ts';
const t=(key,args={})=>(zh[key]??key).replace(/\{([^}]+)\}/g,(_,name)=>args[name]??'');
const user=(seq,time,text)=>({kind:'user',seq,time,source:null,content:[{type:'text',text}]});
const tool=(seq,time,callId,name)=>({kind:'tool-result',seq,time,callId,call:null,callTime:time-500,name,args:{type:'complete',value:{}},content:[{type:'text',text:'已完成委派；实际子执行状态独立记录'}],isError:false,subCalls:[]});
const assistant=(seq,time,text)=>({kind:'assistant',seq,time,turn:1,step:seq,blocks:[{kind:'text',text}],timing:{stepStartTime:time-1000,firstTokenTime:time-800,completedTime:time},usage:{inputTokens:1200,outputTokens:180}});
const facts={
 main:{label:'主 Agent',nodes:[user(1,1000,'整理本周数据，委派核对计算，然后整理可复用的经验。'),assistant(2,2000,'先委派计算，主任务继续进行。'),tool(3,3000,'calculate','subagent'),user(6,6000,'后台发起：记忆整理'),assistant(8,8000,'计算结果已收到，并完成交叉核对。')]},
 calculate:{label:'计算与交叉核对',nodes:[user(40,3000,'核对本周的计算结果，并请另一个 Agent 检查边界。'),tool(45,4200,'nested','subagent'),assistant(60,6000,'核对完成，结果一致。')],start:40,end:60,provider:'普通',status:'已完成'},
 nested:{label:'检查计算边界',nodes:[user(1,4200,'独立检查计算边界。'),assistant(5,5200,'边界检查通过。')],start:1,end:5,provider:'普通',status:'已完成'},
 memory:{label:'记忆整理',nodes:[user(1,1000,'继承的父会话记录：整理本周数据。'),assistant(8,8000,'继承的父会话输出。'),user(40,9000,'检查可跨任务复用的经验并更新记忆。'),assistant(48,11000,'已整理两条可复用经验。')],start:40,end:48,provider:'fork',status:'已完成'},
};
facts.main.nodes[1].blocks.push({kind:'tool-call',callId:'calculate',name:'subagent',argsRaw:JSON.stringify({description:'计算与交叉核对'})});
facts.calculate.nodes.splice(1,0,{...assistant(42,3800,'请独立核对边界。'),blocks:[{kind:'tool-call',callId:'nested',name:'subagent',argsRaw:JSON.stringify({description:'检查计算边界'})}]});
const noop=()=>{};
function Frame({id,navigate,state}){
 const fact=facts[id],ref=React.useRef(null),[history,setHistory]=React.useState(false),[duration,setDuration]=React.useState(false);
 const nodes=history||!fact.start?fact.nodes:fact.nodes.filter(n=>n.seq>=fact.start);
 const snapshot=React.useMemo(()=>({eventNodes:nodes,requests:[],eventLocations:new Map(),callSchemas:new Map(),partial:null,runningCalls:[]}),[nodes]);
 const [viewRequest,setViewRequest]=React.useState(null);
 const locate=end=>{
  const own=fact.nodes.filter(n=>n.seq>=fact.start&&n.seq<=fact.end),node=end?own.at(-1):own[0];
  if(!node)return;
  const identity=node.kind==='assistant'?`assistant\u0000${node.turn}\u0000${node.step}`:`${node.kind}\u0000seq\u0000${node.seq}`;
  [...ref.current.querySelectorAll('[data-trajectory-row-key]')].find(row=>row.getAttribute('data-trajectory-row-key')===encodeURIComponent(identity))?.click();
 };

 React.useEffect(()=>{
  const decorate=()=>{
   for(const row of ref.current.querySelectorAll('[data-trajectory-row-key]')){
    const key=row.getAttribute('data-trajectory-row-key');
    const child=id==='main'?(key.includes('calculate')?'calculate':key==='user%00seq%006'?'memory':null):id==='calculate'&&key.includes('nested')?'nested':null;
    if(!child||row.querySelector('.launch'))continue;
    if(child==='memory'){const label=row.querySelector('[data-role-kind]');if(label)label.textContent='发起';}
    const entry=document.createElement('div');entry.className='launch';
    const text=document.createElement('span');text.textContent=`${facts[child].label} · ${facts[child].provider} · ${child==='memory'?'后台维护':'主动委派'} · 已完成`;
    const button=document.createElement('button');button.textContent='查看本次执行 ↗';button.onclick=event=>{event.stopPropagation();navigate(child);};
    entry.append(text,button);row.lastElementChild.append(entry);
   }
  };
  decorate();const observer=new MutationObserver(decorate);observer.observe(ref.current,{childList:true,subtree:true});return()=>observer.disconnect();
 },[id,navigate]);
 React.useEffect(()=>{
  if(!fact.start)return;
  requestAnimationFrame(()=>{const plot=ref.current.querySelector('[aria-label="时间线概览；水平拖动可聚焦事件"]');if(!plot)return;const rect=plot.getBoundingClientRect();const start=history?0.51:0.01;for(const[type,percent]of[['pointerdown',start],['pointermove',.99],['pointerup',.99]])plot.dispatchEvent(new PointerEvent(type,{bubbles:true,button:0,pointerId:1,clientX:rect.left+rect.width*percent,clientY:rect.top+20}));});
 },[history,fact]);
 return <div className="frame" data-open-range={state==='结束未知'} ref={ref}>{fact.start&&<div className="scope"><div><strong>{fact.label}</strong><span>{fact.provider} · {state==='正常'?fact.status:state}</span><span>{history?'会话历史 · 高亮本次':'本次执行'}　#{fact.start} → {state==='结束未知'?'终点未知':`#${fact.end}`}</span></div><div className="scope-actions"><button onClick={()=>locate(false)}>定位起点</button><button disabled={state==='结束未知'} onClick={()=>locate(true)}>定位终点</button><button onClick={()=>setHistory(!history)}>{history?'只看本次执行':'查看会话历史'}</button></div>{state==='结束未知'&&<small>结束边界未知；时间概览的尾部仅表示最后已知记录。</small>}</div>}{state==='连接中断'&&<div className="notice" role="alert">更新中断；保留上次读取的记录和状态。</div>}<div className="native"><TrajectoryView useSession={select=>select({openState:'open',loadingOlder:false,hasMore:false})} useTrajectory={select=>select(snapshot)} useDuration={select=>select(duration)} setActualDuration={setDuration} loadOlder={async()=>false} loadImage={async()=>''} renderSlot={()=>null} t={t} viewRequest={viewRequest} completeViewRequest={()=>setViewRequest(null)} /></div></div>
}
function App(){const[stack,setStack]=React.useState(['main']),[state,setState]=React.useState('正常');const navigate=React.useCallback(id=>setStack(s=>[...s,id]),[]);return <><div className="demo"><strong>原生组件上的增量原型</strong><span>固定示例；范围条与行内入口为本次增量，数据与拖选为演示。</span><select aria-label="演示状态" value={state} onChange={e=>setState(e.target.value)}>{['正常','结束未知','连接中断'].map(v=><option key={v}>{v}</option>)}</select></div><main><header>Agent 工作台 <span>原生轨迹 · 只读</span></header>{stack.length>1&&<nav><button onClick={()=>setStack(s=>s.slice(0,-1))}>← 返回发起点</button><span>{stack.map(id=>facts[id].label).join(' › ')}</span></nav>}<div className="layers">{stack.map((id,i)=><div className="layer" key={i} hidden={i!==stack.length-1}><Frame id={id} navigate={navigate} state={state}/></div>)}</div></main></>}
const ctx=new Cordis.Context();ctx.provide('configForms',{get:()=>Store.createSnapshotStore({value:{preference:'light',fontSize:14}})});ctx.provide('locale',{register:()=>()=>{}});ctx.provide('slots',{inject:()=>{}});
window.__ModuleLoader__={load:entry=>{const exports=entry.factory(id=>({'react/jsx-runtime':Jsx,'@deepseek-ai/dsh-client-ui-primitives':Primitives,'@deepseek-ai/dsh-client-store':Store})[id]);exports.apply(ctx);}};
const script=document.createElement('script');script.src='http://127.0.0.1:63084/trajectory/plugins/@deepseek-ai/dsh-client-ui-theme/client.js';script.onload=()=>createRoot(document.getElementById('root')).render(<App/>);script.onerror=()=>{document.getElementById('root').textContent='原型依赖的隔离主题资源不可用，请先启动测试服务。';};document.head.append(script);
