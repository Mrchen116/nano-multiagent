import * as Dialog from '@radix-ui/react-dialog';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import type { Conversation } from '../chat/chat-types';
import { cleanupPersonalAgent, getPersonalAgentCleanup, restorePersonalAgent, renamePersonalAgent, createPersonalAgent, updatePersonalAgentPolicy, type PersonalAgentState } from './personal-agent-api';
import './personal-agent.css';

export function PersonalAgentDialog({state, nodes, conversations, onClose, onCreated}: {
  state: PersonalAgentState;
  nodes: {node_id: string; node_name: string; status: string}[];
  conversations: Conversation[];
  onClose(): void;
  onCreated(conversationId: string): void;
}) {
  useTranslation();
  const zh = getCurrentLanguage() === 'zh', text = (cn:string,en:string) => zh ? cn : en;
  const cache = useQueryClient();
  const [name,setName] = useState(state.binding?.display_name ?? text('小助理','My assistant'));
  const [goal,setGoal] = useState('');
  const [observe,setObserve] = useState(true);
  const [nodeId,setNodeId] = useState(nodes.find(n=>n.status==='online')?.node_id ?? nodes[0]?.node_id ?? '');
  const [sourceSearch,setSourceSearch] = useState('');
  const createKey = useRef(crypto.randomUUID());
  const cleanupKey = useRef(crypto.randomUUID());
  const refresh = () => cache.invalidateQueries({queryKey:['personal-agent']});
  const create = useMutation({mutationFn:()=>createPersonalAgent({request_key:createKey.current,node_id:nodeId,display_name:name.trim(),initial_goal:goal.trim() || undefined,observation_enabled:observe}),onSuccess:async result=>{await Promise.all([refresh(),cache.invalidateQueries({queryKey:['chat']})]);if(result.binding) onCreated(result.binding.conversation_id);}});
  const update = useMutation({mutationFn:(patch:{observation_enabled?:boolean;excluded_conversation_ids?:string[]})=>updatePersonalAgentPolicy({expected_revision:state.policy!.revision,...patch}),onSuccess:refresh,onError:refresh});
  const cleanup = useMutation({mutationFn:()=>cleanupPersonalAgent({request_key:cleanupKey.current}),onSuccess:async()=>{await refresh();await cache.invalidateQueries({queryKey:['personal-agent',state.binding?.binding_id,'cleanup']});}});
  const cleanups = useQuery({queryKey:['personal-agent',state.binding?.binding_id,'cleanup'],queryFn:getPersonalAgentCleanup,enabled:!!state.binding,refetchInterval:query=>query.state.data?.items.some(item=>item.status==='pending')?3000:false});
  const rename = useMutation({mutationFn:()=>renamePersonalAgent(name.trim()),onSuccess:async()=>{await Promise.all([refresh(),...['chat','contacts','public-agents','settings'].map(key=>cache.invalidateQueries({queryKey:[key]}))]);}});
  const cleanupState = cleanups.data?.items.find(item=>item.operation_id===cleanup.data?.operation_id) ?? cleanup.data ?? cleanups.data?.items.find(item=>item.status==='pending') ?? cleanups.data?.items[0];
  const recover = useMutation({mutationFn:()=>createPersonalAgent({request_key:state.creation!.request_key,node_id:state.binding!.node_id,display_name:state.binding!.display_name,initial_goal:state.creation!.initial_goal??undefined,observation_enabled:state.policy?.observation_enabled??true}),onSuccess:refresh,onError:refresh});
  const restore=useMutation({mutationFn:()=>restorePersonalAgent(nodeId),onSuccess:refresh,onError:refresh});
  const policy = state.policy;
  return <Dialog.Root open onOpenChange={open=>{if(!open)onClose();}}><Dialog.Portal><Dialog.Overlay className="pa-dialog-overlay"/><Dialog.Content className="pa-dialog"><Dialog.Title>{state.binding ? text('个人助手','Personal assistant') : text('认识你的个人助手','Meet your personal assistant')}</Dialog.Title>
    <Dialog.Description>{state.binding ? text('直接在聊天里交代目标、纠正偏好或叫停。','Give it goals, correct preferences, or ask it to stop in chat.') : text('准备、协调和持续跟进交给它。需要你决定的事，再来找你。','It prepares, coordinates, and follows through, asking you when a decision is needed.')}</Dialog.Description>
    {!state.binding ? <form onSubmit={e=>{e.preventDefault();create.mutate();}}>
      <label>{text('名字','Name')}<input value={name} onChange={e=>setName(e.target.value)} maxLength={80} required/></label>{!name.trim()&&<p className="pa-error" role="status">{text('请填写助手名字。','Enter a name for your assistant.')}</p>}
      <label>{text('最近想推进什么？（可选）','What would you like to work on? (optional)')}<textarea value={goal} onChange={e=>setGoal(e.target.value)}/></label>
      {nodes.length > 1 && <label>{text('工作电脑','Computer')}<select value={nodeId} onChange={e=>setNodeId(e.target.value)}>{nodes.map(n=><option key={n.node_id} value={n.node_id}>{n.node_name}{n.status!=='online'?text(' · 离线',' · Offline'):''}</option>)}</select></label>}
      <label className="pa-toggle"><input type="checkbox" checked={observe} onChange={e=>setObserve(e.target.checked)}/><span>{text('了解我的聊天与任务，主动跟进','Follow my conversations and tasks')}</span></label>
      <p>{text('助手可按需查询你有权查看的已参与聊天。相关资料会由你配置的模型处理。你随时可以暂停观察或排除某个聊天；PA 看过不代表你已读。','Your assistant can look up conversations you participated in and can still access. Your configured model processes relevant information. You can pause observation or exclude a chat anytime. Assistant activity does not mark messages read for you.')}</p>
      {!nodes.length && <p><Link to="/onboarding">{text('先连接工作电脑和模型','Connect a computer and model first')}</Link></p>}
      {create.isError && <p className="pa-error" role="alert">{text('尚未确认创建成功。内容已保留，请重试。','Creation has not been confirmed. Your input is preserved; retry.')}</p>}
      <footer><Dialog.Close className="pa-secondary" type="button">{text('稍后','Later')}</Dialog.Close><button className="im-btn im-btn-primary" disabled={!name.trim()||!nodeId||create.isPending}>{create.isPending?text('正在创建…','Creating…'):text('创建并开始合作','Create and start')}</button></footer>
    </form> : <>
      {state.binding.status!=='active'&&<p role="status">{text('助手尚未准备完成，目标已保留。','Your assistant is not ready; its goal is saved.')} {state.creation&&<button className="pa-secondary" disabled={recover.isPending} onClick={()=>recover.mutate()}>{text('重新准备','Retry setup')}</button>}</p>}
      <form onSubmit={e=>{e.preventDefault();rename.mutate();}}><label>{text('名字','Name')}<input value={name} onChange={e=>setName(e.target.value)} maxLength={80} required/></label>{!name.trim()&&<p className="pa-error" role="status">{text('请填写助手名字。','Enter a name for your assistant.')}</p>}{name.trim()!==state.binding.display_name&&<button className="pa-secondary" disabled={!name.trim()||rename.isPending}>{text('保存名字','Save name')}</button>}</form>
      <Link to={`/settings/agents/${state.binding.agent_id}`} onClick={onClose} className="pa-secondary">{text('模型、指令与能力配置','Model, instructions & capabilities')}</Link>
      {policy && <><label className="pa-toggle"><input type="checkbox" checked={policy.observation_enabled} disabled={update.isPending} onChange={e=>update.mutate({observation_enabled:e.target.checked})}/><span>{text('了解新消息，主动跟进','Observe new messages and follow up')}</span></label><p>{text('暂停只影响新消息观察，已交办目标和按需历史查询继续。暂缓某件事，请在目标里操作或直接告诉助手。','Pausing observation keeps assigned goals and on-demand history lookup active. Pause an individual goal below or ask your assistant.')}</p>
      <details><summary>{text('不让助手查看的聊天','Chats excluded from assistant access')}</summary><label>{text('查找聊天','Find a chat')}<input type="search" value={sourceSearch} onChange={e=>setSourceSearch(e.target.value)}/></label><div className="pa-source-list">{conversations.filter(c=>c.id!==state.binding!.conversation_id&&c.title.toLowerCase().includes(sourceSearch.toLowerCase())).map(c=><label key={c.id}><input type="checkbox" checked={policy.excluded_conversation_ids.includes(c.id)} disabled={update.isPending} onChange={e=>update.mutate({excluded_conversation_ids:e.target.checked?[...policy.excluded_conversation_ids,c.id]:policy.excluded_conversation_ids.filter(id=>id!==c.id)})}/>{c.title}</label>)}</div><p>{text('排除后，该聊天不再用于自动观察或历史查询；可随时取消排除。','Excluded chats are unavailable for observation and history lookup. You can restore access here.')}</p></details></>}
      {nodes.some(n=>n.node_id!==state.binding!.node_id&&n.status==='online')&&<details><summary>{text('更换工作电脑','Change working computer')}</summary><p>{text('保留同一个助手、聊天和目标。旧电脑停止替你行动，本地私人历史不自动复制；助手会重新读取仍获准的资料并安排后续跟进。','Keeps the same assistant, chat and goals. The previous computer loses authority. Local private history is not copied; your assistant reloads allowed sources and reschedules follow-ups.')}</p><label>{text('工作电脑','Computer')}<select value={nodeId} onChange={e=>setNodeId(e.target.value)}>{nodes.filter(n=>n.status==='online').map(n=><option key={n.node_id} value={n.node_id}>{n.node_name}</option>)}</select></label><button className="pa-secondary" disabled={restore.isPending||nodeId===state.binding.node_id} onClick={()=>restore.mutate()}>{text('在这台电脑继续','Continue on this computer')}</button></details>}
      <details><summary>{text('清理助手的来源缓存','Clear assistant source cache')}</summary><p>{text('清理来源缓存，不删除原聊天、执行记录或已经发出的内容。仍获准的资料可在后续问题中重新查询。','Clears source cache, not original chats, execution records, or previously sent content. Authorized sources remain available for later questions.')}</p><button className="pa-secondary" disabled={cleanup.isPending||cleanupState?.status==='pending'} onClick={()=>{if(cleanupState?.status==='completed')cleanupKey.current=crypto.randomUUID();cleanup.mutate();}}>{text('清理全部来源缓存','Clear all source cache')}</button>{cleanupState&&<p role="status">{cleanupState.status==='completed'?text('来源缓存已清理。','Source cache cleared.'):text('已提交，等待电脑确认清理完成。','Requested; waiting for your computer to confirm completion.')}</p>}</details>
      {(update.isError||cleanup.isError||rename.isError||recover.isError||restore.isError)&&<p className="pa-error" role="alert">{text('操作尚未保存成功，请重试。','The change was not saved. Please retry.')}</p>}
      <footer><Dialog.Close className="pa-secondary">{text('完成','Done')}</Dialog.Close></footer>
    </>}
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
