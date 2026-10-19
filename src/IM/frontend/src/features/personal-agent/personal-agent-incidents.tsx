import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getCurrentLanguage, useTranslation } from '../../i18n';
import { getPersonalIncidents, respondToPersonalIncident } from './personal-agent-api';

/** Evidence comes from the owner-only incident API, never inferred from message prose. */
export function PersonalAgentIncidents({bindingId}:{bindingId:string}) {
  useTranslation();
  const zh=getCurrentLanguage()==='zh',text=(cn:string,en:string)=>zh?cn:en;
  const cache=useQueryClient();
  const incidents=useQuery({queryKey:['personal-agent',bindingId,'incidents'],queryFn:getPersonalIncidents,refetchInterval:()=>document.visibilityState==='visible'?5000:false});
  const respond=useMutation({mutationFn:({id,action}:{id:string;action:'block'|'misunderstanding'})=>respondToPersonalIncident(id,action),onSettled:()=>cache.invalidateQueries({queryKey:['personal-agent',bindingId,'incidents']})});
  return <>{(incidents.data?.items??[]).filter(item=>item.status==='open').map(item=><section className="pa-card" key={item.id}><h3>{text('一次需要你知情的请求','A request you should know about')}</h3><p><strong>{item.actor_name}</strong> · {text('疑似越界索取','Possible inappropriate request')}</p><p>{item.reason}</p>{item.count>1&&<p className="pa-notice">{text('相关请求次数：','Related requests: ')}{item.count}</p>}<p className="pa-notice">{text('这不是审批待办。不操作也不会放行相关信息。','This is an information notice. No action is needed to keep the disclosure blocked.')}</p><div className="pa-actions"><Link to={`/chat/${encodeURIComponent(item.conversation_id)}?message_id=${encodeURIComponent(item.source_message_id)}`} state={{personalAgentReturn:true}}>{text('查看相关记录','View related messages')}</Link><button disabled={respond.isPending} onClick={()=>respond.mutate({id:item.id,action:'block'})}>{text('屏蔽此人的新请求','Block new requests from this person')}</button><button disabled={respond.isPending} onClick={()=>respond.mutate({id:item.id,action:'misunderstanding'})}>{text('这是误会，继续协作','Misunderstanding; continue collaborating')}</button></div></section>)}{respond.isError&&<p className="pa-error" role="alert">{text('尚未保存处理结果，已重新核对状态。','The response was not saved; current state has been refreshed.')}</p>}</>;
}
