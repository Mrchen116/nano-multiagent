import * as Dialog from '@radix-ui/react-dialog';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import type { Conversation } from '../chat/chat-types';
import { restorePersonalAgent, renamePersonalAgent, createPersonalAgent, updatePersonalAgentPolicy, type PersonalAgentState } from './personal-agent-api';
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
  const [nodeId,setNodeId] = useState(nodes.find(n=>n.status==='online')?.node_id ?? nodes[0]?.node_id ?? '');
  const [sourceSearch,setSourceSearch] = useState('');
  const createKey = useRef(crypto.randomUUID());
  const refresh = () => cache.invalidateQueries({queryKey:['personal-agent']});
  const create = useMutation({mutationFn:()=>createPersonalAgent({request_key:createKey.current,node_id:nodeId,display_name:name.trim()}),onSuccess:async result=>{await Promise.all([refresh(),cache.invalidateQueries({queryKey:['chat']})]);if(result.binding) onCreated(result.binding.conversation_id);}});
  const update = useMutation({mutationFn:(patch:{excluded_conversation_ids?:string[]})=>updatePersonalAgentPolicy({expected_revision:state.policy!.revision,...patch}),onSuccess:refresh,onError:refresh});
  const rename = useMutation({mutationFn:()=>renamePersonalAgent(name.trim()),onSuccess:async()=>{await Promise.all([refresh(),...['chat','contacts','public-agents','settings'].map(key=>cache.invalidateQueries({queryKey:[key]}))]);}});
  const recover = useMutation({mutationFn:()=>createPersonalAgent({request_key:state.creation!.request_key,node_id:state.binding!.node_id,display_name:state.binding!.display_name}),onSuccess:refresh,onError:refresh});
  const restore=useMutation({mutationFn:()=>restorePersonalAgent(nodeId),onSuccess:refresh,onError:refresh});
  const policy = state.policy;
  return <Dialog.Root open onOpenChange={open=>{if(!open)onClose();}}><Dialog.Portal><Dialog.Overlay className="pa-dialog-overlay"/><Dialog.Content className="pa-dialog"><Dialog.Title>{state.binding ? text('个人助手','Personal assistant') : text('认识你的个人助手','Meet your personal assistant')}</Dialog.Title>
    <Dialog.Description>{state.binding ? text('直接在聊天里交代目标、纠正偏好或叫停。','Give it goals, correct preferences, or ask it to stop in chat.') : text('准备、协调和持续跟进交给它。需要你决定的事，再来找你。','It prepares, coordinates, and follows through, asking you when a decision is needed.')}</Dialog.Description>
    {!state.binding ? <form onSubmit={e=>{e.preventDefault();create.mutate();}}>
      <label>{text('名字','Name')}<input value={name} onChange={e=>setName(e.target.value)} maxLength={80} required/></label>{!name.trim()&&<p className="pa-error" role="status">{text('请填写助手名字。','Enter a name for your assistant.')}</p>}
      {nodes.length > 1 && <label>{text('工作电脑','Computer')}<select value={nodeId} onChange={e=>setNodeId(e.target.value)}>{nodes.map(n=><option key={n.node_id} value={n.node_id}>{n.node_name}{n.status!=='online'?text(' · 离线',' · Offline'):''}</option>)}</select></label>}
      <p>{text('助手可按需查询你有权查看的已参与聊天。相关资料会由你配置的模型处理。你随时可以排除某个聊天；PA 看过不代表你已读。','Your assistant can look up conversations you participated in and can still access. Your configured model processes relevant information. You can exclude a chat anytime. Assistant activity does not mark messages read for you.')}</p>
      {!nodes.length && <p><Link to="/onboarding">{text('先连接工作电脑和模型','Connect a computer and model first')}</Link></p>}
      {create.isError && <p className="pa-error" role="alert">{text('尚未确认创建成功。内容已保留，请重试。','Creation has not been confirmed. Your input is preserved; retry.')}</p>}
      <footer><Dialog.Close className="pa-secondary" type="button">{text('稍后','Later')}</Dialog.Close><button className="im-btn im-btn-primary" disabled={!name.trim()||!nodeId||create.isPending}>{create.isPending?text('正在创建…','Creating…'):text('创建个人助手','Create personal assistant')}</button></footer>
    </form> : <>
      {state.binding.status!=='active'&&<p role="status">{text('助手尚未准备完成，创建信息已保留。','Your assistant is not ready; its setup is saved.')} {state.creation&&<button className="pa-secondary" disabled={recover.isPending} onClick={()=>recover.mutate()}>{text('重新准备','Retry setup')}</button>}</p>}
      <form onSubmit={e=>{e.preventDefault();rename.mutate();}}><label>{text('名字','Name')}<input value={name} onChange={e=>setName(e.target.value)} maxLength={80} required/></label>{!name.trim()&&<p className="pa-error" role="status">{text('请填写助手名字。','Enter a name for your assistant.')}</p>}{name.trim()!==state.binding.display_name&&<button className="pa-secondary" disabled={!name.trim()||rename.isPending}>{text('保存名字','Save name')}</button>}</form>
      <Link to={`/settings/agents/${state.binding.agent_id}`} onClick={onClose} className="pa-secondary">{text('模型、指令与能力配置','Model, instructions & capabilities')}</Link>
      {policy && <>
      <details><summary>{text('不让助手查看的聊天','Chats excluded from assistant access')}</summary><label>{text('查找聊天','Find a chat')}<input type="search" value={sourceSearch} onChange={e=>setSourceSearch(e.target.value)}/></label><div className="pa-source-list">{conversations.filter(c=>c.id!==state.binding!.conversation_id&&c.title.toLowerCase().includes(sourceSearch.toLowerCase())).map(c=><label key={c.id}><input type="checkbox" checked={policy.excluded_conversation_ids.includes(c.id)} disabled={update.isPending} onChange={e=>update.mutate({excluded_conversation_ids:e.target.checked?[...policy.excluded_conversation_ids,c.id]:policy.excluded_conversation_ids.filter(id=>id!==c.id)})}/>{c.title}</label>)}</div><p>{text('排除后，该聊天不再用于自动观察或历史查询；可随时取消排除。','Excluded chats are unavailable for observation and history lookup. You can restore access here.')}</p></details></>}
      {nodes.some(n=>n.node_id!==state.binding!.node_id&&n.status==='online')&&<details><summary>{text('更换工作电脑','Change working computer')}</summary><p>{text('保留同一个助手、聊天和目标。旧电脑停止替你行动，本地私人历史不自动复制；助手会重新读取仍获准的资料并安排后续跟进。','Keeps the same assistant, chat and goals. The previous computer loses authority. Local private history is not copied; your assistant reloads allowed sources and reschedules follow-ups.')}</p><label>{text('工作电脑','Computer')}<select value={nodeId} onChange={e=>setNodeId(e.target.value)}>{nodes.filter(n=>n.status==='online').map(n=><option key={n.node_id} value={n.node_id}>{n.node_name}</option>)}</select></label><button className="pa-secondary" disabled={restore.isPending||nodeId===state.binding.node_id} onClick={()=>restore.mutate()}>{text('在这台电脑继续','Continue on this computer')}</button></details>}
      {(update.isError||rename.isError||recover.isError||restore.isError)&&<p className="pa-error" role="alert">{text('操作尚未保存成功，请重试。','The change was not saved. Please retry.')}</p>}
      <footer><Dialog.Close className="pa-secondary">{text('完成','Done')}</Dialog.Close></footer>
    </>}
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
