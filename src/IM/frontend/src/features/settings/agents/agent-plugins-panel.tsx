import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from '../../../i18n';
import { listAgentPlugins, manageAgentPlugin, type PluginCommand, type PluginText } from './im-agent-config-api';

/** Installed bundles have their own lifecycle, including plugins that contribute no tools. */
export function AgentPluginsPanel({agentId}: {agentId: string}) {
  const {t, i18n} = useTranslation();
  const client = useQueryClient();
  const key = ['agent-plugins', agentId];
  const [confirm, setConfirm] = useState<string>();
  const query = useQuery({queryKey: key, queryFn: () => listAgentPlugins(agentId), retry: false,
    refetchInterval: state => state.state.data?.pending ? 1000 : false});
  const mutation = useMutation({mutationFn: (command: PluginCommand) => manageAgentPlugin(agentId, command),
    onSuccess: data => {client.setQueryData(key, data); setConfirm(undefined);},
  });
  const data = query.data;
  const blocked = !!data?.pending || mutation.isPending || query.isFetching || query.isError || mutation.isError;
  const local = (text: PluginText) => typeof text === 'string' ? text : text[i18n.language] ?? text[i18n.language.split('-')[0]] ?? text.en ?? Object.values(text)[0];
  const refresh = () => {mutation.reset(); void query.refetch();};
  return <section className="grid min-w-0 gap-4" aria-label={t('agents.plugins.title')}>
    <div className="flex items-start justify-between gap-4">
      <div>
        <h3 className="text-lg font-semibold">{t('agents.plugins.title')}</h3>
        <p className="mt-1 text-sm leading-6 text-slate-500">{t('agents.plugins.description')}</p>
      </div>
      <button type="button" className="im-btn im-btn-muted shrink-0" onClick={refresh} disabled={query.isFetching}>{t('agents.plugins.refresh')}</button>
    </div>
    <div className="rounded-xl border border-teal-200 bg-teal-50/60 p-4 text-sm leading-6 text-teal-900">
      <p className="font-semibold">{t('agents.plugins.scope')}</p>
      <p>{t('agents.plugins.scopeHelp')}</p>
      {data && <p className="mt-2 break-all font-mono text-xs opacity-70">{data.workspace}</p>}
    </div>
    {query.isPending && <p role="status" className="text-sm text-slate-500">{t('agents.plugins.loading')}</p>}
    {(query.isError || mutation.isError || data?.error) && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      <p className="font-semibold">{t(query.isError ? 'agents.plugins.unavailable' : 'agents.plugins.operationFailed')}</p>
      <p className="mt-1 break-words">{query.error?.message ?? mutation.error?.message ?? data?.error}</p>
      <p className="mt-1">{t('agents.plugins.retryHelp')}</p>
    </div>}
    {!query.isPending && !query.isError && data?.entries.length === 0 && <div className="im-agent-card py-8 text-center">
      <h4 className="font-semibold">{t('agents.plugins.empty')}</h4>
      <p className="mt-2 text-sm leading-6 text-slate-500">{t('agents.plugins.emptyHelp')}</p>
    </div>}
    {data?.entries.map(plugin => {
      const title = local(plugin.display_name);
      const pending = data.pending?.target === plugin.name ? data.pending : undefined;
      return <article key={plugin.name} className="im-agent-card min-w-0">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h4 className="break-words font-semibold">{title}</h4>
            <p className="mt-1 break-words text-sm leading-6 text-slate-500">{local(plugin.description)}</p>
            <p className={`mt-2 text-xs font-semibold ${plugin.state === 'failed' ? 'text-rose-700' : plugin.enabled ? 'text-teal-700' : 'text-slate-500'}`}>
              {t(`agents.plugins.${plugin.state}`)}
            </p>
          </div>
          <button type="button" role="switch" aria-checked={plugin.enabled} aria-label={title} disabled={blocked}
            className={`relative mt-1 h-6 w-11 shrink-0 rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${plugin.enabled ? 'bg-teal-600' : 'bg-slate-300'}`}
            onClick={() => mutation.mutate({action:'set_bundle',target:plugin.name,enabled:!plugin.enabled})}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${plugin.enabled ? 'left-0.5 translate-x-5' : 'left-0.5'}`}/>
          </button>
        </div>
        {pending && <p role="status" className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{t(pending.phase === 'waiting' ? 'agents.plugins.waiting' : 'agents.plugins.applying')}</p>}
        <details className="mt-4 border-t border-[var(--im-border)] pt-3">
          <summary className="w-fit cursor-pointer text-xs font-semibold text-slate-500">{t('agents.plugins.details')}</summary>
          <div className="mt-3 grid min-w-0 gap-3 text-xs leading-5">
            <p className="break-all font-mono text-slate-500">{plugin.name}{plugin.version ? ` · ${plugin.version}` : ''}</p>
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
  </section>;
}
