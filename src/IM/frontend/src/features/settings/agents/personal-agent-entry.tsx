import { useQuery } from '@tanstack/react-query';
import { useTranslation } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';
import { getPersonalAgent, type PersonalAgentState } from '../../personal-agent/personal-agent-api';
import type { AgentRowProps } from './agent-row';
import { AgentLifecycleRow as AgentRow } from './agent-lifecycle';

export function usePersonalAgentEntry() {
  const self = useAuthStore(s => s.user?.id);
  return useQuery({queryKey:['personal-agent',self],queryFn:getPersonalAgent,enabled:!!self,retry:false,refetchInterval:3000});
}

export function configuredPersonalAgent(state?: PersonalAgentState) {
  return !state?.creation && state?.binding?.status === 'active' ? state.binding : null;
}

/** One owner entry shared by the list and detail/create navigation rails. */
export function PersonalAgentEntry({state, failed, search, agent, isMobile, isActive = false, onRetry, onSelect}: {
  state?: PersonalAgentState; failed: boolean; search: string; agent?: AgentRowProps['agent']; isMobile: boolean; isActive?: boolean; onRetry: () => void; onSelect: (id: string) => void;
}) {
  const {t} = useTranslation();
  const self = useAuthStore(s => s.user?.id);
  const binding = configuredPersonalAgent(state);
  const matches = binding && `${binding.display_name} ${binding.agent_id} ${t('pa.label')} ${agent?.description ?? ''}`.toLowerCase().includes(search.trim().toLowerCase());
  return <>
    {failed && <div className="agents-pa-feedback" role="status"><span>{t('pa.retry')}</span><button onClick={onRetry} type="button">{t('agents.retry')}</button></div>}
    {state?.creation && <p className="agents-pa-feedback">{t('agents.paSettingUp')}</p>}
    {matches && <section className="agents-pa-section" aria-label={t('pa.create')}>
      <h2>{t('pa.create')}</h2>
      <AgentRow agent={{...agent, agent_id: binding.agent_id, display_name: binding.display_name, description: agent?.description ?? '', role: 'personal', owner_id: agent?.owner_id ?? self}} nodes={[]} isActive={isActive} isMobile={isMobile} onSelect={onSelect} />
    </section>}
  </>;
}
