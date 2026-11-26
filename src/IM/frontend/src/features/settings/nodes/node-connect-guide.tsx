import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { DesktopDualInstallPicker, hasDesktopInstallAwareness } from '../../../desktop/desktop-install-picker';
import { useTranslation } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';
import { getOnboarding } from '../../onboarding/onboarding-api';
import { InstallPlatformPicker, suggestedPlatform, WindowsInstallPanel } from '../../onboarding/windows-install';
import type { NodeSettingsProfile } from '../im-settings-api';
import { computerName, NodeStatus } from './node-display';
import { NodeIcon } from './node-surface';

/** Reuse the current service's installation instructions without restarting onboarding. */
export function NodeConnectGuide({ node, onRefresh }: { node?: NodeSettingsProfile; onRefresh(): void }) {
  const { t, i18n } = useTranslation();
  const zh = i18n.language.startsWith('zh');
  const text = (cn: string, en: string) => (zh ? cn : en);
  const userId = useAuthStore(s => s.user?.id);
  const nodePlatform = node?.update?.current?.platform;
  const windowsNode = nodePlatform === 'win32-x64';
  const desktopNode = nodePlatform === 'desktop-darwin-arm64' || nodePlatform === 'desktop-win32-x64';
  const needsMaterials = !node || windowsNode || desktopNode;
  const query = useQuery({ queryKey: ['onboarding', userId], queryFn: getOnboarding, enabled: needsMaterials });
  const [platform, setPlatform] = useState(suggestedPlatform);
  const dualDesktopAware = !node && hasDesktopInstallAwareness(query.data?.install);
  const windows = windowsNode || (!node && !dualDesktopAware && platform === 'windows' && query.data?.install.windows_x64 !== undefined);
  const [mode, setMode] = useState<'agent' | 'manual'>('agent');
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const command = node?.update?.install_command || (!node && query.data?.install.available ? query.data.install.command : '');
  const prompt = node ? t('computers.agentRecoveryInstructions', { command }) : t('computers.agentInstructions', { command, origin: query.data?.install.origin ?? '' });
  const desktopRecoveryMaterials = nodePlatform === 'desktop-darwin-arm64'
    ? query.data?.install.desktop_darwin_arm64
    : nodePlatform === 'desktop-win32-x64'
      ? query.data?.install.desktop_win32_x64
      : null;

  const renderUnixSection = () => (
    !command ? <p className="node-drawer-note">{t('computers.noInstaller')}</p> : <>
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
      {!query.data?.install.windows_x64 && !dualDesktopAware && <p className="node-instructions-platforms">{t('computers.platforms')}</p>}
    </>
  );

  return <section className="node-instructions">
    <span className="node-computer-icon"><NodeIcon name="computer"/></span>
    <h3>{t(node ? 'computers.continueOnComputer' : 'computers.getStarted')}</h3>
    <p>{node ? t('computers.recoveryOn', { name: computerName(node, t('computers.unnamed')) }) : t('computers.connectBody')}</p>
    {node && (windowsNode || desktopNode) && <div aria-live="polite"><NodeStatus node={node}/></div>}
    {node && command && !desktopNode && <p className="node-drawer-note">{t('nodeUpdate.commandHelp')}</p>}
    {!node && !dualDesktopAware && query.data?.install.windows_x64 !== undefined && <InstallPlatformPicker value={platform} onChange={setPlatform}/>}
    {needsMaterials && query.isPending ? <p role="status">{t('common.loading')}</p>
      : needsMaterials && query.isError ? <div className="node-inline-error" role="alert"><p>{t('computers.installFailed')}</p><button className="node-button" onClick={() => void query.refetch()}>{t('common.retry')}</button></div>
      : desktopNode ? (
        desktopRecoveryMaterials ? (
          <div className="desktop-action-box">
            <h3>{text('重新安装或打开 Crewden Desktop', 'Reinstall or open Crewden Desktop')}</h3>
            <p>{text('下载最新安装包覆盖安装，或直接打开桌面客户端恢复这台电脑。', 'Download the latest installer or open Crewden Desktop directly to recover this computer.')}</p>
            <div className="desktop-action-row">
              <a className="desktop-btn primary" href={desktopRecoveryMaterials.download_url} target="_blank" rel="noreferrer">{text('下载最新 Crewden Desktop', 'Download latest Crewden Desktop')}</a>
              <a className="desktop-btn" href={desktopRecoveryMaterials.connect_url}>{text('打开 Crewden Desktop', 'Open Crewden Desktop')}</a>
            </div>
          </div>
        ) : <p className="node-drawer-note">{t('computers.noInstaller')}</p>
      )
      : dualDesktopAware && query.data?.install ? (
        <DesktopDualInstallPicker
          install={query.data.install}
          onRecheck={() => void query.refetch()}
          renderUnixHeadless={renderUnixSection}
        />
      )
      : windows ? <WindowsInstallPanel reconnect={windowsNode} materials={query.data?.install.windows_x64} onRecheck={() => void query.refetch()}/>
      : renderUnixSection()}
    <button className="node-button text node-return" onClick={onRefresh}>{t('computers.refreshList')}</button>
  </section>;
}
