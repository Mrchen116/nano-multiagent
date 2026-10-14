import { useTranslation } from '../../../i18n';
import type { NodeSettingsProfile } from '../im-settings-api';
import { nodeUpdateNeedsRecovery, nodeUpdateSwitching } from './node-update-panel';

/** Resolve the user-visible computer name without exposing technical IDs. */
export function computerName(node: NodeSettingsProfile, fallback: string) {
  return node.alias?.trim() || node.node_name?.trim() || fallback;
}

/** Return a concise version label; diagnostics retain the full value. */
export function computerVersion(node: NodeSettingsProfile) {
  const version = node.update?.current?.version || node.version;
  return version && /^[a-f0-9]{40}$/.test(version) ? version.slice(0, 8) : version || '—';
}

/** Keep the list's last connection time brief; details show the exact timestamp. */
export function lastSeenTime(timestamp: string, language: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(timestamp).getTime()) / 60000));
  const formatter = new Intl.RelativeTimeFormat(language, { numeric: 'auto' });
  if (minutes < 60) return formatter.format(-minutes, 'minute');
  if (minutes < 1440) return formatter.format(-Math.floor(minutes / 60), 'hour');
  return formatter.format(-Math.floor(minutes / 1440), 'day');
}

/** Express availability from update recovery and transport state together. */
export function NodeStatus({ node }: { node: NodeSettingsProfile }) {
  const { t } = useTranslation();
  const recovery = nodeUpdateNeedsRecovery(node.update);
  const switching = nodeUpdateSwitching(node.update);
  const state = recovery ? 'recovery' : switching ? 'updating' : node.status;
  const label = recovery ? 'nodeUpdate.recoveryChip' : switching ? 'nodeUpdate.switching.title'
    : `settings.nodes.${node.status === 'online' ? 'statusOnline' : node.status === 'degraded' ? 'statusDegraded' : 'statusOffline'}`;
  return <span className={`node-status ${state}`} data-testid={`node-status-pill-${node.node_id}`}><i data-status-dot={state}/>{t(label)}</span>;
}

