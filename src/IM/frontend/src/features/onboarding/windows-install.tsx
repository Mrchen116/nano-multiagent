import { useState } from 'react';
import { useTranslation } from '../../i18n';
import type { WindowsInstall } from './onboarding-api';
import './windows-install.css';

export type InstallPlatform = 'windows' | 'unix';
export const suggestedPlatform = (): InstallPlatform => /Windows/i.test(navigator.userAgent) ? 'windows' : 'unix';

export function InstallPlatformPicker({ value, onChange }: {value: InstallPlatform; onChange(value: InstallPlatform): void}) {
  const { t } = useTranslation();
  return <label className="computer-platform-picker">{t('computers.operatingSystem')}
    <select value={value} onChange={e => onChange(e.target.value as InstallPlatform)}>
      <option value="windows">Windows 10 / 11 · x64</option>
      <option value="unix">macOS / Linux / WSL</option>
    </select>
  </label>;
}

/** Download and protocol handoff are user gestures. Only the server can confirm a connection. */
export function WindowsInstallPanel({ materials, onRecheck, onStart, reconnect = false }: {
  materials?: WindowsInstall | null; onRecheck(): void; onStart?(opened: boolean): void; reconnect?: boolean;
}) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState<'initial' | 'downloaded' | 'waiting'>(reconnect ? 'downloaded' : 'initial');
  if (!materials) return <div className="computer-windows-install" role="status"><strong>{t('computers.windows.unavailable')}</strong>
    <p>{t('computers.windows.unavailableHelp')}</p><button className="computer-install-action" onClick={onRecheck}>{t('computers.windows.checkAgain')}</button></div>;
  const download = <a key="download" className="computer-install-action" data-primary={phase === 'initial'} href={materials.download_url} target="_blank" rel="noreferrer"
    onClick={() => { onStart?.(false); setPhase('downloaded'); }}>{t(phase === 'initial' ? 'computers.windows.download' : 'computers.windows.redownload')}</a>;
  const connect = <a key="connect" className="computer-install-action" data-primary={phase !== 'initial'} href={materials.connect_url}
    onClick={() => { onStart?.(true); setPhase('waiting'); }}>{t(phase === 'initial' ? 'computers.windows.alreadyInstalled' : phase === 'waiting' ? 'computers.windows.reopen' : 'computers.windows.open')}</a>;
  return <div className="computer-windows-install" aria-live="polite"><strong>{t(`computers.windows.${phase}Title`)}</strong>
    <p>{t(`computers.windows.${phase}Help`)}</p><div className="computer-windows-actions">
      {phase === 'initial' ? <>{download}{connect}</> : <>{connect}{download}</>}
    </div></div>;
}
