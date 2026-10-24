import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from '../../../i18n';
import { getAgentSettingsSection, type AgentPlugins, manageAgentPlugin, type PluginCommand, type PluginText } from './im-agent-config-api';

import {SettingsReadNotice} from './settings-read-notice';

/** Installed bundles have their own lifecycle, including plugins that contribute no tools. */
export function AgentPluginsPanel({agentId, readOnly = false}: {agentId: string; readOnly?: boolean}) {
  const {t, i18n} = useTranslation();
  const client = useQueryClient();
  const key = ['settings', 'agents', agentId, 'plugins'];
  const [confirm, setConfirm] = useState<string>();
  const query = useQuery({queryKey: key, queryFn: ({signal}) => getAgentSettingsSection<AgentPlugins>(agentId, "plugins", signal), retry: false,
    refetchInterval: state => state.state.data?.data?.pending ? 1000 : false});
  const mutation = useMutation({mutationFn: (command: PluginCommand) => {
      if (readOnly || query.isFetching || query.isError || query.data?.source !== 'current' || query.data.data?.pending) throw new Error(t('agents.settings.refreshing'));
      return manageAgentPlugin(agentId, command);
    },
    onSuccess: () => {setConfirm(undefined);},
    onSettled: () => {void client.invalidateQueries({queryKey:key});},
  });
  const data = query.data?.data;
  const blocked = readOnly || query.data?.source !== 'current' || !!data?.pending || mutation.isPending || query.isFetching || query.isError || mutation.isError;
  const local = (text: PluginText) => typeof text === 'string' ? text : text[i18n.language] ?? text[i18n.language.split('-')[0]] ?? text.en ?? Object.values(text)[0];
  const refresh = () => {mutation.reset(); void query.refetch();};
  return <section className="im-settings-plugins min-w-0" aria-label={t('agents.plugins.title')}>
    <div className="im-settings-list-header">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">{t('agents.plugins.title')}</h3>
          {data && <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs tabular-nums text-slate-500">{data.entries.length}</span>}
        </div>
      </div>
      <button type="button" className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-md px-2 text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--im-accent)] disabled:opacity-40" onClick={refresh} disabled={query.isFetching}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 7a7 7 0 0 1 11.5-1L20 9M4 15l2.4 3A7 7 0 0 0 17.9 17"/></svg>
        {t('agents.plugins.refresh')}
      </button>
    </div>
    <SettingsReadNotice read={query.data} />
    {query.isPending && <p role="status" className="im-settings-empty">{t('agents.plugins.loading')}</p>}
    {(query.isError || mutation.isError || data?.error) && <div role="alert" className="im-settings-feedback">
      <p className="font-semibold">{t(query.isError ? 'agents.plugins.unavailable' : 'agents.plugins.operationFailed')}</p>
      <p className="mt-1 break-words">{query.error?.message ?? mutation.error?.message ?? data?.error}</p>
    </div>}
    {!query.isPending && !query.isError && data?.entries.length === 0 && <div className="im-settings-empty">
      <h4 className="font-semibold">{t('agents.plugins.empty')}</h4>
    </div>}
    {data?.entries.map(plugin => {
      const title = local(plugin.display_name);
      const pending = data.pending?.target === plugin.name ? data.pending : undefined;
      return <article key={plugin.name} className="im-settings-plugin min-w-0">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 17.5h7M17.5 14v7" strokeLinecap="round"/></svg>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <h4 className="text-sm font-semibold [overflow-wrap:anywhere]">{title}</h4>
              {plugin.version && <span className="text-xs text-slate-400">v{plugin.version}</span>}
            </div>
            <p className="mt-1 text-sm leading-6 text-slate-500 [overflow-wrap:anywhere]">{local(plugin.description)}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
            <button type="button" role="switch" aria-checked={plugin.enabled} aria-label={title} disabled={blocked}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--im-accent)] disabled:cursor-not-allowed disabled:opacity-45 ${plugin.enabled ? 'bg-[var(--im-accent)]' : 'bg-slate-300'}`}
            onClick={() => mutation.mutate({action:'set_bundle',target:plugin.name,enabled:!plugin.enabled})}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${plugin.enabled ? 'left-0.5 translate-x-5' : 'left-0.5'}`}/>
          </button>
            <span className={`text-[11px] ${plugin.state === 'failed' ? 'text-rose-700' : 'text-slate-500'}`}>{t(`agents.plugins.${plugin.state}`)}</span>
          </div>
        </div>
        {pending && <p role="status" className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{t(pending.phase === 'waiting' ? 'agents.plugins.waiting' : 'agents.plugins.applying')}</p>}
        <details className="mt-2 sm:ml-12">
          <summary className="w-fit cursor-pointer py-1 text-xs text-slate-500 hover:text-[var(--im-accent)]">{t('agents.plugins.details')}</summary>
          <div className="mt-3 grid min-w-0 gap-3 text-xs leading-5">
            {plugin.name !== title && <p className="break-all font-mono text-slate-500">{plugin.name}</p>}
            {plugin.rows.length > 0 && <div><p className="font-semibold">{t('agents.plugins.entries')}</p><p className="break-words text-slate-500">{plugin.rows.map(row => local(row.name)).join(' · ')}</p></div>}
            {plugin.diagnostics.map((diagnostic,index) => <pre key={index} className="whitespace-pre-wrap break-all rounded-lg bg-rose-50 p-3 text-rose-800">{diagnostic}</pre>)}
            {confirm === plugin.name ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
              <p className="font-semibold text-rose-900">{t('agents.plugins.confirmTitle',{name:title})}</p>
              <p className="mt-1 text-rose-800">{t('agents.plugins.confirmHelp')}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="im-btn im-btn-muted text-rose-700" disabled={blocked} onClick={() => mutation.mutate({action:'remove_bundle',target:plugin.name})}>{t('agents.plugins.confirmUninstall')}</button>
                <button type="button" className="im-btn im-btn-muted" onClick={() => setConfirm(undefined)}>{t('agents.plugins.cancel')}</button>
              </div>
            </div> : plugin.removable && <button type="button" className="w-fit text-xs font-semibold text-rose-700 disabled:opacity-40" disabled={blocked} onClick={() => setConfirm(plugin.name)}>{t('agents.plugins.uninstall')}</button>}
          </div>
        </details>
      </article>;
    })}
    <details className="im-settings-plugin-scope">
      <summary className="w-fit cursor-pointer hover:text-slate-800">{t('agents.plugins.scope')}</summary>
      <p className="mt-2">{t('agents.plugins.scopeHelp')}</p>
      {data && <p className="mt-2 break-all font-mono text-[11px]">{data.workspace}</p>}
    </details>
  </section>;
}
