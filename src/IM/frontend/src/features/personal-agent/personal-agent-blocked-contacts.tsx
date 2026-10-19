import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../i18n';
import { getBlockedPersonalContacts, unblockPersonalContact } from './personal-agent-api';

/** Manage person-level restrictions without hiding the evidence behind another dialog. */
export function PersonalAgentBlockedContacts({bindingId}: {bindingId: string}) {
  const {t} = useTranslation();
  const cache = useQueryClient();
  const contacts = useQuery({queryKey:['personal-agent',bindingId,'blocked-contacts'],queryFn:getBlockedPersonalContacts});
  const unblock = useMutation({mutationFn:unblockPersonalContact,onSuccess:()=>cache.invalidateQueries({queryKey:['personal-agent']})});
  return <section className="im-agent-card pa-blocked-contacts" aria-label={t('pa.blocked.title')}>
    <div><h3 className="im-agent-card-title">{t('pa.blocked.title')}{contacts.data && <span className="pa-blocked-count">{contacts.data.items.length}</span>}</h3>
      <p className="im-agent-card-sub">{t('pa.blocked.help')}</p></div>
    {contacts.isPending && <p role="status" className="im-agent-field-help">{t('pa.blocked.loading')}</p>}
    {contacts.isError && <p role="alert" className="pa-error">{t('pa.configuration.loadError')} <button type="button" onClick={()=>void contacts.refetch()}>{t('pa.configuration.retry')}</button></p>}
    {contacts.data?.items.length===0 && <p className="pa-blocked-empty">{t('pa.blocked.empty')}</p>}
    {contacts.data?.items.map(person=><article key={person.actor_id} className="pa-blocked-person">
      <div className="pa-blocked-heading"><span className="pa-privacy-avatar" aria-hidden="true">{person.actor_name.slice(0,1)}</span><strong>{person.actor_name}</strong>
        <button className="im-btn im-btn-secondary" type="button" disabled={unblock.isPending} onClick={()=>unblock.mutate(person.actor_id)}>{t(unblock.isPending&&unblock.variables===person.actor_id?'pa.blocked.unblocking':'pa.blocked.unblock')}</button></div>
      <p className="pa-privacy-reason">{person.reason}</p>
      <details className="pa-privacy-evidence"><summary>{t('pa.privacy.evidence')}</summary><ol>{person.evidence.map(record=><li key={record.id}><p>{record.reason}</p>
        {record.message_id && <Link to={`/chat/${encodeURIComponent(record.conversation_id)}?message_id=${encodeURIComponent(record.message_id)}`}>{t(record.original?'pa.privacy.source':'pa.blocked.notice')}<span aria-hidden="true"> ↗</span></Link>}
        {!record.original && <p className="im-agent-field-help">{t('pa.blocked.privateSource')}</p>}
      </li>)}</ol></details>
    </article>)}
    {unblock.isSuccess && <p role="status" className="im-agent-field-help">{t('pa.blocked.restored')}</p>}
    {unblock.isError && <p role="alert" className="pa-error">{t('pa.configuration.saveError')}</p>}
  </section>;
}
