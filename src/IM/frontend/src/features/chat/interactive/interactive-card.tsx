import React, { Component, useEffect, useMemo, useRef, useState } from 'react';
import { Renderer, type ActionEvent } from '@openuidev/react-lang';
import { ThemeProvider } from '@openuidev/react-ui';
import { interactiveTheme } from './theme';
import '@openuidev/react-ui/defaults.css';
import '@openuidev/react-ui/components.css';
import { interactiveLibrary } from './catalog';
import { listMessages, readInteractionDraft, saveInteractionDraft } from '../chat-api';
import type { Message } from '../chat-types';
import type { InteractionReplyInput } from './types';
import { useTranslation } from '../../../i18n';
import './interactive-card.css';
import { InteractionSubmissionError } from './submission-error';

export interface InteractiveSelection {
  conversationId: string;
  source_message_id: string;
  state: Record<string, unknown>;
  editedAt: number;
}
export interface InteractiveCardProps {
  message: Message;
  readOnly?: boolean;
  submittedMessageId?: string;
  onUseReplyDraft?(draft: NonNullable<Message["reply_draft"]>, text: string): void;
  onSelect(selection: InteractiveSelection): void;
  onSend(input: InteractionReplyInput, key: string): Promise<unknown>;
}

class RenderBoundary extends Component<{ children: React.ReactNode; fallback: React.ReactNode }, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

/** Render public source while keeping edits private until an explicit continuation. */
export function InteractiveCard({message, readOnly, submittedMessageId, onSelect, onSend, onUseReplyDraft}: InteractiveCardProps) {
  const { t } = useTranslation();
  const [loaded, setLoaded] = useState(false);
  const [initial, setInitial] = useState<Record<string, unknown>>({});
  const [generation, setGeneration] = useState(0);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [applyingDraft, setApplyingDraft] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [error, setError] = useState<'load'|'save'|'conflict'|'send'|'render'|'alreadySubmitted'|'stale'|'action'|null>(null);
  const [submissionConflict, setSubmissionConflict] = useState<InteractionSubmissionError|null>(null);
  const state = useRef<Record<string, unknown>>({});
  const revision = useRef(0);
  const touched = useRef(false);
  const lastEditedAt = useRef(0);
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
  const selectRef = useRef(onSelect); selectRef.current = onSelect;
  const select = (value: Record<string, unknown>, editedAt = Date.now()) => selectRef.current({
    conversationId: message.conversation_id, source_message_id: message.id,
    state: value, editedAt,
  });
  function updateReplyText() {
    const value = message.reply_draft ? state.current[message.reply_draft.field_name] : undefined;
    setReplyText(typeof value === 'string' ? value : '');
  }
  async function useReplyDraft() {
    if (!message.reply_draft || !onUseReplyDraft || lockedRef.current || applyingDraft) return;
    clearTimeout(timer.current);
    setApplyingDraft(true);
    try {
      // Persist the same private edits before navigation unmounts this card.
      await saveRequest.current?.catch(() => undefined);
      await save();
      if (dirty.current || saving.current) return;
      const value = state.current[message.reply_draft.field_name];
      if (typeof value === 'string' && value.trim()) onUseReplyDraft(message.reply_draft, value);
    } finally { setApplyingDraft(false); }
  }
  async function load() {
    setError(null);
    try {
      const draft = await readInteractionDraft(message.conversation_id, message.id);
      state.current = draft.state; revision.current = draft.draft_revision;
      updateReplyText();
      setInitial(draft.state); setDone(Boolean(draft.submission_message_id));
      setGeneration(value => value + 1); setLoaded(true); dirty.current = false;
      touched.current = false;
      lastEditedAt.current = draft.updated_at ? Date.parse(draft.updated_at) : 0;
      if (!readOnly) select(draft.state, lastEditedAt.current);
    } catch { setError('load'); }
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

  async function save() {
    if (saving.current || lockedRef.current || !dirty.current || pending.current) return;
    saving.current = true;
    dirty.current = false;
    const value = state.current;
    try {
      saveRequest.current = saveInteractionDraft(message.conversation_id, message.id, revision.current, value);
      const result = await saveRequest.current;
      revision.current = result.draft_revision;
      setError(null);
    } catch (e) {
      dirty.current = true;
      setError(String(e).includes('409') ? 'conflict' : 'save');
    } finally { saving.current = false; saveRequest.current = null; }
    // An edit during an in-flight save must persist with the newly returned revision.
    if (state.current !== value && dirty.current) void save();
  }
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
    if (action.type === 'open_url') {
      try { const url=new URL(String(action.params.url)); if (!['https:','http:'].includes(url.protocol)) throw new Error('Unsupported URL'); window.open(url.href,'_blank','noopener,noreferrer'); }
      catch { setError('action'); }
      return;
    }
    if (action.type === 'nano_continue' && typeof action.params.action_id === 'string') {
      void submit({action_id:action.params.action_id}, action.formState).catch(() => undefined); return;
    }
    if (action.type === 'continue_conversation') {
      void submit({event:{type:'continue_conversation',message:action.humanFriendlyMessage,context:action.params.context,
        form_name:action.formName,label:actionLabel.current || t('chat.interactive.ask')}}, action.formState).catch(() => undefined); return;
    }
    setError('action');
  }
  const fallback = <p role="status">{t('chat.interactive.fallback')}</p>;
  return <section className="interactive-card" aria-label={t('chat.interactive.title')}
    onClickCapture={event => {
      touched.current = true;
      const target = event.target instanceof Element ? event.target.closest('button,[role="button"],a,[tabindex]') : null;
      actionLabel.current = (target?.getAttribute('aria-label') || target?.textContent || '').trim();
    }}
    onTouchStart={e => e.stopPropagation()} onContextMenu={e => e.stopPropagation()}
    onPointerDownCapture={() => { touched.current = true; }} onKeyDownCapture={() => { touched.current = true; }}
    onChangeCapture={() => { touched.current = true; }}>
    {!loaded && !error && <p role="status">{t('chat.interactive.loading')}</p>}
    {loaded && error !== 'render' && <RenderBoundary fallback={fallback}>
      <fieldset disabled={busy || applyingDraft || Boolean(pending.current)} className="interactive-card-fields">
        <ThemeProvider mode="light" lightTheme={interactiveTheme} cssSelector=".interactive-card">
        <Renderer key={generation} response={message.interactive!.source} library={interactiveLibrary}
          initialState={initial} isStreaming={busy || Boolean(pending.current)} toolProvider={toolProvider} publishObservability={false}
          onParseResult={parsed => {
            state.current = {...parsed?.stateDeclarations, ...state.current};
            updateReplyText();
            if (!lockedRef.current) select(state.current, lastEditedAt.current);
          }}
          onError={errors => { if (errors.some(error => error.source === 'parser')) setError('render'); }}
          onStateUpdate={value => {
            state.current = value;
            updateReplyText();
            if (lockedRef.current || pending.current) return;
            if (touched.current) lastEditedAt.current = Date.now();
            select(value, lastEditedAt.current);
            if (!touched.current) return;
            dirty.current = true; setDone(false);
            clearTimeout(timer.current); timer.current = setTimeout(() => { void save(); }, 500);
          }}
          onAction={onAction} />
        </ThemeProvider>
      </fieldset>
    </RenderBoundary>}
    {error === 'render' && fallback}
    {message.reply_draft && onUseReplyDraft && loaded && error !== 'render' && <div className="interactive-card-status">
      {message.reply_draft.possible_stale && <p role="status">{t('pa.draftStale')}</p>}
      <button type="button" disabled={locked || busy || applyingDraft || !replyText.trim()} onClick={() => void useReplyDraft()}>{t('pa.useDraft')}</button>
    </div>}
    {(locked || busy || done || error) && <div className="interactive-card-status" aria-live="polite">
      {locked ? t('chat.interactive.readOnly') : busy ? t('chat.interactive.sending') : done ? t('chat.interactive.submitted') : null}
      {error && error !== 'render' && <span role="alert">{t(`chat.interactive.${error}Error`)}</span>}
      {submissionConflict?.submissionMessageId && <a href={`/chat/${encodeURIComponent(message.conversation_id)}?message_id=${encodeURIComponent(submissionConflict.submissionMessageId)}`}>{t('chat.interactive.previousSubmission')}</a>}
      {error === 'load' && <button type="button" onClick={() => void load()}>{t('chat.interactive.retry')}</button>}
      {error === 'save' && <button type="button" onClick={() => void save()}>{t('chat.interactive.retry')}</button>}
      {error === 'send' && <button type="button" onClick={() => void submit().catch(() => undefined)}>{t('chat.interactive.retry')}</button>}
      {error === 'conflict' && <button type="button" onClick={() => void load()}>{t('chat.interactive.loadLatest')}</button>}
    </div>}
  </section>;
}
