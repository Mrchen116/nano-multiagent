import { Avatar, agentAvatarId } from "../chat/components/avatar";
import { PersonalAgentIncidents } from './personal-agent-incidents';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import type { PersonalAgentState } from './personal-agent-api';
import './personal-agent.css';

export function PersonalAgentCollaboration({state, pendingOwnerInput=false}: {state:PersonalAgentState; pendingOwnerInput?:boolean}) {
  useTranslation();
  const zh=getCurrentLanguage()==='zh', text=(cn:string,en:string)=>zh?cn:en;
  return <div className="pa-collaboration">
    {pendingOwnerInput&&state.binding!.status==='active'&&<p className="pa-notice pa-waiting" role="status"><Avatar id={agentAvatarId(state.binding!.agent_id)} size={24} /><span>{text('消息已发出，等待助手接收…','Message sent. Waiting for your assistant to receive it…')}</span></p>}
    {state.binding!.status!=='active'&&<p className="pa-notice" role="status">{text('助手尚未就绪，工作请求会保留；电脑恢复后继续。','Your assistant is not ready. Requests remain saved for recovery.')}</p>}
    <PersonalAgentIncidents bindingId={state.binding!.binding_id}/>
  </div>;
}
