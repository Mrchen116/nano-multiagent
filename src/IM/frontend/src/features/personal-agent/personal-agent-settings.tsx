import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from '../../i18n';
import { useAuthStore } from '../auth/auth-store';
import { listConversations } from '../chat/chat-api';
import { getPersonalAgentSettings, updatePersonalAgentPolicy } from './personal-agent-api';
import './personal-agent.css';
import { PersonalAgentBlockedContacts } from './personal-agent-blocked-contacts';

/** Keep PA-only access settings alongside the shared Agent configuration. */
export function PersonalAgentSettings({ agentId, readOnly = false }: { agentId: string; readOnly?: boolean }) {
  const { t } = useTranslation();
  const ownerId = useAuthStore(s => s.user?.id);
  const cache = useQueryClient();
  const [search, setSearch] = useState('');
  const state = useQuery({ queryKey: ['settings', 'agents', agentId, 'pa-policy', ownerId], queryFn: ({signal}) => getPersonalAgentSettings(signal), staleTime: 0 });
  const chats = useQuery({ queryKey: ['chat', 'conversations'], queryFn: listConversations });
  const refresh = async () => {await Promise.all([cache.invalidateQueries({ queryKey: ['personal-agent'] }), cache.invalidateQueries({queryKey: ['settings','agents',agentId,'pa-policy']})]);};
  const blocked = readOnly || state.isFetching || state.isError || !state.isFetchedAfterMount;
  const update = useMutation({
    mutationFn: (excluded: string[]) => {if (blocked) throw new Error(t("agents.settings.refreshing")); return updatePersonalAgentPolicy({ expected_revision: state.data!.policy!.revision, excluded_conversation_ids: excluded });},
    onSettled: refresh,
  });
  const binding = state.data?.binding;
  const policy = state.data?.policy;
  if (state.isError) return <p role="alert" className="pa-error">{t('pa.configuration.loadError')} <button type="button" onClick={() => void state.refetch()}>{t('pa.configuration.retry')}</button></p>;
  if (!binding || binding.agent_id !== agentId || !policy) return null;
  const visibleChats = (chats.data ?? []).filter(c => c.id !== binding.conversation_id && c.title.toLowerCase().includes(search.toLowerCase()));
  return <>
    <section className="im-agent-card pa-access-settings">
      <div><h3 className="im-agent-card-title">{t('pa.configuration.accessTitle')}</h3><p className="im-agent-card-sub">{t('pa.configuration.accessHelp')}</p></div>
      <details><summary>{t('pa.configuration.exclusions', { count: policy.excluded_conversation_ids.length })}</summary>
        <label className="im-agent-field">{t('pa.configuration.search')}<input className="im-input" type="search" value={search} onChange={e => setSearch(e.target.value)} /></label>
        {chats.isPending && <p role="status">{t('pa.configuration.loading')}</p>}
        {chats.isError ? <p role="alert" className="pa-error">{t('pa.configuration.loadError')} <button type="button" onClick={() => void chats.refetch()}>{t('pa.configuration.retry')}</button></p> : <div className="pa-source-list">{visibleChats.map(c => <label key={c.id}><input type="checkbox" checked={policy.excluded_conversation_ids.includes(c.id)} disabled={blocked || update.isPending} onChange={e => update.mutate(e.target.checked ? [...policy.excluded_conversation_ids, c.id] : policy.excluded_conversation_ids.filter(id => id !== c.id))} />{c.title}</label>)}</div>}
        {chats.isSuccess && !visibleChats.length && <p className="im-agent-field-help">{t('pa.configuration.noChats')}</p>}
      </details>
      <p className="im-agent-field-help">{t('pa.configuration.immediate')}</p>
      {update.isPending && <p role="status">{t('pa.configuration.saving')}</p>}
      {update.isSuccess && <p role="status" className="im-agent-field-help">{t('pa.configuration.saved')}</p>}
      {update.isError && <p role="alert" className="pa-error">{t('pa.configuration.saveError')}</p>}
    </section>
    <PersonalAgentBlockedContacts bindingId={binding.binding_id} agentId={agentId} readOnly={readOnly} />
  </>;
}
