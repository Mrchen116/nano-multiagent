import { PersonalAgentIncidents } from './personal-agent-incidents';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import type { PersonalAgentState } from './personal-agent-api';
import './personal-agent.css';

export function PersonalAgentCollaboration({state, pendingOwnerInput=false}: {state:PersonalAgentState; pendingOwnerInput?:boolean}) {
  useTranslation();
  const zh=getCurrentLanguage()==='zh', text=(cn:string,en:string)=>zh?cn:en;
  return <div className="pa-collaboration">
    {pendingOwnerInput&&state.binding!.status==='active'&&<p className="pa-notice" role="status">{text('正在处理你的请求…','Working on your request…')}</p>}
    {state.binding!.status!=='active'&&<p className="pa-notice" role="status">{text('助手尚未就绪，工作请求会保留；电脑恢复后继续。','Your assistant is not ready. Requests remain saved for recovery.')}</p>}
    <PersonalAgentIncidents bindingId={state.binding!.binding_id}/>
  </div>;
}
