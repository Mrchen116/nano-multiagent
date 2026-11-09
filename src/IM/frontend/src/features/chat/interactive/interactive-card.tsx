import React, { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Renderer, type ActionEvent } from '@openuidev/react-lang';
import { ThemeProvider } from '@openuidev/react-ui';
import '@openuidev/react-ui/defaults.css';
import '@openuidev/react-ui/components.css';
import { interactiveLibrary } from './catalog';
import { runLibraryAction } from './open-intelligent-ui/actions';
import { CardAttachmentImage } from './open-intelligent-ui/attachment-images';
import { MessageImage, protectedResourceUrl } from '../components/message-image';
import { listMessages, readInteractionDraft, saveInteractionDraft } from '../chat-api';
import type { Message } from '../chat-types';
import type { InteractionReplyInput } from './types';
import { useTranslation } from '../../../i18n';
import './interactive-card.css';
import { InteractionSubmissionError } from './submission-error';
import { clearDraftFailure, draftSession, noteDraftFailed, noteDraftSaved, readable, registerDraftHandle,
  type DraftFailureReason, type DraftHandle } from '../interaction-background';

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
  const [loaded, setLoaded] = useState(false);
  const [initial, setInitial] = useState<Record<string, unknown>>({});
  const [generation, setGeneration] = useState(0);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [applyingDraft, setApplyingDraft] = useState(false);
  const [composeError, setComposeError] = useState<string | null>(null);
  const [error, setError] = useState<'load'|'save'|'conflict'|'send'|'render'|'alreadySubmitted'|'stale'|'action'|null>(null);
  const [submissionConflict, setSubmissionConflict] = useState<InteractionSubmissionError|null>(null);
  const state = useRef<Record<string, unknown>>({});
  const revision = useRef(0);
  const touched = useRef(false);
  const lastSavedAt = useRef<string | undefined>(undefined);
  const saveFailure = useRef<DraftFailureReason | null>(null);
  const dirty = useRef(false);
  const saving = useRef(false);
  const saveRequest = useRef<ReturnType<typeof saveInteractionDraft> | null>(null);
  const submitting = useRef(false);
  const actionLabel = useRef('');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pending = useRef<{input: InteractionReplyInput; key: string}|null>(null);
  const locked = Boolean(readOnly || submissionConflict);
  const lockedRef = useRef(locked);
  lockedRef.current = locked;
  async function composeMessage(target: string, text: string) {
    if (!onComposeMessage || lockedRef.current || applyingDraft) return;
    clearTimeout(timer.current); setApplyingDraft(true); setComposeError(null);
    try {
      await saveRequest.current?.catch(() => undefined);
      await save();
      if (dirty.current || saving.current) return;
      const latest = await readInteractionDraft(message.conversation_id, message.id);
      if (latest.can_interact !== true || latest.read_only || latest.superseded_by) throw new Error(t('chat.interactive.readOnly'));
      await onComposeMessage(target, text);
    } catch (error) { setComposeError(error instanceof Error ? error.message : t('chat.interactive.actionError')); }
    finally { setApplyingDraft(false); }
  }
  async function load(adopting = false) {
    setError(null);
    try {
      const draft = await readInteractionDraft(message.conversation_id, message.id);
      state.current = draft.state; revision.current = draft.draft_revision;
      setInitial(draft.state); setDone(Boolean(draft.submission_message_id));
      setGeneration(value => value + 1); setLoaded(true); dirty.current = false;
      touched.current = false;
      return true;
    } catch { setError(adopting ? 'conflict' : 'load'); return false; }
  }
  useEffect(() => { void load(); return () => clearTimeout(timer.current); }, [message.id]);
  async function syncSubmittedDraft() {
    try {
      const draft = await readInteractionDraft(message.conversation_id, message.id);
      // POST and WS can confirm the same submission in either order.
      revision.current = Math.max(revision.current, draft.draft_revision);
      setDone(JSON.stringify(state.current) === JSON.stringify(draft.state));
    } catch { setError('save'); }
  }
  // Composer submissions also advance the draft revision, without remounting the explorer.
  useEffect(() => {
    if (loaded && submittedMessageId) void syncSubmittedDraft();
  }, [submittedMessageId]);

  async function save(): Promise<string | undefined> {
    if (saving.current || lockedRef.current || !dirty.current || pending.current) return lastSavedAt.current;
    saving.current = true;
    dirty.current = false;
    const value = state.current, session = draftSession(message.conversation_id);
    try {
      saveRequest.current = saveInteractionDraft(message.conversation_id, message.id, revision.current, value);
      const result = await saveRequest.current;
      if (session !== draftSession(message.conversation_id)) return undefined;
      revision.current = result.draft_revision;
      lastSavedAt.current = result.updated_at ?? undefined;
      saveFailure.current = null;
      setError(null);
      // Watermark advances only on confirmed saves; this is what leaving will clear.
      if (!isGroup) {
        noteDraftSaved(message.conversation_id, result.updated_at ?? undefined, session);
        clearDraftFailure(message.conversation_id, message.id, session);
      }
    } catch (e) {
      if (session !== draftSession(message.conversation_id)) return undefined;
      dirty.current = true;
      const reason: DraftFailureReason = String(e).includes('409') ? 'conflict' : 'transient';
      saveFailure.current = reason;
      setError(reason === 'conflict' ? 'conflict' : 'save');
      if (!isGroup) noteDraftFailed(message.conversation_id, message.id, reason, session);
    } finally { saving.current = false; saveRequest.current = null; }
    // An edit during an in-flight save must persist with the newly returned revision.
    if (state.current !== value && dirty.current) void save();
    return lastSavedAt.current;
  }
  /** Finish this card's debounce window for the composer; never throws into the send path. */
  async function flush(): Promise<{updatedAt?: string; reason?: DraftFailureReason}> {
    const session = draftSession(message.conversation_id);
    clearTimeout(timer.current);
    await saveRequest.current?.catch(() => undefined);
    if (session !== draftSession(message.conversation_id)) return {reason: 'transient'};
    await save();
    if (saving.current || dirty.current) {
      const reason = saveFailure.current ?? 'transient';
      noteDraftFailed(message.conversation_id, message.id, reason);
      return {reason};
    }
    if (saveFailure.current) return {reason: saveFailure.current};
    return lastSavedAt.current ? {updatedAt: lastSavedAt.current} : {};
  }
  /** Read-only comparison of the server draft with this device's edit. Applies nothing. */
  async function describeConflict(): Promise<{columns: {label: string; remote: string; local: string}[]}> {
    const remote = await readInteractionDraft(message.conversation_id, message.id);
    const raw = (name: string) => {
      const value = state.current[name];
      return value && typeof value === 'object' && 'value' in (value as Record<string, unknown>)
        ? (value as Record<string, unknown>).value : value;
    };
    return {columns: (remote.fields ?? []).map(field => ({label: field.label,
      remote: readable(field.value, field.display_value, field.options),
      local: readable(raw(field.name), undefined, field.options)}))};
  }
  /** Adopt the server draft after the user accepted discarding this device's edit. */
  async function adoptRemote(): Promise<void> {
    // A failed read leaves this device's edit intact; it is not a successful adoption and
    // must not release the conversation-wide block.
    if (!await load(true)) throw new Error(t('chat.interactive.loadError'));
    saveFailure.current = null;
    clearDraftFailure(message.conversation_id, message.id);
  }
  const handleRef = useRef<DraftHandle>({flush, describeConflict, adoptRemote});
  handleRef.current = {flush, describeConflict, adoptRemote};
  useEffect(() => {
    if (readOnly || isGroup) return;
    return registerDraftHandle(message.conversation_id, message.id, handleRef.current);
  }, [message.id, message.conversation_id, readOnly, isGroup]);
  async function submit(request?: Pick<InteractionReplyInput, 'action_id'|'event'>, formState?: Record<string, unknown>) {
    if (lockedRef.current) { setError('stale'); throw new Error('This historical reply cannot submit new requests'); }
    if (submitting.current) throw new Error('A request is already pending');
    submitting.current = true;
    if (!pending.current) pending.current = {input: {source_message_id: message.id, ...request,
      state: structuredClone({...state.current, ...formState})}, key: crypto.randomUUID()};
    clearTimeout(timer.current); setBusy(true); setError(null);
    try {
      // Finish an earlier private save before submission increments its revision.
      await saveRequest.current?.catch(() => undefined);
      const result = await onSend(pending.current.input, pending.current.key);
      setDone(true); pending.current = null; dirty.current = false;
      await syncSubmittedDraft();
      return result;
    } catch (e) {
      if (e instanceof InteractionSubmissionError) {
        pending.current = null; dirty.current = false;
        setSubmissionConflict(e); setError(e.reason);
      } else setError('send');
      throw e;
    }
    finally { submitting.current = false; setBusy(false); }
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
      <fieldset disabled={readOnly || busy || applyingDraft || Boolean(pending.current)} className="interactive-card-fields">
        <CardAttachmentImage.Provider value={renderAttachment}>
        <ThemeProvider mode="light" cssSelector=".interactive-card">
        <Renderer key={generation} response={message.interactive!.source} library={interactiveLibrary}
          initialState={initial} isStreaming={busy || Boolean(pending.current)} toolProvider={toolProvider} publishObservability={false}
          onParseResult={parsed => { state.current = {...parsed?.stateDeclarations, ...state.current}; }}
          onError={errors => { if (errors.some(error => error.source === 'parser')) setError('render'); }}
          onStateUpdate={value => {
            state.current = value;
            if (lockedRef.current || pending.current) return;
            // Only a real input event may arm a background; rendering must never do it.
            if (!touched.current) return;
            dirty.current = true; setDone(false);
            clearTimeout(timer.current); timer.current = setTimeout(() => { void save(); }, 500);
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
      {isGroup && error === 'conflict' && <button type="button" onClick={() => void load()}>{t('chat.interactive.loadLatest')}</button>}
    </div>}
  </section>;
}
