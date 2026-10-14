import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from '../../../i18n';
import { subscribeUserStream } from '../../../realtime/user-stream';
import { listNodes, updateNode, type NodeSettingsProfile } from '../im-settings-api';
import { NodeUpdatePanel, nodeUpdateActive, nodeUpdateNeedsRecovery, nodeUpdateSwitching } from './node-update-panel';
import { NodeDrawer, NodeIcon } from './node-surface';
import { NodeDetails } from './node-details';
import { NodeConnectGuide } from './node-connect-guide';
import './nodes-page.css';

import { computerName, computerVersion, lastSeenTime, NodeStatus } from './node-display';

/** Manage owned computers while preserving update and realtime query ownership. */
export function NodesPage() {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const { hash } = useLocation();
  const returnFocus = useRef<HTMLElement | null>(null);
  const [panel, setPanel] = useState<{ kind: 'detail' | 'connect' | 'recovery'; id?: string } | null>(null);
  const query = useQuery({ queryKey: ['settings', 'nodes'], queryFn: listNodes,
    refetchInterval: query => query.state.data?.some(n => nodeUpdateActive(n.update)) ? 2000 : 60000 });
  const nodes = query.data ?? [];
  const selected = nodes.find(n => n.node_id === panel?.id);
  const mutation = useMutation({
    mutationFn: ({ node, alias }: { node: NodeSettingsProfile; alias: string }) => updateNode(node.node_id, {
      alias, relay_enabled: node.relay_enabled, reporting_enabled: node.reporting_enabled
    }),
    onSuccess: async (saved) => {
      client.setQueryData<NodeSettingsProfile[]>(['settings', 'nodes'], rows => rows?.map(n => n.node_id === saved.node_id ? { ...n, alias: saved.alias } : n));
      await Promise.all([
        client.invalidateQueries({ queryKey: ['settings', 'nodes'] }),
        client.invalidateQueries({ queryKey: ['settings', 'agents', 'nodes-status'] }),
        client.invalidateQueries({ queryKey: ['chat', 'nodes'] }),
        client.invalidateQueries({ queryKey: ['contacts'] })
      ]);
    }
  });
  useEffect(() => subscribeUserStream({
    onRecovery: async () => { await client.invalidateQueries({ queryKey: ['settings', 'nodes'] }); },
    onEvent: event => {
      if (event.eventType === 'node.update_changed') { void client.invalidateQueries({ queryKey: ['settings', 'nodes'] }); return; }
      if (event.eventType !== 'node.status_changed') return;
      const p = event.payload as Partial<NodeSettingsProfile>;
      if (typeof p.node_id !== 'string' || typeof p.status !== 'string') return;
      // Only live fields change here; an open rename form owns its alias draft.
      const rows = client.getQueryData<NodeSettingsProfile[]>(['settings', 'nodes']);
      if (!rows?.some(n => n.node_id === p.node_id)) { void client.invalidateQueries({ queryKey: ['settings', 'nodes'] }); return; }
      client.setQueryData<NodeSettingsProfile[]>(['settings', 'nodes'], current => current?.map(n => n.node_id !== p.node_id ? n : {
        ...n, status: p.status!,
        last_heartbeat_at: typeof p.last_heartbeat_at === 'string' ? p.last_heartbeat_at : n.last_heartbeat_at,
        last_error: p.last_error === null || typeof p.last_error === 'string' ? p.last_error : n.last_error
      }));
    }
  }), [client]);
  useEffect(() => {
    if (hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView?.({ block: 'start' });
  }, [hash, nodes.length]);
  function open(kind: 'detail' | 'connect' | 'recovery', id?: string) {
    returnFocus.current = document.activeElement as HTMLElement;
    mutation.reset(); setPanel({ kind, id });
  }
  const online = nodes.filter(n => n.status === 'online' && !nodeUpdateSwitching(n.update) && !nodeUpdateNeedsRecovery(n.update)).length;
  const hasData = query.data !== undefined;
  return <div className="computers-page"><main className="computers-frame">
    <Link className="computers-back" to="/me" data-testid="nodes-page-back"><NodeIcon name="back"/>{t('computers.account')}</Link>
    <header className="computers-heading"><div><h1>{t('computers.title')}</h1><p>{hasData ? t('computers.summary', { count: nodes.length, total: nodes.length, online }) : t('computers.subtitle')}</p></div>
      <button className="node-button" onClick={() => open('connect')}><NodeIcon name="plus"/>{t('computers.connect')}</button>
    </header>
    {query.isPending ? <div role="status" aria-label={t('settings.nodes.loading')}><div className="node-skeleton"/><div className="node-skeleton"/></div>
      : !hasData && query.isError ? <section className="nodes-empty"><NodeIcon name="info"/><h2>{t('settings.nodes.loadFailed')}</h2><p>{t('computers.loadHelp')}</p><button className="node-button primary" onClick={() => void query.refetch()}>{t('common.retry')}</button></section>
      : nodes.length === 0 ? <section className="nodes-empty" data-testid="nodes-empty"><span className="node-computer-icon"><NodeIcon name="computer"/></span><h2>{t('computers.emptyTitle')}</h2><p>{t('computers.emptyBody')}</p><button className="node-button primary" onClick={() => open('connect')}>{t('computers.connect')}</button></section>
      : <>
        {query.isError && <div className="node-notice" role="alert"><NodeIcon name="info"/><span>{t('computers.stale')}</span><button className="node-button" onClick={() => void query.refetch()}>{t('common.retry')}</button></div>}
        <div className="computers-list-label"><span>{t('computers.connected')}</span><span>{t('computers.private')}</span></div>
        {nodes.map(node => {
          const name = computerName(node, t('computers.unnamed'));
          const offline = node.status !== 'online' && !nodeUpdateSwitching(node.update);
          return <article className={`computer-card ${offline ? 'offline' : ''}`} key={node.node_id} id={`node-${node.node_id}`}>
            <div className="computer-main"><span className="node-computer-icon"><NodeIcon name="computer"/></span>
              <div className="computer-identity"><h2><button onClick={() => open('detail', node.node_id)}>{name}</button></h2>
                <div className="computer-metadata"><NodeStatus node={node}/><span>·</span><span>{nodeUpdateNeedsRecovery(node.update) ? t('computers.lastVersion') : 'Nano'} {computerVersion(node)}</span><span>·</span><span>{t('computers.assistantCount', { count: node.agent_count })}</span></div>
              </div><button className="computer-detail-link" aria-label={t('computers.viewDetails', { name })} onClick={() => open('detail', node.node_id)}><span>{t('computers.details')}</span><NodeIcon name="next"/></button>
            </div>
            {node.update && <NodeUpdatePanel nodeId={node.node_id} update={node.update} onInstructions={() => open('recovery', node.node_id)}/>}
            {offline && !nodeUpdateNeedsRecovery(node.update) && <p className="computer-offline-note">{node.last_heartbeat_at ? t('computers.lastSeen', { time: lastSeenTime(node.last_heartbeat_at, i18n.language) }) : t('computers.noConnection')} · {t('computers.reconnect')}</p>}
          </article>;
        })}
      </>}
    <p className="computers-help"><NodeIcon name="leaf"/>{t('computers.help')}</p>
    {panel && <NodeDrawer title={t(panel.kind === 'detail' ? 'computers.detailsTitle' : panel.kind === 'recovery' ? 'computers.recoveryTitle' : 'computers.connect')} returnFocus={returnFocus} onClose={() => setPanel(null)}>
      {panel.kind === 'detail' && selected ? <NodeDetails key={selected.node_id} node={selected} pending={mutation.isPending} error={mutation.isError} save={alias => mutation.mutateAsync({ node: selected, alias })} resetError={mutation.reset}/>
        : panel.kind !== 'detail' ? <NodeConnectGuide node={panel.kind === 'recovery' ? selected : undefined} onRefresh={() => { void query.refetch(); setPanel(null); }}/>
        : <p>{t('computers.notFound')}</p>}
    </NodeDrawer>}
  </main></div>;
}
