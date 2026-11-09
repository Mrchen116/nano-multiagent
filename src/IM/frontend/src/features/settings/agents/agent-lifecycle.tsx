import type { AgentLifecycleSnapshot } from '@nano/product-contracts/agent-lifecycle';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useTranslation } from '../../../i18n';
import { subscribeUserStream } from '../../../realtime/user-stream';
import { authFetchJson } from '../../auth/auth-fetch';
import { useAuthStore } from '../../auth/auth-store';
import { AgentRow, type AgentRowProps } from './agent-row';

const path = (id: string) => `/im/v1/agents/${encodeURIComponent(id)}/lifecycle`;
const read = (id: string, signal?: AbortSignal) => authFetchJson<AgentLifecycleSnapshot>(path(id), { signal }, 'Agent lifecycle');

/** Keep immediate lifecycle intent separate from editable configuration and device presence. */
export function useAgentLifecycle(agentId: string) {
  const self = useAuthStore(s => s.user?.id);
  const client = useQueryClient();
  const key = ['agent-lifecycle', self, agentId];
  const query = useQuery({ queryKey: key, queryFn: ({signal}) => read(agentId, signal), enabled: !!agentId, retry: false, refetchInterval: 3000 });
  useEffect(() => subscribeUserStream({
    onEvent: event => {
      if (event.eventType === 'agent.lifecycle.changed' && event.payload.agent_id === agentId) void client.invalidateQueries({queryKey: ['agent-lifecycle', self, agentId]});
    },
    onRecovery: async () => { await client.invalidateQueries({queryKey: ['agent-lifecycle', self, agentId]}); }
  }), [agentId, self, client]);
  const mutation = useMutation({
    onMutate: () => client.cancelQueries({queryKey: key}),
    mutationFn: async (action: 'disable' | 'enable' | 'retry') => {
      const current = query.data;
      if (!current) throw new Error('Agent state unavailable');
      const request_id = crypto.randomUUID();
      if (action === 'retry') return authFetchJson<AgentLifecycleSnapshot>(path(agentId) + '/retry', {method: 'POST', body: JSON.stringify({request_id})}, 'Retry stop');
      const submit = (revision: number) => authFetchJson<AgentLifecycleSnapshot>(path(agentId), {method:'PUT', body:JSON.stringify({enabled:action === 'enable', request_id, expected_revision:revision})}, 'Agent lifecycle');
      try { return await submit(current.revision); }
      catch (error) {
        if ((error as {status?:number}).status !== 409) throw error;
        const latest = await read(agentId);
        client.setQueryData(key, latest);
        // A concurrent enable must never reverse the user's emergency stop intent.
        if (action === 'disable') return latest.desired === 'disabled' ? latest : submit(latest.revision);
        throw error;
      }
    },
    onSuccess: async value => {
      await client.cancelQueries({queryKey: key});
      client.setQueryData<AgentLifecycleSnapshot>(key, current => current && current.revision > value.revision ? current : value);
    },
    onError: () => { void client.invalidateQueries({queryKey: key}); }
  });
  return {query, mutation};
}
type Lifecycle = ReturnType<typeof useAgentLifecycle>;
/** Explain retained chat messages without offering lifecycle changes in chat. */
export function AgentLifecycleChatNotice({agentId, name, deleted = false}: {agentId:string; name:string; deleted?:boolean}) {
  const lifecycle = useAgentLifecycle(deleted ? "" : agentId);
  const l = useLabels();
  if (deleted) return <div className="chat-observer-notice" role="status"><strong>{name} · {l('Agent 已删除', 'Agent deleted')}</strong></div>;
  if (lifecycle.query.data?.desired !== 'disabled') return null;
  return <div className="chat-observer-notice" role="status"><strong>{name} · {l('不处理新消息','Not processing new messages')}</strong><span>{l('消息会保留，但该 Agent 不会处理。','Messages are kept, but this Agent will not process them.')}</span></div>;
}
function useLabels() {
  const { i18n } = useTranslation();
  return (zh: string, en: string) => i18n.language.startsWith('zh') ? zh : en;
}
function confirmedDisabled(state: AgentLifecycleSnapshot) {
  return state.desired === 'disabled' && state.observed === 'disabled' && state.applied_revision === state.revision;
}
export function AgentLifecycleAction({lifecycle, canManage, online, name}: {lifecycle:Lifecycle; canManage:boolean; online:boolean; name?:string}) {
  const l = useLabels();
  if (!canManage) return null;
  const state = lifecycle.query.data;
  const action = state?.desired === 'enabled' ? 'disable' : state && confirmedDisabled(state) ? 'enable'
    : online && state?.observed === 'stop_unconfirmed' && state.error_code !== 'node_upgrade_required' ? 'retry' : null;
  const disabling = l('正在停用…','Disabling…');
  const label = lifecycle.mutation.isPending
    ? lifecycle.mutation.variables === 'enable' ? l('正在启用…','Enabling…') : disabling
    : action === 'disable' ? l('停用 Agent','Disable Agent') : action === 'retry' ? l('重试停用','Retry disabling') : action === 'enable' ? l('启用 Agent','Enable Agent')
      : state ? disabling : l('读取状态…','Loading state…');
  return <button type="button" className={`im-settings-action im-agent-lifecycle-action ${action === 'retry' ? 'danger' : ''}`} disabled={!action || lifecycle.mutation.isPending || lifecycle.query.isError} aria-label={name ? `${label} ${name}` : label} onClick={() => action && lifecycle.mutation.mutate(action)}>{label}</button>;
}
export function AgentLifecycleStatus({lifecycle, online, compact = false}: {lifecycle:Lifecycle; online:boolean; compact?:boolean}) {
  const l = useLabels();
  const state = lifecycle.query.data;
  const failed = state?.observed === 'stop_unconfirmed';
  const disabled = state && confirmedDisabled(state);
  const stopping = state?.desired === 'disabled' && !disabled;
  const error = lifecycle.mutation.error ?? lifecycle.query.error;
  const disabledLabel = l('已停用','Disabled');
  const disabledDetail = l('重新启用后可以接收新工作，旧任务继续暂停。','Re-enabling allows new work. Previous tasks stay paused.');
  if (compact) return disabled && !error ? <span className="im-agent-lifecycle-badge" aria-live="polite" title={disabledDetail}>{disabledLabel}</span> : null;
  const detail = !stopping ? '' : !online
    ? l('电脑离线，联网后会继续停用。','The computer is offline. Disabling will continue when it reconnects.')
    : state.error_code === 'node_upgrade_required' ? l('请更新电脑上的 Nano 后再停用。','Update Nano on the computer to finish disabling.')
      : failed && !lifecycle.mutation.isPending ? l('停用还没完成。','Disabling did not finish.') : '';
  if (!disabled && !detail && !error) return null;
  return <div className={`im-agent-lifecycle-status ${stopping ? 'im-agent-lifecycle-feedback warning' : ''}`} aria-live="polite">
    {disabled && !error && <><strong>{disabledLabel}</strong><span>{disabledDetail}</span></>}
    {detail && <span>{detail}</span>}
    {error && <span role="alert">{lifecycle.query.isError
      ? l('无法读取 Agent 状态，请刷新后重试。','Could not read the Agent status. Refresh and try again.')
      : l('操作未完成，请重试。','The action did not finish. Try again.')}</span>}
    {lifecycle.query.isError && <button type="button" className="im-settings-action" onClick={() => void lifecycle.query.refetch()}>{l('刷新状态','Refresh state')}</button>}
  </div>;
}
/** Keep navigation rows quiet; lifecycle controls live in the Agent detail. */
export function AgentLifecycleRow(props: AgentRowProps) {
  const lifecycle = useAgentLifecycle(props.agent.agent_id);
  return <div className="im-agent-lifecycle-row"><AgentRow {...props} statusBadge={<AgentLifecycleStatus lifecycle={lifecycle} online={props.agent.node_status === 'online'} compact />} /></div>;
}
