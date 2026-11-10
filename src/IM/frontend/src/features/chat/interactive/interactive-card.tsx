import React, { Component, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { Renderer, type ActionEvent } from '@openuidev/react-lang';
import { ThemeProvider } from '@openuidev/react-ui';
import '@openuidev/react-ui/defaults.css';
import '@openuidev/react-ui/components.css';
import { interactiveLibrary } from './catalog';
import { runLibraryAction } from './open-intelligent-ui/actions';
import { CardAttachmentImage } from './open-intelligent-ui/attachment-images';
import { MessageImage, protectedResourceUrl } from '../components/message-image';
import { listMessages, readInteractionDraft } from '../chat-api';
import type { Message } from '../chat-types';
import type { InteractionReplyInput } from './types';
import { useTranslation } from '../../../i18n';
import './interactive-card.css';
import { InteractionSubmissionError } from './submission-error';
import { attachDraftRecord, forgetInteractionDraft, interactionDraftRecord, registerDraftHandle,
  type DraftHandle } from '../interaction-background';

export interface InteractiveCardProps {
  message: Message;
  readOnly?: boolean;
  isGroup?: boolean;
  submittedMessageId?: string;
  onComposeMessage?(target: string, text: string): Promise<void>;
  onAttachmentVisibility?(url: string, visible: boolean): void;
  onSend(input: InteractionReplyInput, key: string): Promise<unknown>;
}

class RenderBoundary extends Component<{ children: React.ReactNode; fallback: React.ReactNode }, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

function CardMessageImage({ url, alt, report }: { url: string; alt: string; report?: InteractiveCardProps['onAttachmentVisibility'] }) {
  const onCardVisibility = useCallback((visible: boolean) => report?.(url, visible), [url, report]);
  return <MessageImage src={url} alt={alt} onCardVisibility={onCardVisibility} />;
}

/** Render public source while keeping edits private until an explicit continuation. */
export function InteractiveCard({message, readOnly, isGroup, submittedMessageId, onSend, onComposeMessage, onAttachmentVisibility}: InteractiveCardProps) {
  const { t } = useTranslation();
  const retained = !readOnly && !isGroup;
  const record = useMemo(() => interactionDraftRecord(message.conversation_id, message.id, retained),
    [message.conversation_id, message.id, retained]);
  useSyncExternalStore(record.subscribe, record.snapshot, record.snapshot);
  // A replacement renderer starts at the retained edit, but an ordinary acknowledgement
  // must never reseed the current renderer or move its cursor.
  const initial = useMemo(() => record.state, [record, record.renderVersion]);
  const { loaded, done } = record;
  const busy = record.submitting;
  const pending = record.hasPendingSubmission;
  const [applyingDraft, setApplyingDraft] = useState(false);
  const [composeError, setComposeError] = useState<string | null>(null);
  const [actionError, setError] = useState<'load'|'save'|'conflict'|'render'|'alreadySubmitted'|'stale'|'action'|null>(null);
  const error = pending && !busy ? 'send' : actionError ?? (isGroup && record.failure === 'conflict' ? 'conflict' : isGroup && record.failure ? 'save' : record.loadFailed ? 'load' : null);
  const [submissionConflict, setSubmissionConflict] = useState<InteractionSubmissionError|null>(null);
  const touched = useRef(false);
  const viewActive = useRef(true);
  const actionLabel = useRef('');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const locked = Boolean(readOnly || submissionConflict);
  const lockedRef = useRef(locked);
  lockedRef.current = locked;
  async function composeMessage(target: string, text: string) {
    if (!onComposeMessage || lockedRef.current || applyingDraft) return;
    clearTimeout(timer.current); setApplyingDraft(true); setComposeError(null);
    const version = record.renderVersion;
    try {
      await record.request;
      await save();
      if (!viewActive.current || !record.current) return;
      if (record.dirty || record.request) throw new Error(t('chat.interactive.saveError'));
      if (record.renderVersion !== version) throw new Error(t('chat.interactive.conflictError'));
      const latest = await readInteractionDraft(message.conversation_id, message.id);
      if (latest.can_interact !== true || latest.read_only || latest.superseded_by) throw new Error(t('chat.interactive.readOnly'));
      if (viewActive.current && record.current) await onComposeMessage(target, text);
    } catch (error) { setComposeError(error instanceof Error ? error.message : t('chat.interactive.actionError')); }
    finally { setApplyingDraft(false); }
  }
  async function load(adopting = false) {
    setError(null);
    const success = await record.load(adopting);
    if (success) touched.current = false;
    else if (adopting && record.current && !record.hasPendingSubmission) setError('conflict');
    return success;
  }
  useEffect(() => {
    viewActive.current = true;
    const detach = attachDraftRecord(record, retained);
    if (readOnly) forgetInteractionDraft(message.conversation_id, message.id);
    void load();
    // A detach may interrupt the debounce before the first PUT; resume it on this view.
    if (record.dirty && !record.failure && !record.hasPendingSubmission) timer.current = setTimeout(() => { void save(); }, 500);
    return () => { viewActive.current = false; clearTimeout(timer.current); detach(); };
  }, [record]);
  async function syncSubmittedDraft() {
    try { await record.syncSubmitted(); }
    catch { if (record.current) setError('save'); }
  }
  // Composer submissions also advance the draft revision, without remounting the explorer.
  useEffect(() => {
    if (loaded && submittedMessageId) void syncSubmittedDraft();
  }, [submittedMessageId]);

  async function save(): Promise<string | undefined> {
    if (lockedRef.current || record.hasPendingSubmission) return record.savedAt;
    setError(null);
    return record.save();
  }
  /** Finish this view's debounce while the retained record owns any in-flight PUT. */
  async function flush() {
    clearTimeout(timer.current);
    if (lockedRef.current || record.hasPendingSubmission) {
      return record.unsaved ? {reason: record.failure ?? 'transient' as const} : {updatedAt: record.savedAt};
    }
    return record.flush();
  }
  const handleRef = useRef<DraftHandle>({flush});
  handleRef.current = {flush};
  useEffect(() => {
    if (readOnly || isGroup) return;
    return registerDraftHandle(message.conversation_id, message.id, handleRef.current);
  }, [record, readOnly, isGroup]);
  async function submit(request?: Pick<InteractionReplyInput, 'action_id'|'event'>, formState?: Record<string, unknown>) {
    if (lockedRef.current) { setError('stale'); throw new Error('This historical reply cannot submit new requests'); }
    const pending = record.beginSubmission(() => ({source_message_id: message.id, ...request,
      state: structuredClone({...record.state, ...formState})}));
    clearTimeout(timer.current); setError(null);
    let outcome: 'accepted' | 'rejected' | 'unknown' = 'unknown';
    try {
      // Finish an earlier private save before submission increments its revision.
      await record.request;
      if (!viewActive.current || !record.current) throw new Error('This interaction view is no longer active');
      const result = await onSend(pending.input, pending.key);
      outcome = 'accepted';
      if (record.current) await syncSubmittedDraft();
      return result;
    } catch (e) {
      if (e instanceof InteractionSubmissionError) {
        outcome = 'rejected';
        setSubmissionConflict(e); setError(e.reason);
      }
      throw e;
    }
    finally { record.finishSubmission(outcome); }
  }
  const submitRef = useRef(submit); submitRef.current = submit;
  const toolProvider = useMemo(() => ({
    conversation_messages: async (args: Record<string, unknown>) => {
        const result = await listMessages(message.conversation_id, {limit:typeof args.limit === 'number' ? Math.max(1, Math.min(100, Math.floor(args.limit))) : 20});
        return result.items.flatMap(item => item.type === 'message' ? [{id:item.message.id,sender:item.message.sender.display_name,content:item.message.content,delivery_status:item.message.delivery_status}] : []);
    },
    continue_conversation: async (args: Record<string, unknown>) => {
        if (typeof args.message !== 'string') throw new Error('message required');
        const result = await submitRef.current({event:{type:'continue_conversation',message:args.message,context:args.context,label:actionLabel.current || t('chat.interactive.ask')}}) as Message | undefined;
        return {message_id:result?.id,delivery_status:result?.delivery_status};

    },
  }), [message.id, message.conversation_id, t]);
  function onAction(action: ActionEvent) {
    if (!viewActive.current || !record.current) return;
    const handled = runLibraryAction(action);
    if (handled) { void handled.then(ok => { if (!ok) setError('action'); }); return; }
    if (action.type === 'ComposeMessage') {
      if (typeof action.params.target === 'string' && typeof action.params.text === 'string') void composeMessage(action.params.target, action.params.text);
      else setError('action');
      return;
    }
    if (action.type === 'open_url') {
      try { const url=new URL(String(action.params.url)); if (!['https:','http:'].includes(url.protocol)) throw new Error('Unsupported URL'); window.open(url.href,'_blank','noopener,noreferrer'); }
      catch { setError('action'); }
      return;
    }
    if (action.type === 'nano_continue' && typeof action.params.action_id === 'string') {
      void submit({action_id:action.params.action_id}, action.formState).catch(() => undefined); return;
    }
    if (action.type === 'SendToChat' || action.type === 'continue_conversation') {
      const text = action.type === 'SendToChat' ? action.params.message : action.humanFriendlyMessage;
      if (typeof text !== 'string') { setError('action'); return; }
      void submit({event:{type:'continue_conversation',message:text,context:action.params.context,
        form_name:action.formName,label:actionLabel.current || t('chat.interactive.ask')}}, action.formState).catch(() => undefined); return;
    }
    setError('action');
  }
  const renderAttachment = (index: number, alt: string) => {
    const attachment = message.attachments?.[index - 1];
    if (!attachment?.content_type?.startsWith('image/') || !protectedResourceUrl(attachment.url, message.conversation_id)) {
      return <MessageImage alt={alt} />;
    }
    return <CardMessageImage url={attachment.url} alt={alt} report={onAttachmentVisibility} />;
  };
  const fallback = <p role="status">{t('chat.interactive.fallback')}</p>;
  function markTouched(event: React.SyntheticEvent) {
    if (!(event.target instanceof Element && event.target.closest('[data-attachment-preview]'))) touched.current = true;
  }
  return <section className={`interactive-card${message.content.trim() ? "" : " interactive-card--standalone"}`} aria-label={t('chat.interactive.title')}
    onClickCapture={event => {
      if (event.target instanceof Element && event.target.closest('[data-attachment-preview]')) return;
      touched.current = true;
      const target = event.target instanceof Element ? event.target.closest('button,[role="button"],a,[tabindex]') : null;
      actionLabel.current = (target?.getAttribute('aria-label') || target?.textContent || '').trim();
    }}
    onTouchStart={e => e.stopPropagation()} onContextMenu={e => e.stopPropagation()}
    onPointerDownCapture={markTouched} onKeyDownCapture={markTouched}
    onChangeCapture={() => { touched.current = true; }}>
    {!loaded && !error && <p role="status">{t('chat.interactive.loading')}</p>}
    {loaded && error !== 'render' && <RenderBoundary fallback={fallback}>
      <fieldset disabled={readOnly || busy || applyingDraft || pending} className="interactive-card-fields">
        <CardAttachmentImage.Provider value={renderAttachment}>
        <ThemeProvider mode="light" cssSelector=".interactive-card">
        <Renderer key={record.renderVersion} response={message.interactive!.source} library={interactiveLibrary}
          initialState={initial} isStreaming={busy || pending} toolProvider={toolProvider} publishObservability={false}
          onParseResult={parsed => { if (viewActive.current) record.update({...parsed?.stateDeclarations, ...record.state}); }}
          onError={errors => { if (errors.some(error => error.source === 'parser')) setError('render'); }}
          onStateUpdate={value => {
            if (!viewActive.current) return;
            // Only a real input event may arm a background; rendering must never do it.
            const edited = !lockedRef.current && !record.hasPendingSubmission && touched.current;
            if (record.update(value, edited)) {
              clearTimeout(timer.current); timer.current = setTimeout(() => { void save(); }, 500);
            }
          }}
          onAction={onAction} />
        </ThemeProvider>
        </CardAttachmentImage.Provider>
      </fieldset>
    </RenderBoundary>}
    {error === 'render' && fallback}
    {composeError && <p role="alert">{composeError}</p>}
    {(locked || busy || done || error) && <div className="interactive-card-status" aria-live="polite">
      {locked ? t('chat.interactive.readOnly') : busy ? t('chat.interactive.sending') : done ? t('chat.interactive.submitted') : null}
      {error && error !== 'render' && <span role="alert">{t(`chat.interactive.${error}Error`)}</span>}
      {submissionConflict?.submissionMessageId && <a href={`/chat/${encodeURIComponent(message.conversation_id)}?message_id=${encodeURIComponent(submissionConflict.submissionMessageId)}`}>{t('chat.interactive.previousSubmission')}</a>}
      {error === 'load' && <button type="button" onClick={() => void load()}>{t('chat.interactive.retry')}</button>}
      {error === 'save' && <button type="button" onClick={() => void save()}>{t('chat.interactive.retry')}</button>}
      {error === 'send' && <button type="button" onClick={() => void submit().catch(() => undefined)}>{t('chat.interactive.retry')}</button>}
      {isGroup && error === 'conflict' && <button type="button" onClick={() => void load(true)}>{t('chat.interactive.loadLatest')}</button>}
    </div>}
  </section>;
}
