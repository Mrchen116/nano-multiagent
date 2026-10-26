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
export function AgentLifecycleChatNotice({agentId, name}: {agentId:string; name:string}) {
  const lifecycle = useAgentLifecycle(agentId);
  const l = useLabels();
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
export function AgentLifecycleAction({lifecycle, canManage, name}: {lifecycle:Lifecycle; canManage:boolean; name?:string}) {
  const l = useLabels();
  if (!canManage) return null;
  const state = lifecycle.query.data;
  const action = state?.desired === 'enabled' ? 'disable' : state?.observed === 'stop_unconfirmed' ? 'retry' : state && confirmedDisabled(state) ? 'enable' : null;
  const label = lifecycle.mutation.isPending ? l('提交中…','Submitting…') : action === 'disable' ? l('停用','Disable') : action === 'retry' ? l('重试停止','Retry stop') : action === 'enable' ? l('启用','Enable') : state ? l('停止中…','Stopping…') : l('读取状态…','Loading state…');
  return <button type="button" className={`im-settings-action im-agent-lifecycle-action ${action === 'retry' ? 'danger' : ''}`} disabled={!action || lifecycle.mutation.isPending || lifecycle.query.isError} aria-label={name ? `${label} ${name}` : label} onClick={() => action && lifecycle.mutation.mutate(action)}>{label}</button>;
}
export function AgentLifecycleStatus({lifecycle, online, compact = false}: {lifecycle:Lifecycle; online:boolean; compact?:boolean}) {
  const l = useLabels();
  const state = lifecycle.query.data;
  const failed = state?.observed === 'stop_unconfirmed';
  const disabled = state && confirmedDisabled(state);
  const stopping = state?.desired === 'disabled' && !disabled;
  const title = failed ? l('停止未确认','Stop unconfirmed') : disabled ? l('已停用','Disabled') : stopping ? l('停止中','Stopping') : state?.observed === 'enabling' ? l('启用中','Enabling') : l('已启用','Enabled');
  const detail = failed ? l('仍禁止新工作。请重试停止。','New work remains blocked. Retry stopping.') : disabled ? l('启用后只接收新工作，旧任务仍暂停。','Enabling allows new work; old tasks remain paused.') : stopping ? online ? l('正在停止全部受管执行，尚未确认停止。','Stopping managed execution; stop is not confirmed yet.') : l('已请求停用，等待节点确认。','Disable requested; waiting for the node to confirm.') : state && state.revision > 1 ? l('可接收新工作，旧任务仍暂停。','Ready for new work; old tasks remain paused.') : '';
  const error = lifecycle.mutation.error ?? lifecycle.query.error;
  const showState = state && (state.desired !== 'enabled' || state.observed !== 'enabled');
  // Reserve the extra row for transitions, disabled state, and failures.
  if (!error && !showState) return null;
  if (compact) return <span className={`im-agent-lifecycle-badge ${failed || stopping || error ? 'warning' : ''}`} aria-live="polite" title={error ? l('状态未确认，打开详情重试。','State not confirmed. Open details to retry.') : detail}>{error ? l('状态未确认','State unknown') : title}</span>;
  return <div className={`im-agent-lifecycle-status ${failed || stopping ? 'warning' : ''}`} aria-live="polite">
    {showState && <><strong>{title}</strong>{!compact && detail && <span>{detail}</span>}{failed && !compact && state.error_detail && <span>{state.error_detail}</span>}</>}
    {error && <span role="alert">{l('状态未确认，请刷新后重试。','State not confirmed. Refresh and try again.')}</span>}
    {lifecycle.query.isError && <button type="button" className="im-settings-action" onClick={() => void lifecycle.query.refetch()}>{l('刷新状态','Refresh state')}</button>}
  </div>;
}
/** Keep navigation rows quiet; lifecycle controls live in the Agent detail. */
export function AgentLifecycleRow(props: AgentRowProps) {
  const lifecycle = useAgentLifecycle(props.agent.agent_id);
  return <div className="im-agent-lifecycle-row"><AgentRow {...props} statusBadge={<AgentLifecycleStatus lifecycle={lifecycle} online={props.agent.node_status === 'online'} compact />} /></div>;
}
