import * as Dialog from '@radix-ui/react-dialog';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import { createPersonalAgent, type PersonalAgentState } from './personal-agent-api';
import './personal-agent.css';

export function PersonalAgentDialog({state, nodes, onClose, onCreated}: {
  state: PersonalAgentState;
  nodes: {node_id: string; node_name: string; status: string}[];
  onClose(): void;
  onCreated(conversationId: string): void;
}) {
  useTranslation();
  const zh = getCurrentLanguage() === 'zh', text = (cn:string,en:string) => zh ? cn : en;
  const cache = useQueryClient();
  const [name,setName] = useState(state.binding?.display_name ?? text('小助理','My assistant'));
  const [nodeId,setNodeId] = useState(nodes.find(n=>n.status==='online')?.node_id ?? nodes[0]?.node_id ?? '');
  const createKey = useRef(crypto.randomUUID());
  const refresh = () => cache.invalidateQueries({queryKey:['personal-agent']});
  const create = useMutation({mutationFn:()=>createPersonalAgent({request_key:createKey.current,node_id:nodeId,display_name:name.trim()}),onSuccess:async result=>{await Promise.all([refresh(),cache.invalidateQueries({queryKey:['chat']})]);if(result.binding) onCreated(result.binding.conversation_id);}});
  const recover = useMutation({mutationFn:()=>createPersonalAgent({request_key:state.creation!.request_key,node_id:state.binding!.node_id,display_name:state.binding!.display_name}),onSuccess:refresh,onError:refresh});
  return <Dialog.Root open onOpenChange={open=>{if(!open)onClose();}}><Dialog.Portal><Dialog.Overlay className="pa-dialog-overlay"/><Dialog.Content className="pa-dialog" aria-describedby={!state.binding ? "pa-create-access-notice" : undefined}><Dialog.Title>{state.binding ? text('个人助手','Personal assistant') : text('创建个人助手','Create personal assistant')}</Dialog.Title>

    {!state.binding ? <form onSubmit={e=>{e.preventDefault();create.mutate();}}>
      <label>{text('名字','Name')}<input value={name} onChange={e=>setName(e.target.value)} maxLength={80} required/></label>{!name.trim()&&<p className="pa-error" role="status">{text('请填写助手名字。','Enter a name for your assistant.')}</p>}
      {nodes.length > 1 && <label>{text('工作电脑','Computer')}<select value={nodeId} onChange={e=>setNodeId(e.target.value)}>{nodes.map(n=><option key={n.node_id} value={n.node_id}>{n.node_name}{n.status!=='online'?text(' · 离线',' · Offline'):''}</option>)}</select></label>}
      <p id="pa-create-access-notice">{text('助手可按需查询你有权查看的已参与聊天。相关资料会由你配置的模型处理。你随时可以排除某个聊天；PA 看过不代表你已读。','Your assistant can look up conversations you participated in and can still access. Your configured model processes relevant information. You can exclude a chat anytime. Assistant activity does not mark messages read for you.')}</p>
      {!nodes.length && <p><Link to="/onboarding">{text('先连接工作电脑和模型','Connect a computer and model first')}</Link></p>}
      {create.isError && <p className="pa-error" role="alert">{text('尚未确认创建成功。内容已保留，请重试。','Creation has not been confirmed. Your input is preserved; retry.')}</p>}
      <footer><Dialog.Close className="pa-secondary" type="button">{text('稍后','Later')}</Dialog.Close><button className="im-btn im-btn-primary" disabled={!name.trim()||!nodeId||create.isPending}>{create.isPending?text('正在创建…','Creating…'):text('创建个人助手','Create personal assistant')}</button></footer>
    </form> : <>
      {state.binding.status!=='active'&&<p role="status">{text('助手尚未准备完成，创建信息已保留。','Your assistant is not ready; its setup is saved.')} {state.creation&&<button className="pa-secondary" disabled={recover.isPending} onClick={()=>recover.mutate()}>{text('重新准备','Retry setup')}</button>}</p>}
      {recover.isError&&<p className="pa-error" role="alert">{text('操作尚未保存成功，请重试。','The change was not saved. Please retry.')}</p>}
      <footer><Dialog.Close className="pa-secondary">{text('完成','Done')}</Dialog.Close></footer>
    </>}
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
