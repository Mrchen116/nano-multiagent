import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from '../../../i18n';
import { cancelNodeUpdate, startNodeUpdate, type NodeUpdateView } from '../im-settings-api';

const cancellable = ['requested','downloading','installing','waiting'];
const switching = ['switching','verifying','rolling_back'];
export function nodeUpdateActive(update?: NodeUpdateView) {
  return !!update?.operation && [...cancellable,...switching].includes(update.operation.state);
}
export function nodeUpdateSwitching(update?: NodeUpdateView) {
  return !!update?.operation && switching.includes(update.operation.state);
}
export function nodeUpdateNeedsRecovery(update?: NodeUpdateView) { return update?.operation?.relay_gated && !nodeUpdateActive(update); }
export function nodeUpdateLabel(update?: NodeUpdateView): string | null {
  if (nodeUpdateNeedsRecovery(update)) return 'recoveryChip';
  if (nodeUpdateSwitching(update)) return 'switching.title';
  if (nodeUpdateActive(update)) return 'progressChip';
  if (update?.available) return 'available.title';
  return null;
}
const version = (value?: string) => value && /^[a-f0-9]{40}$/.test(value) ? value.slice(0,8) : value ?? '—';

/** One explicit click authorizes an update; progress survives leaving this page. */
export function NodeUpdatePanel({nodeId, update}: {nodeId:string;update:NodeUpdateView}) {
  const {t}=useTranslation(); const client=useQueryClient();
  const requestId=useRef<string|null>(null); const [instructions,setInstructions]=useState(false); const [copied,setCopied]=useState(false);
  const op=update.operation; const active=nodeUpdateActive(update);
  useEffect(()=>{if(op && !active)requestId.current=null;},[op?.id,op?.state,active]);
  const refresh=async()=>{await Promise.all([
    client.invalidateQueries({queryKey:['settings','nodes']}),client.invalidateQueries({queryKey:['chat','nodes']})
  ]);};
  const start=useMutation({mutationFn:()=>{
    requestId.current ??= crypto.randomUUID();
    return startNodeUpdate(nodeId,{request_id:requestId.current,version:update.target!.version,sha256:update.target!.sha256});
  },onSuccess:()=>{requestId.current=null;},onSettled:refresh});
  const cancel=useMutation({mutationFn:()=>cancelNodeUpdate(nodeId,op!.id),onSettled:refresh});
  const recover=nodeUpdateNeedsRecovery(update);
  const result=op && !(op.state==='succeeded' && update.available) && ['succeeded','cancelled','failed','rolled_back','interrupted'].includes(op.state) ? op.state : null;
  const state=recover?'recovery_required':active?op!.state:['available','current'].includes(update.reason)?result ?? update.reason:update.reason;
  const error=['failed','rolled_back','interrupted','recovery_required'].includes(state);
  const bridge=['legacy','recovery_required','incompatible'].includes(state);
  const canCancel=!!op && cancellable.includes(op.state);
  const canUpdate=!active && update.available;
  return <div data-testid={`node-update-${nodeId}`} className={`rounded-[10px] border p-4 ${error?'border-amber-200 bg-amber-50/60':'border-[var(--im-border)] bg-[var(--im-accent-soft)]/30'}`}>
    <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center sm:gap-6">
      <div className="min-w-0">
        <h4 className="m-0 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[15px] font-bold" aria-live="polite">
          {t(`nodeUpdate.${state}.title`)}
          {update.current && <span className="text-xs font-normal text-[var(--im-text-muted)]">{version(update.current.version)}{update.target && update.reason!=='current' && state!=='succeeded' ? ` → ${version(update.target.version)}`:''}</span>}
        </h4>
        {state==='available' && update.target?.release_notes && <p className="mb-0 mt-1 whitespace-pre-wrap text-[13px] text-[var(--im-text-secondary)]">{update.target.release_notes}</p>}
        <p className="mb-0 mt-1 text-[13px] leading-5 text-[var(--im-text-muted)]">{t(`nodeUpdate.${state}.body`)}</p>
      </div>
      {canCancel ? <button type="button" className="im-btn im-btn-muted shrink-0" disabled={cancel.isPending||op!.cancel_requested} onClick={()=>cancel.mutate()}>{t(op!.cancel_requested?'nodeUpdate.cancelling':'nodeUpdate.cancel')}</button>
        : bridge ? <button type="button" className="im-btn im-btn-primary shrink-0" onClick={()=>setInstructions(!instructions)} aria-expanded={instructions}>{t(state==='legacy'?'nodeUpdate.bridge':'nodeUpdate.recover')}</button>
        : canUpdate || state==='offline' ? <button type="button" className="im-btn im-btn-primary shrink-0" disabled={!canUpdate||start.isPending} onClick={()=>start.mutate()}>{t(start.isPending?'nodeUpdate.starting':error?'common.retry':'nodeUpdate.update')}</button>:null}
    </div>
    {(start.isError||cancel.isError) && <p role="alert" className="mb-0 mt-2 text-xs text-amber-800">{t('nodeUpdate.requestError')}</p>}
    {instructions && <div className="mt-4 border-t border-[var(--im-border)] pt-3 text-[13px]">
      <p className="m-0 leading-5">{t('nodeUpdate.commandHelp')}</p>
      <pre className="my-3 overflow-x-auto rounded-lg bg-white p-3 text-xs"><code>{update.install_command}</code></pre>
      <button type="button" className="im-btn im-btn-muted" onClick={()=>{void navigator.clipboard.writeText(update.install_command).then(()=>setCopied(true)).catch(()=>setCopied(false));}}>{t(copied?'nodeUpdate.copied':'nodeUpdate.copy')}</button>
    </div>}
  </div>;
}
