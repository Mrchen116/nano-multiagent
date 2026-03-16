import { ChangeEvent, Dispatch, FormEvent, KeyboardEvent, SetStateAction, SyntheticEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  ChatAttachment,
  ChatMessage,
  ChatStarter,
  ChatUsageView,
  ConversationDetail,
  MentionCandidate,
  UsageAgentView,
  UsageTotals
} from "../types";
import { getSendAvailabilityMessages, SendAvailability } from "../im-chat-api";

const SEND_AVAILABILITY_MESSAGES = getSendAvailabilityMessages();
const RELAY_UNAVAILABLE_MESSAGE = SEND_AVAILABILITY_MESSAGES.unavailableHelperText;

function toErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    if (error.message.includes("target_node_id is not connected")) {
      return RELAY_UNAVAILABLE_MESSAGE;
    }
    return error.message;
  }
  return RELAY_UNAVAILABLE_MESSAGE;
}

function getFailureAppearance(sendAvailability: SendAvailability) {
  if (sendAvailability.state === "unbound") {
    return {
      title: SEND_AVAILABILITY_MESSAGES.failureTitle,
      actionLabel: "Open bind flow",
      helperText: sendAvailability.helperText
    };
  }
  if (sendAvailability.state === "offline") {
    return {
      title: SEND_AVAILABILITY_MESSAGES.failureTitle,
      actionLabel: "Bring Gateway online",
      helperText: sendAvailability.helperText
    };
  }
  return {
    title: SEND_AVAILABILITY_MESSAGES.failureTitle,
    actionLabel: "Retry delivery",
    helperText: RELAY_UNAVAILABLE_MESSAGE
  };
}

function FailureStateBanner({ sendAvailability }: { sendAvailability: SendAvailability }) {
  if (sendAvailability.canSend || !sendAvailability.helperText) {
    return null;
  }
  const appearance = getFailureAppearance(sendAvailability);
  return (
    <div role="alert" className="mb-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <p className="font-semibold text-amber-950">{appearance.title}</p>
      <p className="mt-1">{appearance.helperText}</p>
      <p className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-amber-800">Next: {appearance.actionLabel}</p>
    </div>
  );
}

function SendErrorBanner(props: { message: string; onRetry: () => void; isRetrying: boolean }) {
  return (
    <div role="alert" className="mb-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-rose-900">{SEND_AVAILABILITY_MESSAGES.failureTitle}</p>
          <p className="mt-1">{props.message}</p>
          <p className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-rose-700">Next: Retry delivery</p>
        </div>
        <button type="button" className="im-btn im-btn-muted" onClick={props.onRetry} disabled={props.isRetrying}>
          Retry send
        </button>
      </div>
    </div>
  );
}

function UploadErrorBanner(props: {
  message: string;
  fileName: string;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  return (
    <div role="alert" className="mb-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-amber-950">Attachment upload failed</p>
          <p className="mt-1">{props.message}</p>
          <p className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-amber-800">Next: Retry upload</p>
        </div>
        <button type="button" className="im-btn im-btn-muted" onClick={props.onRetry} disabled={props.isRetrying}>
          {`Retry upload ${props.fileName}`}
        </button>
      </div>
    </div>
  );
}

function toUploadErrorMessage(fileName: string, error: unknown) {
  if (error instanceof Error && error.message) {
    return `Couldn't upload ${fileName}. ${error.message}`;
  }
  return `Couldn't upload ${fileName}. Try again.`;
}

function toDeliveryStatusCopy(message: ChatMessage) {
  switch (message.delivery_status) {
    case "sent":
      return {
        label: message.is_mine ? "Sent to relay" : "Delivered",
        hint: message.is_mine ? "Your message left this device and is waiting for agent work." : null
      };
    case "running":
      return {
        label: "Agent is working",
        hint: "The relay accepted your request and the agent is still processing it."
      };
    case "completed":
      return {
        label: message.sender_type === "agent" ? "Agent replied" : "Delivered",
        hint: message.sender_type === "agent" ? "The latest agent response finished successfully." : null
      };
    case "failed":
      return {
        label: message.sender_type === "agent" ? "Agent couldn't finish" : "Didn't send",
        hint:
          message.recovery_hint ??
          (message.sender_type === "agent"
            ? "The agent stopped before finishing this turn. Retry the request to ask the agent again."
            : "The message did not reach the relay. Retry after the connection is back."),
        actionLabel: message.recovery_action_label ?? "Retry"
      };
    default:
      return null;
  }
}

interface FailedUploadState {
  file: File;
  message: string;
}

function removeAttachmentAt(attachments: ChatAttachment[], indexToRemove: number) {
  return attachments.filter((_, index) => index !== indexToRemove);
}

function canSubmitMessage(input: {
  draft: string;
  attachments: ChatAttachment[];
  canSend: boolean;
  isUploading: boolean;
  isMentionMenuOpen: boolean;
  isSending: boolean;
}) {
  return !((!input.draft.trim() && input.attachments.length === 0) || !input.canSend || input.isUploading || input.isMentionMenuOpen || input.isSending);
}

function isTextAreaElement(target: EventTarget | null): target is HTMLTextAreaElement {
  return target instanceof HTMLTextAreaElement;
}

function requestSubmitFromTarget(target: EventTarget | null) {
  if (!isTextAreaElement(target)) {
    return;
  }
  target.form?.requestSubmit();
}

function retrySubmitFromForm(form: HTMLFormElement | null) {
  form?.requestSubmit();
}

function retryUploadAction(retry: () => void) {
  retry();
}

function retrySendAction(retry: () => void) {
  retry();
}

function submitOnEnter(event: KeyboardEvent<HTMLTextAreaElement>) {
  if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
    return false;
  }
  event.preventDefault();
  requestSubmitFromTarget(event.currentTarget);
  return true;
}

function removePendingAttachmentAction(input: {
  index: number;
  attachments: ChatAttachment[];
  setPendingAttachments: Dispatch<SetStateAction<ChatAttachment[]>>;
}) {
  input.setPendingAttachments(removeAttachmentAt(input.attachments, input.index));
}

function retryPendingUpload(input: {
  failedUpload: FailedUploadState | null;
  uploadFile: (file: File) => Promise<void>;
}) {
  if (!input.failedUpload) {
    return Promise.resolve();
  }
  return input.uploadFile(input.failedUpload.file);
}

function PendingStatusHint(props: { canSend: boolean; isUploading: boolean; hasAttachments: boolean }) {
  if (props.isUploading) {
    return <p className="mt-2 text-xs text-slate-500">Attachment upload in progress. Send unlocks when the upload finishes.</p>;
  }
  if (props.hasAttachments) {
    return <p className="mt-2 text-xs text-slate-500">Attachments stay in the draft until you send or remove them.</p>;
  }
  if (!props.canSend) {
    return null;
  }
  return <p className="mt-2 text-xs text-slate-500">Press Enter to send. Press Shift+Enter for a new line.</p>;
}

function AttachmentLinks({ attachments, muted = false }: { attachments: ChatAttachment[]; muted?: boolean }) {
  if (attachments.length === 0) {
    return null;
  }
  return (
    <ul className="mt-2 space-y-1 text-xs">
      {attachments.map((attachment) => (
        <li key={`${attachment.url}:${attachment.file_name ?? "file"}`}>
          <a
            href={attachment.url}
            target="_blank"
            rel="noreferrer"
            className={muted ? "underline underline-offset-2 opacity-80" : "underline underline-offset-2"}
          >
            {attachment.file_name ?? attachment.url}
          </a>
        </li>
      ))}
    </ul>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const mine = message.is_mine ?? message.sender_type === "user";
  const attachments = message.attachments ?? [];
  const deliveryStatus = toDeliveryStatusCopy(message);
  return (
    <div className={`mb-3 flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={[
          "max-w-[80%] rounded-2xl px-3 py-2 text-sm",
          mine ? "bg-[#0f766e] text-white" : "bg-[#e5ebf2] text-slate-900"
        ].join(" ")}
      >
        <p className="text-[11px] opacity-75">{message.sender_name ?? message.sender_type}</p>
        {message.content ? <p className="mt-1 whitespace-pre-wrap">{message.content}</p> : null}
        <AttachmentLinks attachments={attachments} muted={mine} />
        {deliveryStatus && (
          <div className="mt-2 rounded-xl border border-black/10 bg-black/5 px-2 py-1 text-[10px] leading-4">
            <p className="font-semibold tracking-wide opacity-80">{deliveryStatus.label}</p>
            {deliveryStatus.hint ? <p className="mt-1 opacity-75">{deliveryStatus.hint}</p> : null}
            {deliveryStatus.actionLabel ? <p className="mt-1 font-semibold opacity-80">Recovery: {deliveryStatus.actionLabel}</p> : null}
          </div>
        )}
      </div>
    </div>
  );
}

function UsageCard(props: { label: string; totals: UsageTotals }) {
  return (
    <div className="rounded-2xl border border-[var(--im-border)] bg-slate-50 px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">{props.label}</p>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
        <span>{props.totals.turns} turns</span>
        <span>{props.totals.totalTokens} tokens</span>
        <span>Prompt {props.totals.promptTokens}</span>
        <span>Completion {props.totals.completionTokens}</span>
      </div>
    </div>
  );
}

function AgentUsagePanel(props: { agents: UsageAgentView[] }) {
  const [activeAgentId, setActiveAgentId] = useState<string | null>(props.agents[0]?.agentId ?? null);

  useEffect(() => {
    if (!props.agents.some((agent) => agent.agentId === activeAgentId)) {
      setActiveAgentId(props.agents[0]?.agentId ?? null);
    }
  }, [activeAgentId, props.agents]);

  if (props.agents.length === 0) {
    return null;
  }

  const activeAgent = props.agents.find((agent) => agent.agentId === activeAgentId) ?? props.agents[0];
  return (
    <div className="mt-2 rounded-2xl border border-[var(--im-border)] bg-white px-3 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">By agent</p>
      <div className="mt-2 flex flex-wrap gap-2" role="tablist" aria-label="Agent usage views">
        {props.agents.map((agent) => {
          const selected = agent.agentId === activeAgent.agentId;
          return (
            <button
              key={agent.agentId}
              type="button"
              role="tab"
              aria-selected={selected}
              className={[
                "rounded-full border px-3 py-1 text-xs font-semibold",
                selected
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-slate-50 text-slate-600"
              ].join(" ")}
              onClick={() => setActiveAgentId(agent.agentId)}
            >
              {agent.label}
            </button>
          );
        })}
      </div>
      <div className="mt-3">
        <UsageCard label={`Agent · ${activeAgent.label}`} totals={activeAgent.totals} />
      </div>
    </div>
  );
}

function UsageStrip(props: { usage: ChatUsageView }) {
  return (
    <div className="border-b border-[var(--im-border)] px-4 py-3">
      <div className="grid gap-2 md:grid-cols-2">
        <UsageCard label="This chat" totals={props.usage.conversation} />
        <UsageCard label="Workspace total" totals={props.usage.workspace} />
      </div>
      <AgentUsagePanel agents={props.usage.agents} />
    </div>
  );
}

const STABLE_MENTION_PREFIX = "@agent:";

function formatMention(agentId: string) {
  return `${STABLE_MENTION_PREFIX}${agentId}`;
}

function getMentionQuery(draft: string, selectionStart = draft.length): { start: number; query: string } | null {
  const beforeCursor = draft.slice(0, selectionStart);
  const match = /(?:^|\s)@([^\s@]*)$/.exec(beforeCursor);
  if (!match || typeof match.index !== "number") {
    return null;
  }
  const start = match.index + match[0].lastIndexOf("@");
  return {
    start,
    query: match[1] ?? ""
  };
}

function getMentionTokenRange(draft: string, selectionStart: number, selectionEnd: number): { start: number; end: number } | null {
  if (selectionStart !== selectionEnd || selectionStart === 0) {
    return null;
  }
  const mentionPattern = /(^|\s)(@agent:[^\s@]+)(?=\s|$)/g;
  let match: RegExpExecArray | null = mentionPattern.exec(draft);
  while (match) {
    const whitespacePrefix = match[1] ?? "";
    const mentionText = match[2] ?? "";
    const start = match.index + whitespacePrefix.length;
    const end = start + mentionText.length;
    const tokenEnd = end < draft.length && draft[end] === " " ? end + 1 : end;
    if (selectionStart === tokenEnd) {
      return { start, end: tokenEnd };
    }
    match = mentionPattern.exec(draft);
  }
  return null;
}

function buildMentionCandidates(detail: ConversationDetail | null): MentionCandidate[] {
  return detail?.mention_candidates ?? [];
}

function PendingAttachments(props: {
  attachments: ChatAttachment[];
  isUploading: boolean;
  onRemove: (index: number) => void;
}) {
  if (props.attachments.length === 0 && !props.isUploading) {
    return null;
  }
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      {props.attachments.map((attachment, index) => {
        const label = attachment.file_name ?? attachment.url;
        return (
          <span
            key={`${attachment.url}:${attachment.file_name ?? "pending"}:${index}`}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
          >
            <span>{label}</span>
            <button
              type="button"
              className="rounded-full px-1 text-slate-500 transition hover:bg-slate-200 hover:text-slate-900"
              aria-label={`Remove attachment ${label}`}
              onClick={() => props.onRemove(index)}
            >
              ×
            </button>
          </span>
        );
      })}
      {props.isUploading && (
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">Uploading…</span>
      )}
    </div>
  );
}

function DefaultAgentStarterCard({ starter }: { starter: ChatStarter }) {
  return (
    <section className="im-card flex h-full min-h-[420px] flex-col justify-center gap-4 px-6 py-6 text-slate-700">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Default chat</p>
        <h2 className="im-title mt-2 text-2xl font-bold">{starter.title}</h2>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">{starter.description}</p>
      </div>
      <dl className="grid gap-2 text-sm text-slate-500">
        <div className="flex items-center gap-2">
          <dt className="font-semibold text-slate-700">Agent</dt>
          <dd>{starter.agentName}</dd>
        </div>
        {starter.nodeLabel && (
          <div className="flex items-center gap-2">
            <dt className="font-semibold text-slate-700">Node</dt>
            <dd>{starter.nodeLabel}</dd>
          </div>
        )}
        {starter.statusLabel && (
          <div className="flex items-center gap-2">
            <dt className="font-semibold text-slate-700">Gateway status</dt>
            <dd>{starter.statusLabel}</dd>
          </div>
        )}
      </dl>
      <div className="rounded-2xl border border-[var(--im-border)] bg-slate-50 px-4 py-3 text-sm text-slate-600">
        <p className="font-semibold text-slate-800">Need a different target?</p>
        <p className="mt-1">Reuse each agent's dedicated direct chat from Settings, or open group chats and agent-to-agent threads from the conversation list.</p>
      </div>
      <div>
        <Link to={starter.actionHref} className="im-btn im-btn-primary inline-flex" aria-label={starter.actionLabel}>
          {starter.actionLabel}
        </Link>
      </div>
    </section>
  );
}

function EmptyWorkspaceState() {
  return (
    <section className="im-card hidden h-full min-h-[420px] items-center justify-center px-6 py-6 lg:flex">
      <div className="max-w-md text-center text-slate-600">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Workspace ready</p>
        <h2 className="im-title mt-2 text-2xl font-bold text-slate-900">Open a conversation to review context and reply</h2>
        <p className="mt-3 text-sm">
          Pick a thread from the conversation list to inspect history, compare usage, and continue the discussion without losing context.
        </p>
      </div>
    </section>
  );
}

function EmptyThreadState() {
  return (
    <div className="flex min-h-full items-center justify-center py-10">
      <div className="max-w-sm text-center text-slate-500">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">No messages yet</p>
        <p className="mt-2 text-sm">This conversation is ready for the first message. Replies and status updates will appear here.</p>
      </div>
    </div>
  );
}

export function MessagePane(props: {
  detail: ConversationDetail | null;
  starter?: ChatStarter | null;
  isMobile: boolean;
  isSending: boolean;
  isStartingFreshSession: boolean;
  sendAvailability: SendAvailability;
  usage: ChatUsageView;
  onSend: (payload: { content: string; attachments: ChatAttachment[] }) => Promise<unknown>;
  onStartFreshSession?: (agentId: string) => Promise<unknown>;
  onUploadAttachment: (file: File) => Promise<ChatAttachment>;
}) {
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const [failedUpload, setFailedUpload] = useState<FailedUploadState | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<ChatAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [activeMentionIndex, setActiveMentionIndex] = useState(0);
  const listRef = useRef<HTMLDivElement | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const [composerSelection, setComposerSelection] = useState({ start: 0, end: 0 });

  const mentionCandidates = useMemo(() => buildMentionCandidates(props.detail), [props.detail]);
  const mentionQuery = useMemo(() => getMentionQuery(draft, composerSelection.start), [draft, composerSelection.start]);
  const filteredMentionCandidates = useMemo(() => {
    if (!mentionQuery || mentionCandidates.length === 0) {
      return [];
    }
    const normalizedQuery = mentionQuery.query.trim().toLowerCase();
    if (!normalizedQuery) {
      return mentionCandidates;
    }
    return mentionCandidates.filter((candidate) => {
      const stableMention = formatMention(candidate.agentId).toLowerCase();
      return candidate.label.toLowerCase().includes(normalizedQuery) || stableMention.includes(normalizedQuery);
    });
  }, [mentionCandidates, mentionQuery]);
  const isMentionMenuOpen = props.detail?.kind_label === "Group chat" && filteredMentionCandidates.length > 0 && Boolean(mentionQuery);

  useEffect(() => {
    if (!props.detail) {
      return;
    }
    const node = listRef.current;
    if (!node) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [props.detail, props.detail?.messages.length]);

  useEffect(() => {
    if (!isMentionMenuOpen) {
      setActiveMentionIndex(0);
      return;
    }
    setActiveMentionIndex((current) => Math.min(current, filteredMentionCandidates.length - 1));
  }, [filteredMentionCandidates.length, isMentionMenuOpen]);

  useEffect(() => {
    if (!composerRef.current) {
      return;
    }
    composerRef.current.setSelectionRange(composerSelection.start, composerSelection.end);
  }, [composerSelection, draft]);

  if (!props.detail) {
    if (props.starter) {
      return <DefaultAgentStarterCard starter={props.starter} />;
    }
    return <EmptyWorkspaceState />;
  }

  const uploadFile = async (file: File) => {
    setSendError(null);
    setFailedUpload(null);
    setIsUploading(true);
    try {
      const uploaded = await props.onUploadAttachment(file);
      setPendingAttachments((current) => [...current, uploaded]);
    } catch (error) {
      setFailedUpload({
        file,
        message: toUploadErrorMessage(file.name || "attachment", error)
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const onPickAttachment = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await uploadFile(file);
  };

  const selectMention = (candidate: MentionCandidate) => {
    if (!mentionQuery) {
      return;
    }
    const prefix = draft.slice(0, mentionQuery.start);
    const suffix = draft.slice(composerSelection.start);
    const mention = `${formatMention(candidate.agentId)} `;
    const nextDraft = `${prefix}${mention}${suffix}`;
    const nextSelection = prefix.length + mention.length;
    setDraft(nextDraft);
    setComposerSelection({ start: nextSelection, end: nextSelection });
    setActiveMentionIndex(0);
    setSendError(null);
  };

  const onComposerSelect = (event: SyntheticEvent<HTMLTextAreaElement>) => {
    setComposerSelection({
      start: event.currentTarget.selectionStart,
      end: event.currentTarget.selectionEnd
    });
  };

  const onComposerChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setDraft(event.target.value);
    setComposerSelection({
      start: event.target.selectionStart,
      end: event.target.selectionEnd
    });
  };

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (isMentionMenuOpen) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveMentionIndex((current) => (current + 1) % filteredMentionCandidates.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveMentionIndex((current) => (current - 1 + filteredMentionCandidates.length) % filteredMentionCandidates.length);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const candidate = filteredMentionCandidates[activeMentionIndex];
        if (candidate) {
          selectMention(candidate);
        }
        return;
      }
    }
    if (event.key === "Backspace") {
      const mentionTokenRange = getMentionTokenRange(draft, event.currentTarget.selectionStart, event.currentTarget.selectionEnd);
      if (mentionTokenRange) {
        event.preventDefault();
        const nextDraft = `${draft.slice(0, mentionTokenRange.start)}${draft.slice(mentionTokenRange.end)}`;
        setDraft(nextDraft);
        setComposerSelection({ start: mentionTokenRange.start, end: mentionTokenRange.start });
        setSendError(null);
        return;
      }
    }
    submitOnEnter(event);
  };

  const submitDraft = async () => {
    const text = draft.trim();
    if (
      !canSubmitMessage({
        draft: text,
        attachments: pendingAttachments,
        canSend: props.sendAvailability.canSend,
        isUploading,
        isMentionMenuOpen,
        isSending: props.isSending
      })
    ) {
      return;
    }
    setSendError(null);
    try {
      await props.onSend({ content: text, attachments: pendingAttachments });
      setDraft("");
      setPendingAttachments([]);
      setFailedUpload(null);
    } catch (error) {
      setSendError(toErrorMessage(error));
      // Preserve the draft and uploaded attachments so the user can retry after reading the failure feedback.
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submitDraft();
  };

  return (
    <section className="im-card flex h-full min-h-[420px] flex-col overflow-hidden">
      <div className="flex items-start gap-3 border-b border-[var(--im-border)] px-4 py-3">
        {props.isMobile && (
          <Link to="/chat" className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">
            Back
          </Link>
        )}
        <div className="min-w-0 flex-1">
          {props.detail.kind_label && (
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{props.detail.kind_label}</p>
          )}
          <h2 className="im-title text-lg font-bold">{props.detail.title}</h2>
          {props.detail.target_label && <p className="mt-1 text-xs text-slate-600">Target: {props.detail.target_label}</p>}
          {props.detail.discoverability_hint && (
            <p className="mt-1 text-xs text-slate-500">{props.detail.discoverability_hint}</p>
          )}
          {props.detail.direct_agent_id && props.onStartFreshSession ? (
            <p className="mt-1 text-xs text-slate-500">
              Existing turns in this thread keep their earlier profile snapshot. Start a fresh session to verify newly saved prompt changes without rewriting this history.
            </p>
          ) : null}
          {props.detail.ownership_label && (
            <p className="mt-1 text-xs text-slate-500">{props.detail.ownership_label}</p>
          )}
        </div>
        {props.detail.direct_agent_id && props.onStartFreshSession ? (
          <button
            type="button"
            className="im-btn im-btn-muted shrink-0"
            disabled={props.isStartingFreshSession}
            onClick={() => void props.onStartFreshSession?.(props.detail!.direct_agent_id!)}
          >
            {props.isStartingFreshSession ? "Starting fresh session…" : "Start fresh session"}
          </button>
        ) : null}
      </div>
      <UsageStrip usage={props.usage} />
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-4">
        <div data-testid="message-list-stack" className="flex min-h-full flex-col justify-end">
          {props.detail.messages.length === 0 ? (
            <EmptyThreadState />
          ) : (
            props.detail.messages.map((message) => <MessageBubble key={message.message_id} message={message} />)
          )}
        </div>
      </div>
      <form ref={formRef} className="border-t border-[var(--im-border)] p-3" onSubmit={onSubmit}>
        <FailureStateBanner sendAvailability={props.sendAvailability} />
        {failedUpload && (
          <UploadErrorBanner
            message={failedUpload.message}
            fileName={failedUpload.file.name || "attachment"}
            onRetry={() => retryUploadAction(() => void retryPendingUpload({ failedUpload, uploadFile }))}
            isRetrying={isUploading}
          />
        )}
        {sendError && <SendErrorBanner message={sendError} onRetry={() => retrySendAction(() => retrySubmitFromForm(formRef.current))} isRetrying={props.isSending} />}
        <PendingAttachments
          attachments={pendingAttachments}
          isUploading={isUploading}
          onRemove={(index) => removePendingAttachmentAction({ index, attachments: pendingAttachments, setPendingAttachments })}
        />
        <div className="relative flex items-end gap-2">
          <label className="im-btn im-btn-muted cursor-pointer">
            <span aria-hidden="true">+</span>
            <span className="sr-only">Attachment picker</span>
            <input
              ref={fileInputRef}
              type="file"
              className="sr-only"
              aria-label="Attachment picker"
              onChange={onPickAttachment}
            />
          </label>
          <div className="relative flex-1">
            <textarea
              ref={composerRef}
              className="im-input min-h-24 max-h-56 w-full resize-y"
              placeholder={props.sendAvailability.placeholder}
              value={draft}
              rows={3}
              disabled={!props.sendAvailability.canSend}
              onChange={onComposerChange}
              onClick={onComposerSelect}
              onKeyUp={onComposerSelect}
              onSelect={onComposerSelect}
              onKeyDown={onComposerKeyDown}
              aria-expanded={isMentionMenuOpen}
              aria-controls={isMentionMenuOpen ? "mention-candidate-list" : undefined}
              aria-autocomplete={props.detail.kind_label === "Group chat" ? "list" : undefined}
            />
            {isMentionMenuOpen && (
              <div
                id="mention-candidate-list"
                role="listbox"
                aria-label="Mention candidates"
                className="absolute bottom-full left-0 z-10 mb-2 w-full rounded-2xl border border-[var(--im-border)] bg-white p-2 shadow-lg"
              >
                {filteredMentionCandidates.map((candidate, index) => {
                  const isActive = index === activeMentionIndex;
                  return (
                    <button
                      key={candidate.agentId}
                      type="button"
                      role="option"
                      aria-selected={isActive}
                      className={[
                        "flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm",
                        isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-50"
                      ].join(" ")}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        selectMention(candidate);
                      }}
                    >
                      <span className="font-medium">{candidate.label}</span>
                      <span className={isActive ? "text-slate-200" : "text-slate-400"}>{formatMention(candidate.agentId)}</span>
                    </button>
                  );
                })}
              </div>
            )}
            <PendingStatusHint
              canSend={props.sendAvailability.canSend}
              isUploading={isUploading}
              hasAttachments={pendingAttachments.length > 0}
            />
          </div>
          <button
            type="submit"
            className="im-btn im-btn-primary"
            disabled={props.isSending || !props.sendAvailability.canSend || isUploading}
          >
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
