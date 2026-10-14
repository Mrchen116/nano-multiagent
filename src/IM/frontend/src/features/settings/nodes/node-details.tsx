import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';
import { getOnboarding } from '../../onboarding/onboarding-api';
import type { NodeSettingsProfile } from '../im-settings-api';
import { computerName, computerVersion, NodeStatus } from './node-display';
import { NodeIcon } from './node-surface';
import { nodeUpdateNeedsRecovery, nodeUpdateSwitching } from './node-update-panel';

/** Edit only the alias while connection fields keep following the live node. */
export function NodeDetails({ node, pending, error, save, resetError }: {
  node: NodeSettingsProfile; pending: boolean; error: boolean;
  save(alias: string): Promise<unknown>; resetError(): void;
}) {
  const { t, i18n } = useTranslation();
  const userId = useAuthStore(s => s.user?.id);
  const query = useQuery({ queryKey: ['onboarding', userId], queryFn: getOnboarding });
  const name = computerName(node, t('computers.unnamed'));
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [empty, setEmpty] = useState(false);
  const [saved, setSaved] = useState(false);
  const canManage = node.status === 'online' && !nodeUpdateSwitching(node.update) && !nodeUpdateNeedsRecovery(node.update);
  const agents = query.data?.agents?.filter(a => a.node_id === node.node_id) ?? [];
  return <>
    <div className="node-detail-identity"><span className="node-computer-icon"><NodeIcon name="computer"/></span><div><h3>{name}</h3><NodeStatus node={node}/></div></div>
    {editing ? <form className="node-name-form" onSubmit={event => {
      event.preventDefault(); if (!canManage || pending) return;
      if (!draft.trim()) { setEmpty(true); return; }
      void save(draft.trim()).then(() => { setEditing(false); setSaved(true); }).catch(() => { /* Mutation retains the error and the input. */ });
    }}>
      <label htmlFor="computer-name">{t('computers.name')}</label>
      <input id="computer-name" autoFocus value={draft} disabled={pending} aria-invalid={empty || error} aria-describedby={empty || error ? 'computer-name-error' : undefined}
        onFocus={event => event.target.select()} onChange={event => { setDraft(event.target.value); setEmpty(false); resetError(); }}/>
      {(empty || error) && <p id="computer-name-error" className="node-form-error" role="alert">{t(empty ? 'computers.nameRequired' : 'computers.saveFailed')}</p>}
      <div className="node-field-actions"><button className="node-button" type="button" disabled={pending} onClick={() => { setEditing(false); resetError(); }}>{t('common.cancel')}</button>
        <button className="node-button primary" disabled={pending || !canManage}>{t(pending ? 'settings.nodes.saving' : 'computers.saveName')}</button></div>
    </form> : <div className="node-detail-row"><span>{t('computers.name')}</span><button className="node-button text" disabled={!canManage} onClick={() => { setDraft(name); setEditing(true); setEmpty(false); setSaved(false); resetError(); }}>{t('computers.rename')}</button></div>}
    {saved && <p className="node-save-success" role="status">{t('computers.saved')}</p>}
    {!canManage && <p className="node-drawer-note">{t(node.status !== 'online' && !nodeUpdateSwitching(node.update) && !nodeUpdateNeedsRecovery(node.update) ? 'computers.offlineManage' : 'computers.updateManage')}</p>}
    <div className="node-detail-row"><span>{t(nodeUpdateNeedsRecovery(node.update) ? 'computers.lastVersion' : 'settings.nodes.version')}</span><span>{computerVersion(node)}</span></div>
    <div className="node-detail-row"><span>{t('computers.lastOnline')}</span><span>{node.last_heartbeat_at ? new Date(node.last_heartbeat_at).toLocaleString(i18n.language) : t('computers.noConnection')}</span></div>
    <h4 className="node-section-title">{t('computers.assistantsHere')}</h4>
    {query.isPending ? <p className="node-muted">{t('common.loading')}</p> : query.isError ? <div className="node-inline-error"><p>{t('computers.assistantsFailed')}</p><button className="node-button" onClick={() => void query.refetch()}>{t('common.retry')}</button></div>
      : agents.length ? agents.map(agent => <div className="node-detail-row" key={agent.agent_id}><span className="node-assistant"><span className="node-assistant-avatar">{agent.display_name.slice(0, 1)}</span>{agent.display_name}</span></div>)
      : <p className="node-muted">{t('computers.noAssistants')}</p>}
    {canManage ? <Link className="node-button node-create" to={`/settings/nodes/${encodeURIComponent(node.node_id)}/agents/new`}><NodeIcon name="plus"/>{t('computers.createAssistant')}</Link>
      : <button className="node-button node-create" disabled><NodeIcon name="plus"/>{t('computers.createAssistant')}</button>}
    <details className="node-diagnostics"><summary>{t('computers.diagnostics')}</summary>
      <div className="node-detail-row"><span>{t('settings.nodes.version')}</span><code>{node.update?.current?.version || node.version || '—'}</code></div>
      <div className="node-detail-row"><span>{t('computers.id')}</span><code>{node.node_id}</code></div>
      <div className="node-detail-row"><span>{t('settings.nodes.heartbeat')}</span><span>{node.last_heartbeat_at ? new Date(node.last_heartbeat_at).toLocaleString(i18n.language) : '—'}</span></div>
      <div className="node-detail-row"><span>{t('computers.connectionLog')}</span><code data-testid={`node-last-error-${node.node_id}`}>{node.last_error || t('computers.noError')}</code></div>
    </details>
  </>;
}
