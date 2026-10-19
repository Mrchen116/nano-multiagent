import React, { Component, useEffect, useRef, useState } from 'react';
import { Renderer } from '@openuidev/react-lang';
import '@openuidev/react-ui/defaults.css';
import '@openuidev/react-ui/components.css';
import { interactiveLibrary } from './catalog';
import { readInteractionDraft, saveInteractionDraft } from '../chat-api';
import type { Message } from '../chat-types';
import type { InteractionReplyInput } from './types';
import { useTranslation } from '../../../i18n';
import './interactive-card.css';
import { InteractionSubmissionError } from './submission-error';

export interface InteractiveSelection {
  conversationId: string;
  source_message_id: string;
  title: string;
  state: Record<string, unknown>;
  editedAt: number;
}
export interface InteractiveCardProps {
  message: Message;
  readOnly?: boolean;
  submitted?: boolean;
  onSelect(selection: InteractiveSelection): void;
  onSend(input: InteractionReplyInput, key: string): Promise<unknown>;
}

class RenderBoundary extends Component<{ children: React.ReactNode; fallback: React.ReactNode }, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

/** Render public source while keeping edits private until an explicit continuation. */
export function InteractiveCard({message, readOnly, submitted, onSelect, onSend}: InteractiveCardProps) {
  const { t } = useTranslation();
  const [loaded, setLoaded] = useState(false);
  const [initial, setInitial] = useState<Record<string, unknown>>({});
  const [generation, setGeneration] = useState(0);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<'load'|'save'|'conflict'|'send'|'render'|'alreadySubmitted'|'stale'|null>(null);
  const [submissionConflict, setSubmissionConflict] = useState<InteractionSubmissionError|null>(null);
  const [saved, setSaved] = useState(false);
  const state = useRef<Record<string, unknown>>({});
  const revision = useRef(0);
  const touched = useRef(false);
  const dirty = useRef(false);
  const saving = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pending = useRef<{input: InteractionReplyInput; key: string}|null>(null);
  const locked = Boolean(readOnly || submitted || done || submissionConflict);
  const lockedRef = useRef(locked);
  lockedRef.current = locked;
  const selectRef = useRef(onSelect); selectRef.current = onSelect;
  const select = (value: Record<string, unknown>, editedAt = Date.now()) => selectRef.current({
    conversationId: message.conversation_id, source_message_id: message.id,
    title: message.content, state: value, editedAt,
  });
  async function load() {
    setError(null);
    try {
      const draft = await readInteractionDraft(message.conversation_id, message.id);
      state.current = draft.state; revision.current = draft.draft_revision;
      setInitial(draft.state); setDone(Boolean(draft.submission_message_id));
      setGeneration(value => value + 1); setLoaded(true); dirty.current = false;
      touched.current = false;
      if (draft.updated_at && !draft.submission_message_id && !readOnly) select(draft.state, Date.parse(draft.updated_at));
    } catch { setError('load'); }
  }
  useEffect(() => { void load(); return () => clearTimeout(timer.current); }, [message.id]);

  async function save() {
    if (saving.current || lockedRef.current || !dirty.current || pending.current) return;
    saving.current = true;
    dirty.current = false;
    const value = state.current;
    try {
      const result = await saveInteractionDraft(message.conversation_id, message.id, revision.current, value);
      revision.current = result.draft_revision;
      setSaved(true); setError(null);
    } catch (e) {
      dirty.current = true;
      setError(String(e).includes('409') ? 'conflict' : 'save');
    } finally { saving.current = false; }
    // An edit during an in-flight save must persist with the newly returned revision.
    if (state.current !== value && dirty.current) void save();
  }
  async function submit(actionId?: string) {
    if (locked || busy) return;
    if (!pending.current) pending.current = {input: {source_message_id: message.id, action_id: actionId, state: structuredClone(state.current)}, key: crypto.randomUUID()};
    clearTimeout(timer.current); setBusy(true); setError(null);
    try {
      await onSend(pending.current.input, pending.current.key);
      setDone(true); pending.current = null; dirty.current = false;
    } catch (e) {
      if (e instanceof InteractionSubmissionError) {
        pending.current = null; dirty.current = false;
        setSubmissionConflict(e); setError(e.reason);
      } else setError('send');
    }
    finally { setBusy(false); }
  }
  const fallback = <p role="status">{t('chat.interactive.fallback')}</p>;
  return <section className="interactive-card" aria-label={t('chat.interactive.title')}
    onTouchStart={e => e.stopPropagation()} onContextMenu={e => e.stopPropagation()}
    onPointerDownCapture={() => { touched.current = true; }} onKeyDownCapture={() => { touched.current = true; }}
    onChangeCapture={() => { touched.current = true; }}>
    {!loaded && !error && <p role="status">{t('chat.interactive.loading')}</p>}
    {loaded && error !== 'render' && <RenderBoundary fallback={fallback}>
      <fieldset disabled={locked || busy || Boolean(pending.current)} className="interactive-card-fields">
        <Renderer key={generation} response={message.interactive!.source} library={interactiveLibrary}
          initialState={initial} isStreaming={locked || busy || Boolean(pending.current)} publishObservability={false}
          onError={errors => { if (errors.length) setError('render'); }}
          onStateUpdate={value => {
            state.current = value;
            if (!touched.current || lockedRef.current || pending.current) return;
            dirty.current = true; setSaved(false); select(value);
            clearTimeout(timer.current); timer.current = setTimeout(() => { void save(); }, 500);
          }}
          onAction={action => {
            const id = action.params?.action_id;
            if (action.type === 'nano_continue' && typeof id === 'string') void submit(id);
          }} />
      </fieldset>
    </RenderBoundary>}
    {error === 'render' && fallback}
    <div className="interactive-card-status" aria-live="polite">
      {locked ? t(submitted || done ? 'chat.interactive.submitted' : 'chat.interactive.readOnly') : busy ? t('chat.interactive.sending') : saved ? t('chat.interactive.saved') : null}
      {error && error !== 'render' && <span role="alert">{t(`chat.interactive.${error}Error`)}</span>}
      {submissionConflict?.submissionMessageId && <a href={`/chat/${encodeURIComponent(message.conversation_id)}?message_id=${encodeURIComponent(submissionConflict.submissionMessageId)}`}>{t('chat.interactive.previousSubmission')}</a>}
      {error === 'load' && <button type="button" onClick={() => void load()}>{t('chat.interactive.retry')}</button>}
      {error === 'save' && <button type="button" onClick={() => void save()}>{t('chat.interactive.retry')}</button>}
      {error === 'send' && <button type="button" onClick={() => void submit()}>{t('chat.interactive.retry')}</button>}
      {error === 'conflict' && <button type="button" onClick={() => void load()}>{t('chat.interactive.loadLatest')}</button>}
    </div>
  </section>;
}
