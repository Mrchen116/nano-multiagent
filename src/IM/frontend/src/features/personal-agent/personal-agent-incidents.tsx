import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../i18n';
import { getPersonalIncidents, respondToPersonalIncident, type PersonalIncident } from './personal-agent-api';
import './personal-agent.css';

/** Summarize owner-only evidence without turning blocked requests into an approval queue. */
export function PersonalAgentIncidents({bindingId}:{bindingId:string}) {
  const {t}=useTranslation();
  const [expanded,setExpanded]=useState(false);
  const [feedback,setFeedback]=useState('');
  const cache=useQueryClient();
  const key=['personal-agent',bindingId,'incidents'];
  const incidents=useQuery({queryKey:key,queryFn:getPersonalIncidents,refetchInterval:()=>document.visibilityState==='visible'?5000:false});
  const respond=useMutation({
    mutationFn:async({items,action}:{items:PersonalIncident[];action:'block'|'misunderstanding'|'dismiss'})=>{
      // Blocking applies to the contact. Acknowledging only closes the records the user saw.
      const targets=action==='block'?items.slice(0,1):items;
      const results=await Promise.allSettled(targets.map(item=>respondToPersonalIncident(item.id,action)));
      if(results.some(result=>result.status==='rejected'))throw new Error('Not all responses were saved');
      return action;
    },
    onMutate:()=>setFeedback(''),
    onSuccess:action=>setFeedback(t(`pa.privacy.saved.${action}`)),
    onSettled:()=>cache.invalidateQueries({queryKey:key}),
  });
  const open=(incidents.data?.items??[]).filter(item=>item.status==='open');
  const groups=new Map<string,PersonalIncident[]>();
  for(const item of open)groups.set(item.actor_id,[...(groups.get(item.actor_id)??[]),item]);
  const total=open.reduce((sum,item)=>sum+item.count,0);
  if(!open.length)return feedback?<p className="pa-privacy-feedback" role="status">{feedback}</p>:null;
  return <section className="pa-privacy" aria-label={t('pa.privacy.title')}>
    <button type="button" className="pa-privacy-summary" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>
      <span className="pa-privacy-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M12 3 4 6v5c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-3Z"/><path d="m8 12 3 3 5-6"/></svg></span>
      <span className="pa-privacy-summary-copy"><strong>{t('pa.privacy.title')}<span className="pa-privacy-protected">{t('pa.privacy.protected')}</span></strong><span>{t('pa.privacy.requests',{count:total})} · {t('pa.privacy.contacts',{count:groups.size})}</span></span>
      <span className="pa-privacy-toggle">{t(expanded?'pa.privacy.collapse':'pa.privacy.expand')}<span aria-hidden="true">{expanded?'⌃':'⌄'}</span></span>
    </button>
    {expanded&&<div className="pa-privacy-body">
      <p className="pa-privacy-intro">{t('pa.privacy.intro')}</p>
      {[...groups.entries()].map(([actorId,items])=><article className="pa-privacy-person" key={actorId}>
        <div className="pa-privacy-person-heading"><span className="pa-privacy-avatar" aria-hidden="true">{Array.from(items[0].actor_name)[0]}</span><h3>{items[0].actor_name}</h3><span>{t('pa.privacy.requests',{count:items.reduce((sum,item)=>sum+item.count,0)})}</span></div>
        <p className="pa-privacy-reason">{items[0].reason}</p>
        <details className="pa-privacy-evidence"><summary>{t('pa.privacy.evidence')}</summary><ol>{items.map(item=><li key={item.id}><p>{item.reason}</p><Link to={`/chat/${encodeURIComponent(item.conversation_id)}?message_id=${encodeURIComponent(item.source_message_id)}`} state={{personalAgentReturn:true}}>{t('pa.privacy.source')}<span aria-hidden="true"> ↗</span></Link>{item.count>1&&<span className="pa-privacy-repeat">{t('pa.privacy.requests',{count:item.count})}</span>}</li>)}</ol></details>
        <div className="pa-privacy-actions"><button type="button" disabled={respond.isPending} onClick={()=>respond.mutate({items,action:'dismiss'})}>{t('pa.privacy.dismiss')}</button>
          <details className="pa-privacy-options"><summary>{t('pa.privacy.options')}</summary><div><p>{t('pa.privacy.optionsHint')}</p><button type="button" disabled={respond.isPending} onClick={()=>respond.mutate({items,action:'misunderstanding'})}>{t('pa.privacy.misunderstanding')}</button><button type="button" className="pa-privacy-block" disabled={respond.isPending} onClick={()=>respond.mutate({items,action:'block'})}>{t('pa.privacy.block')}</button></div></details>
        </div>
      </article>)}
      {respond.isPending&&<p className="pa-privacy-feedback" role="status">{t('pa.privacy.saving')}</p>}
      {feedback&&<p className="pa-privacy-feedback" role="status">{feedback}</p>}
      {respond.isError&&<p className="pa-error" role="alert">{t('pa.privacy.error')}</p>}
    </div>}
  </section>;
}
