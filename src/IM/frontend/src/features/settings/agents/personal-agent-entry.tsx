import { useQuery } from '@tanstack/react-query';
import { useTranslation } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';
import { Avatar, colorForAgent, initialsOf } from '../../chat/components/avatar';
import { getPersonalAgent, type PersonalAgentState } from '../../personal-agent/personal-agent-api';

export function usePersonalAgentEntry() {
  const self = useAuthStore(s => s.user?.id);
  return useQuery({queryKey:['personal-agent',self],queryFn:getPersonalAgent,enabled:!!self,retry:false,refetchInterval:3000});
}

export function configuredPersonalAgent(state?: PersonalAgentState) {
  return !state?.creation && state?.binding?.status === 'active' ? state.binding : null;
}

/** One owner entry shared by the list and detail/create navigation rails. */
export function PersonalAgentEntry({state, failed, search, searchText = "", onRetry, onSelect}: {
  state?: PersonalAgentState; failed: boolean; search: string; searchText?: string; onRetry: () => void; onSelect: (id: string) => void;
}) {
  const {t} = useTranslation();
  const binding = configuredPersonalAgent(state);
  const matches = binding && `${binding.display_name} ${binding.agent_id} ${t('pa.label')} ${searchText}`.toLowerCase().includes(search.trim().toLowerCase());
  return <>
    {failed && <div className="agents-pa-feedback" role="status"><span>{t('pa.retry')}</span><button onClick={onRetry} type="button">{t('agents.retry')}</button></div>}
    {state?.creation && <p className="agents-pa-feedback">{t('agents.paSettingUp')}</p>}
    {matches && <section className="agents-pa-section" aria-label={t('pa.create')}>
      <h2>{t('pa.create')}</h2>
      <button type="button" className="agents-pa-entry" onClick={() => onSelect(binding.agent_id)} aria-label={`${t('agents.configure')} ${binding.display_name}`}>
        <Avatar initials={initialsOf(binding.display_name)} color={colorForAgent(binding)} size={36} />
        <span className="agents-pa-identity"><strong>{binding.display_name}</strong><small>{t('pa.label')}</small></span>
        <span className="agents-pa-action">{t('agents.configure')} ›</span>
      </button>
    </section>}
  </>;
}
