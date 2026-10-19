import { PersonalAgentIncidents } from './personal-agent-incidents';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import { getPersonalAssistance, getPersonalDecisions, resolvePersonalDecision, setPersonalAssistancePaused, type PersonalAgentState, type PersonalDecision } from './personal-agent-api';
import './personal-agent.css';

export function PersonalAgentCollaboration({state, onDraft, pendingOwnerInput=false}: {state:PersonalAgentState; pendingOwnerInput?:boolean; onDraft(decision:PersonalDecision, text:string):void}) {
  useTranslation();
  const zh=getCurrentLanguage()==='zh', text=(cn:string,en:string)=>zh?cn:en;
  const bindingId=state.binding!.binding_id;
  const decisions=useQuery({queryKey:['personal-agent',bindingId,'decisions'],queryFn:getPersonalDecisions,refetchInterval:()=>document.visibilityState==='visible'?5000:false});
  const [clock,setClock]=useState(Date.now());
  useEffect(()=>{
    const next=(decisions.data?.items??[]).map(d=>d.snooze_until?new Date(d.snooze_until).getTime():0).filter(at=>at>Date.now()).sort((a,b)=>a-b)[0];
    if(!next)return;
    const timer=window.setTimeout(()=>setClock(Date.now()),Math.min(next-Date.now()+1,2_147_483_647));
    return ()=>window.clearTimeout(timer);
  },[decisions.data,clock]);
  return <div className="pa-collaboration">
    {pendingOwnerInput&&state.binding!.status==='active'&&<p className="pa-notice" role="status">{text('正在理解你的请求…','Understanding your request…')}</p>}
    {state.binding!.status!=='active'&&<p className="pa-notice" role="status">{text('助手尚未就绪，工作请求会保留；电脑恢复后继续。','Your assistant is not ready. Requests remain saved for recovery.')}</p>}
    {state.policy&&!state.policy.observation_enabled&&<p className="pa-notice">{text('已暂停新消息观察。已交办目标继续；新消息可能尚未看到。','New-message observation is paused. Assigned goals continue; new messages may not have been seen.')}</p>}
    {decisions.isError&&<p className="pa-error" role="alert">{text('暂时无法读取最新进展。','Could not load the latest progress.')} <button onClick={()=>{void decisions.refetch();}}>{text('重试','Retry')}</button></p>}
    {(decisions.data?.items??[]).filter(d=>d.status==='pending'&&(!d.snooze_until||new Date(d.snooze_until).getTime()<=clock)).map(d=><DecisionCard key={`${d.id}:${d.revision}`} decision={d} onDraft={onDraft}/>)}

    <PersonalAgentIncidents bindingId={bindingId}/>
  </div>;
}

function DecisionCard({decision, onDraft}:{decision:PersonalDecision;onDraft(decision:PersonalDecision,text:string):void}) {
  useTranslation();
  const zh=getCurrentLanguage()==='zh',text=(cn:string,en:string)=>zh?cn:en;
  const cache=useQueryClient();
  const [draft,setDraft]=useState(decision.content??'');
  const [snooze,setSnooze]=useState('');
  const [showSnooze,setShowSnooze]=useState(false);
  const resolve=useMutation({mutationFn:(choice:{option?:string;snooze_until?:string;decline?:boolean})=>resolvePersonalDecision(decision.id,{expected_revision:decision.revision,request_key:`${decision.id}:${decision.revision}:${JSON.stringify(choice)}`,...choice}),onSettled:()=>cache.invalidateQueries({queryKey:['personal-agent']})});
  return <section className="pa-card" aria-label={decision.question}><h3>{decision.question}</h3>
    {decision.kind==='draft'?<><p className="pa-notice">{text('仅你可见的草稿，由你编辑后以本人身份发送。','Private draft. Edit it and send as yourself.')}</p><textarea aria-label={text('回复草稿','Reply draft')} value={draft} onChange={e=>setDraft(e.target.value)}/><div className="pa-actions"><button disabled={!draft.trim()||!decision.target_conversation_id} onClick={()=>onDraft(decision,draft)}>{text('放入原聊天输入框','Use in original chat')}</button></div>{decision.target_conversation_id&&decision.source_message_id&&<Link to={`/chat/${encodeURIComponent(decision.target_conversation_id)}?message_id=${encodeURIComponent(decision.source_message_id)}`} state={{personalAgentReturn:true}}>{text('查看原消息','View original message')}</Link>}</>:<div className="pa-actions">{decision.options.map(option=><button key={option.id} disabled={resolve.isPending} onClick={()=>resolve.mutate({option:option.id})}><strong>{option.label}{decision.recommended===option.id?text(' · 推荐',' · Recommended'):''}</strong>{option.consequence&&<span style={{display:'block'}}>{option.consequence}</span>}</button>)}</div>}
    <div className="pa-actions">{decision.kind==='choice'&&<button disabled={resolve.isPending} onClick={()=>setShowSnooze(!showSnooze)}>{text('稍后提醒','Remind me later')}</button>}<button disabled={resolve.isPending} onClick={()=>resolve.mutate({decline:true})}>{decision.kind==='draft'?text('不用这份草稿','Dismiss draft'):text('不采用','Decline')}</button></div>
    {showSnooze&&<form onSubmit={e=>{e.preventDefault();if(snooze)resolve.mutate({snooze_until:new Date(snooze).toISOString()});}}><label>{text('提醒时间','Remind at')}<input type="datetime-local" required value={snooze} onChange={e=>setSnooze(e.target.value)}/></label><div className="pa-actions"><button disabled={!snooze||resolve.isPending}>{text('确定时间','Set time')}</button></div></form>}
    {resolve.isError&&<p className="pa-error" role="alert">{text('决定尚未保存，已重新核对最新内容。','Your choice was not saved; the latest decision has been refreshed.')}</p>}
  </section>;
}

export function PersonalAgentGoals({state}:{state:PersonalAgentState}) {
  const {t}=useTranslation();
  const zh=getCurrentLanguage()==='zh',text=(cn:string,en:string)=>zh?cn:en;
  const cache=useQueryClient();
  const bindingId=state.binding!.binding_id;
  const assistance=useQuery({queryKey:['personal-agent',bindingId,'assistance'],queryFn:getPersonalAssistance,refetchInterval:()=>document.visibilityState==='visible'?5000:false});
  const pause=useMutation({mutationFn:(input:{taskRef:string;paused:boolean;revision:number})=>setPersonalAssistancePaused(input.taskRef,input.paused,input.revision),onSettled:()=>cache.invalidateQueries({queryKey:['personal-agent',bindingId,'assistance']})});
  return <>
    {!!assistance.data?.items.length&&<details className="pa-goals-menu"><summary>{text('跟进中','Following up')} · {assistance.data.items.length}</summary><div className="pa-goals-panel">{assistance.data.items.map(item=><section key={item.task_ref} className="pa-goal"><h3>{item.task?<Link to={`/tasks/${encodeURIComponent(item.task_ref)}`}>{item.task.title}</Link>:text('来源暂不可读','Source unavailable')}</h3>
      {item.task&&<p className="pa-notice">{text('任务状态：','Task status: ')}{t(`tasks.status.${item.task.status}`,{defaultValue:item.task.status})}</p>}
      {item.next_action&&<p>{text('接下来：','Next: ')}{item.next_action}</p>}{item.waiting_on&&<p>{text('正在等：','Waiting for: ')}{item.waiting_on}</p>}{item.next_check_at&&<p>{text('下次跟进：','Next check: ')}{new Date(item.next_check_at).toLocaleString()}</p>}
      {typeof item.task?.result==='string'&&<p>{item.task.result}</p>}
      <div className="pa-actions">{item.status!=='completed'&&<button disabled={pause.isPending} onClick={()=>pause.mutate({taskRef:item.task_ref,paused:!item.paused,revision:item.revision})}>{item.paused?text('继续这件事','Resume this goal'):text('暂缓这件事','Pause this goal')}</button>}{item.status==='completed'&&<span className="pa-notice">{text('已完成','Completed')}</span>}{item.paused&&<span className="pa-notice">{text('仅暂缓这件事，原任务状态不变。','Only this assistance is paused; the task status is unchanged.')}</span>}{item.status==='pending'&&<span className="pa-notice">{text('等待电脑确认','Waiting for computer confirmation')}</span>}</div>
    </section>)}    {pause.isError&&<p className="pa-error" role="alert">{text('尚未确认操作成功，已重新读取状态。','The change is not confirmed; current state has been refreshed.')}</p>}</div></details>}

  </>;
}
