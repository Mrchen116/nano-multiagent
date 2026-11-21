import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';
import { getOnboarding } from '../../onboarding/onboarding-api';
import { InstallPlatformPicker, suggestedPlatform, WindowsInstallPanel } from '../../onboarding/windows-install';
import type { NodeSettingsProfile } from '../im-settings-api';
import { computerName, NodeStatus } from './node-display';
import { NodeIcon } from './node-surface';

/** Reuse the current service's installation instructions without restarting onboarding. */
export function NodeConnectGuide({ node, onRefresh }: { node?: NodeSettingsProfile; onRefresh(): void }) {
  const { t } = useTranslation();
  const userId = useAuthStore(s => s.user?.id);
  const windowsNode = node?.update?.current?.platform === 'win32-x64';
  const needsMaterials = !node || windowsNode;
  const query = useQuery({ queryKey: ['onboarding', userId], queryFn: getOnboarding, enabled: needsMaterials });
  const [platform, setPlatform] = useState(suggestedPlatform);
  const windows = windowsNode || (!node && platform === 'windows' && query.data?.install.windows_x64 !== undefined);
  const [mode, setMode] = useState<'agent' | 'manual'>('agent');
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const command = node?.update?.install_command || (!node && query.data?.install.available ? query.data.install.command : '');
  const prompt = node ? t('computers.agentRecoveryInstructions', { command }) : t('computers.agentInstructions', { command, origin: query.data?.install.origin ?? '' });
  return <section className="node-instructions">
    <span className="node-computer-icon"><NodeIcon name="computer"/></span>
    <h3>{t(node ? 'computers.continueOnComputer' : 'computers.getStarted')}</h3>
    <p>{node ? t('computers.recoveryOn', { name: computerName(node, t('computers.unnamed')) }) : t('computers.connectBody')}</p>
    {node && windowsNode && <div aria-live="polite"><NodeStatus node={node}/></div>}
    {node && command && <p className="node-drawer-note">{t('nodeUpdate.commandHelp')}</p>}
    {!node && query.data?.install.windows_x64 !== undefined && <InstallPlatformPicker value={platform} onChange={setPlatform}/>}
    {needsMaterials && query.isPending ? <p role="status">{t('common.loading')}</p>
      : needsMaterials && query.isError ? <div className="node-inline-error" role="alert"><p>{t('computers.installFailed')}</p><button className="node-button" onClick={() => void query.refetch()}>{t('common.retry')}</button></div>
      : windows ? <WindowsInstallPanel reconnect={windowsNode} materials={query.data?.install.windows_x64} onRecheck={() => void query.refetch()}/>
      : !command ? <p className="node-drawer-note">{t('computers.noInstaller')}</p>
      : <>
        <div className="node-mode-tabs" role="group" aria-label={t('computers.installMethod')}>{(['agent', 'manual'] as const).map(value => <button key={value} aria-pressed={mode === value} onClick={() => { setMode(value); setCopied(false); setCopyError(false); }}>{t(`computers.${value}Mode`)}</button>)}</div>
        <ol><li>{t(mode === 'agent' ? 'computers.openAgent' : 'computers.openTerminal')}</li><li>{t(mode === 'agent' ? 'computers.giveInstructions' : 'computers.pasteCommand')}</li><li>{t(node ? 'computers.returnAfterRecovery' : 'computers.confirmBinding')}</li></ol>
        <pre className="node-command"><code>{mode === 'agent' ? prompt : command}</code></pre>
        <button className="node-button primary" onClick={() => {
          setCopyError(false); void (async () => {
            try { await navigator.clipboard.writeText(mode === 'agent' ? prompt : command); setCopied(true); }
            catch { setCopied(false); setCopyError(true); }
          })();
        }}><NodeIcon name="copy"/>{t(copied ? 'nodeUpdate.copied' : mode === 'agent' ? 'computers.copyInstructions' : 'computers.copyCommand')}</button>
        {copyError && <p className="node-form-error" role="alert">{t('computers.copyFailed')}</p>}
        {!query.data?.install.windows_x64 && <p className="node-instructions-platforms">{t('computers.platforms')}</p>}
      </>}
    <button className="node-button text node-return" onClick={onRefresh}>{t('computers.refreshList')}</button>
  </section>;
}
