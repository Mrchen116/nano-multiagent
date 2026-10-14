import { useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from '../../../i18n';
import { cancelNodeUpdate, startNodeUpdate, type NodeUpdateView } from '../im-settings-api';
import { NodeIcon } from './node-surface';

const cancellable = ['requested', 'downloading', 'installing', 'waiting'];
const switching = ['switching', 'verifying', 'rolling_back'];
/** Identify an operation whose persisted lifecycle has not finished. */
export function nodeUpdateActive(update?: NodeUpdateView) {
  return !!update?.operation && [...cancellable, ...switching].includes(update.operation.state);
}
/** Identify stages where the computer cannot accept configuration changes. */
export function nodeUpdateSwitching(update?: NodeUpdateView) {
  return !!update?.operation && switching.includes(update.operation.state);
}
/** Prefer the relay gate over a terminal label when recovery is incomplete. */
export function nodeUpdateNeedsRecovery(update?: NodeUpdateView) {
  return !!update?.operation?.relay_gated && !nodeUpdateActive(update);
}
/** Share update availability labels with the chat computer chip. */
export function nodeUpdateLabel(update?: NodeUpdateView): string | null {
  if (nodeUpdateNeedsRecovery(update)) return 'recoveryChip';
  if (nodeUpdateSwitching(update)) return 'switching.title';
  if (nodeUpdateActive(update)) return 'progressChip';
  if (update?.available) return 'available.title';
  return null;
}

/** Authorize updates once and show the next action beside its real progress. */
export function NodeUpdatePanel({ nodeId, update, onInstructions }: {
  nodeId: string; update: NodeUpdateView; onInstructions?(): void;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const requestId = useRef<string | null>(null);
  const op = update.operation;
  const active = nodeUpdateActive(update);
  useEffect(() => { if (op && !active) requestId.current = null; }, [op?.id, op?.state, active]);
  const refresh = async () => { await Promise.all([
    client.invalidateQueries({ queryKey: ['settings', 'nodes'] }), client.invalidateQueries({ queryKey: ['chat', 'nodes'] })
  ]); };
  const start = useMutation({ mutationFn: () => {
    // A request with an uncertain response must retain its authorization ID.
    requestId.current ??= crypto.randomUUID();
    return startNodeUpdate(nodeId, { request_id: requestId.current, version: update.target!.version, sha256: update.target!.sha256 });
  }, onSuccess: () => { requestId.current = null; }, onSettled: refresh });
  const cancel = useMutation({ mutationFn: () => cancelNodeUpdate(nodeId, op!.id), onSettled: refresh });
  const recover = nodeUpdateNeedsRecovery(update);
  const result = op && !(op.state === 'succeeded' && update.available) && !(update.reason === 'current' && op.state !== 'succeeded')
    && ['succeeded', 'cancelled', 'failed', 'rolled_back', 'interrupted'].includes(op.state) ? op.state : null;
  const state = recover ? 'recovery_required' : active ? op!.state : ['available', 'current'].includes(update.reason) ? result ?? update.reason : update.reason;
  const error = ['failed', 'rolled_back', 'interrupted', 'recovery_required', 'incompatible'].includes(state);
  const bridge = ['legacy', 'recovery_required', 'incompatible'].includes(state);
  const newVersion = update.target && update.target.version !== update.current?.version;
  // Offline is not evidence of a new release. Do not offer an inert update CTA.
  if (state === 'current' || (state === 'offline' && !newVersion)) return null;
  const canCancel = !!op && cancellable.includes(op.state);
  const canUpdate = !active && update.available;
  const step = cancellable.includes(state) ? (state === 'waiting' ? 1 : 0) : 2;
  const title = state === 'available' ? t('computers.releaseReady', { version: update.target?.version }) : t(`nodeUpdate.${state}.title`);
  return <div data-testid={`node-update-${nodeId}`} className={`node-update-band ${error ? 'warning' : ['source', 'legacy', 'unpublished', 'offline', 'cancelled'].includes(state) ? 'neutral' : ''}`}>
    <span className="node-update-symbol"><NodeIcon name={state === 'succeeded' ? 'check' : state === 'waiting' ? 'clock' : error || bridge ? 'info' : 'update'} spin={active && state !== 'waiting'}/></span>
    <div className="node-update-copy"><h3 aria-live="polite">{title}</h3>
      <p>{state === 'available' && update.target?.release_notes ? update.target.release_notes : t(`nodeUpdate.${state}.body`)}</p>
      {active && <div className="node-update-steps" aria-label={t('computers.updateStages')}>{['prepare', 'idle', 'switch'].map((stage, index) => <span key={stage} className={index === step ? 'current' : index < step ? 'done' : ''}>{t(`computers.stage.${stage}`)}</span>)}</div>}
    </div>
    {canCancel ? <button className="node-button" disabled={cancel.isPending || op!.cancel_requested} onClick={() => cancel.mutate()}>{t(op!.cancel_requested || cancel.isPending ? 'nodeUpdate.cancelling' : 'nodeUpdate.cancel')}</button>
      : bridge ? <button className="node-button primary" onClick={onInstructions}>{t(state === 'legacy' ? 'nodeUpdate.bridge' : 'nodeUpdate.recover')}</button>
      : canUpdate ? <button className="node-button primary" disabled={start.isPending} onClick={() => start.mutate()}>{t(start.isPending ? 'nodeUpdate.starting' : error ? 'common.retry' : 'nodeUpdate.update')}</button> : null}
    {(start.isError || cancel.isError) && <p className="node-update-error" role="alert">{t('nodeUpdate.requestError')}</p>}
  </div>;
}
