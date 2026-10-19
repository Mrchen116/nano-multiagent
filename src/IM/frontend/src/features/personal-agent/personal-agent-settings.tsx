import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from '../../i18n';
import { useAuthStore } from '../auth/auth-store';
import { listConversations } from '../chat/chat-api';
import { listNodes } from '../settings/agents/im-agent-config-api';
import { getPersonalAgent, restorePersonalAgent, updatePersonalAgentPolicy } from './personal-agent-api';
import './personal-agent.css';

/** Keep PA-only access settings alongside the shared Agent configuration. */
export function PersonalAgentSettings({ agentId, hasUnsavedChanges = false }: { agentId: string; hasUnsavedChanges?: boolean }) {
  const { t } = useTranslation();
  const ownerId = useAuthStore(s => s.user?.id);
  const cache = useQueryClient();
  const [search, setSearch] = useState('');
  const [nodeId, setNodeId] = useState('');
  const state = useQuery({ queryKey: ['personal-agent', ownerId], queryFn: getPersonalAgent });
  const chats = useQuery({ queryKey: ['chat', 'conversations'], queryFn: listConversations });
  const nodes = useQuery({ queryKey: ['settings', 'nodes'], queryFn: listNodes });
  const refresh = () => cache.invalidateQueries({ queryKey: ['personal-agent'] });
  const update = useMutation({
    mutationFn: (excluded: string[]) => updatePersonalAgentPolicy({ expected_revision: state.data!.policy!.revision, excluded_conversation_ids: excluded }),
    onSettled: refresh,
  });
  const restore = useMutation({
    mutationFn: () => restorePersonalAgent(nodeId),
    onSuccess: async () => { setNodeId(''); await Promise.all([refresh(), cache.invalidateQueries({ queryKey: ['settings', 'agents', agentId] })]); },
  });
  const binding = state.data?.binding;
  const policy = state.data?.policy;
  if (state.isError) return <p role="alert" className="pa-error">{t('pa.configuration.loadError')} <button type="button" onClick={() => void state.refetch()}>{t('pa.configuration.retry')}</button></p>;
  if (!binding || binding.agent_id !== agentId || !policy) return null;
  const alternatives = (nodes.data ?? []).filter(n => n.node_id !== binding.node_id && n.status === 'online');
  const visibleChats = (chats.data ?? []).filter(c => c.id !== binding.conversation_id && c.title.toLowerCase().includes(search.toLowerCase()));
  return <>
    <section className="im-agent-card pa-access-settings">
      <div><h3 className="im-agent-card-title">{t('pa.configuration.accessTitle')}</h3><p className="im-agent-card-sub">{t('pa.configuration.accessHelp')}</p></div>
      <details><summary>{t('pa.configuration.exclusions', { count: policy.excluded_conversation_ids.length })}</summary>
        <label className="im-agent-field">{t('pa.configuration.search')}<input className="im-input" type="search" value={search} onChange={e => setSearch(e.target.value)} /></label>
        {chats.isPending && <p role="status">{t('pa.configuration.loading')}</p>}
        {chats.isError ? <p role="alert" className="pa-error">{t('pa.configuration.loadError')} <button type="button" onClick={() => void chats.refetch()}>{t('pa.configuration.retry')}</button></p> : <div className="pa-source-list">{visibleChats.map(c => <label key={c.id}><input type="checkbox" checked={policy.excluded_conversation_ids.includes(c.id)} disabled={update.isPending} onChange={e => update.mutate(e.target.checked ? [...policy.excluded_conversation_ids, c.id] : policy.excluded_conversation_ids.filter(id => id !== c.id))} />{c.title}</label>)}</div>}
        {chats.isSuccess && !visibleChats.length && <p className="im-agent-field-help">{t('pa.configuration.noChats')}</p>}
      </details>
      <p className="im-agent-field-help">{t('pa.configuration.immediate')}</p>
      {update.isPending && <p role="status">{t('pa.configuration.saving')}</p>}
      {update.isSuccess && <p role="status" className="im-agent-field-help">{t('pa.configuration.saved')}</p>}
      {update.isError && <p role="alert" className="pa-error">{t('pa.configuration.saveError')}</p>}
    </section>
    {alternatives.length > 0 && <section className="im-agent-card pa-access-settings"><details><summary>{t('pa.configuration.moveTitle')}</summary>
      <p className="im-agent-card-sub">{t('pa.configuration.moveHelp')}</p>
      <label className="im-agent-field">{t('pa.configuration.computer')}<select className="im-input" value={nodeId} onChange={e => setNodeId(e.target.value)}><option value="">{t('pa.configuration.chooseComputer')}</option>{alternatives.map(n => <option key={n.node_id} value={n.node_id}>{n.node_name}</option>)}</select></label>
      <button className="im-btn im-btn-secondary" type="button" disabled={!nodeId || restore.isPending || hasUnsavedChanges} onClick={() => restore.mutate()}>{t('pa.configuration.move')}</button>
      {hasUnsavedChanges && <p className="im-agent-field-help">{t('pa.configuration.saveBeforeMove')}</p>}
      {restore.isSuccess && <p role="status">{t('pa.configuration.saved')}</p>}{restore.isError && <p role="alert" className="pa-error">{t('pa.configuration.saveError')}</p>}
    </details></section>}
  </>;
}
