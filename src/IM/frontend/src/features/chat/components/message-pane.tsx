// @deprecated v1 chat surface. Production router (src/app/router.tsx:5) mounts
// `features/chat/v2/components/message-pane.tsx`; this file remains only to
// keep its dedicated vitest suites (≥ 20 tests) compiling. M19/R6 visual
// rewrite landed here by mistake — superseded by R8.5 on the v2 path.
// TODO(feat-340-v2-cleanup): drop this file + v1 test suites after the v2
// surface fully replaces it (R12+ scope).
import { ChangeEvent, Dispatch, FormEvent, KeyboardEvent, SetStateAction, SyntheticEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  ChatAttachment,
  ChatMessage,
  ChatStarter,
  ChatTokenUsage,
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
  if (message.sender_type === "agent" && message.delivery_status === "completed" && !message.content?.trim()) {
    return null;
  }
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
        label: "Delivered",
        hint: null
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

function getGroupMessageSenderLabel(message: ChatMessage) {
  if (message.sender_display_name) {
    return message.sender_display_name;
  }
  if (message.sender_name && message.sender_name !== message.sender_user_id) {
    return message.sender_name;
  }
  if (message.sender_type === "agent") {
    return "Agent";
  }
  if (message.sender_type === "system") {
    return "System";
  }
  return "Participant";
}

function formatMessageTimestamp(createdAt: string) {
  const timestamp = new Date(createdAt);
  if (Number.isNaN(timestamp.getTime())) {
    throw new Error(`Invalid message timestamp: ${createdAt}`);
  }
  const hours = String(timestamp.getHours()).padStart(2, "0");
  const minutes = String(timestamp.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}

function avatarInitials(message: ChatMessage): string {
  const source = message.sender_display_name || message.sender_name || (message.is_mine ? "ME" : "AG");
  return source.trim().slice(0, 2).toUpperCase();
}

// M19/R11-7: prototype `im-components.jsx::TokenChip` 用 pct = round(used/window*100),
// warn >= 70% / critical >= 90%;颜色: oklch(0.52 0.14 180) 青 (normal) → oklch(0.65 0.18 60)
// 橙 (warn) → oklch(0.55 0.15 25) 红 (critical)。chip 落在气泡下方 status row。
function TokenChip({ usage }: { usage: ChatTokenUsage }) {
  const pct = Math.round((usage.context_used / usage.context_window) * 100);
  const critical = pct >= 90;
  const warn = pct >= 70;
  function fmtK(n: number) {
    return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
  }
  const colorClass = critical
    ? "text-[oklch(0.55_0.15_25)] border-[oklch(0.55_0.15_25)]"
    : warn
      ? "text-[oklch(0.55_0.16_60)] border-[oklch(0.75_0.18_60)]"
      : "text-[oklch(0.38_0.01_240)] border-[oklch(0.76_0.012_240)]";
  return (
    <span
      data-testid="token-chip"
      className={[
        "inline-flex items-center gap-[5px] rounded-full bg-[oklch(0.96_0.005_240)] px-[9px] py-[3px] font-mono text-[11px] font-semibold",
        "border",
        colorClass
      ].join(" ")}
    >
      <span>{fmtK(usage.output)} tok</span>
      <span className="opacity-40">·</span>
      <span>ctx {pct}%</span>
    </span>
  );
}

function MessageBubble({ message, isGroupChat }: { message: ChatMessage; isGroupChat: boolean }) {
  const mine = message.is_mine ?? message.sender_type === "user";
  const attachments = message.attachments ?? [];
  const deliveryStatus = toDeliveryStatusCopy(message);
  const senderLabel = isGroupChat ? getGroupMessageSenderLabel(message) : null;
  const timestampLabel = formatMessageTimestamp(message.created_at);
  const initials = avatarInitials(message);
  const tokenUsage = message.token_usage;
  return (
    <div
      className={["mb-4 flex items-start gap-[10px]", mine ? "flex-row-reverse" : "flex-row"].join(" ")}
    >
      <span
        data-testid="message-avatar"
        aria-hidden="true"
        className={[
          "flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white",
          "bg-[oklch(0.52_0.14_180)]"
        ].join(" ")}
      >
        {initials}
      </span>
      <div className={["flex max-w-[72%] min-w-0 flex-col", mine ? "items-end" : "items-start"].join(" ")}>
        {senderLabel ? (
          <span className="mb-[3px] px-[2px] text-[11px] font-bold text-[oklch(0.38_0.10_180)]">{senderLabel}</span>
        ) : null}
        <div
          data-testid="message-bubble"
          className={[
            "px-[13px] py-[9px] text-[13.5px] leading-[1.6]",
            mine
              ? "rounded-[16px_16px_4px_16px] bg-[oklch(0.52_0.14_180)] text-white"
              : "rounded-[16px_16px_16px_4px] bg-[oklch(0.91_0.007_240)] text-[oklch(0.14_0.01_240)]"
          ].join(" ")}
        >
          {message.content ? <p className="m-0 whitespace-pre-wrap break-words">{message.content}</p> : null}
          <AttachmentLinks attachments={attachments} muted={mine} />
        </div>
        <div
          className={[
            "mt-[3px] flex items-center gap-[6px]",
            mine ? "pr-[2px]" : "pl-[2px]"
          ].join(" ")}
        >
          <time
            data-testid="message-timestamp"
            dateTime={message.created_at}
            className="text-[11px] text-[oklch(0.65_0.01_240)]"
          >
            {timestampLabel}
          </time>
          {tokenUsage ? <TokenChip usage={tokenUsage} /> : null}
        </div>
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
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-b border-[var(--im-border)] px-4 py-2">
      <button
        type="button"
        className="flex w-full items-center gap-1 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 hover:text-slate-700"
        aria-expanded={expanded}
        onClick={() => setExpanded((prev) => !prev)}
      >
        <span>Usage</span>
        <span aria-hidden="true" className="text-[10px] text-slate-400">{expanded ? "▲" : "▶"}</span>
      </button>
      {expanded && (
        <div className="mt-2">
          <div className="grid gap-2 md:grid-cols-2">
            <UsageCard label="This chat" totals={props.usage.conversation} />
            <UsageCard label="Workspace total" totals={props.usage.workspace} />
          </div>
          <AgentUsagePanel agents={props.usage.agents} />
        </div>
      )}
    </div>
  );
}

const STABLE_MENTION_PREFIX = "@agent:";

function formatMention(agentId: string) {
  return `${STABLE_MENTION_PREFIX}${agentId}`;
}

function formatMentionDisplay(label: string) {
  return `@${label}`;
}

function encodeMentionDraft(draft: string, candidates: MentionCandidate[]) {
  return candidates.reduce((nextDraft, candidate) => {
    const encodedLabel = formatMentionDisplay(candidate.label);
    const stableMention = formatMention(candidate.agentId);
    return nextDraft.replaceAll(encodedLabel, stableMention);
  }, draft);
}

function getMentionDisplayTokenRange(
  draft: string,
  selectionStart: number,
  selectionEnd: number,
  candidates: MentionCandidate[]
): { start: number; end: number } | null {
  if (selectionStart !== selectionEnd || selectionStart === 0) {
    return null;
  }
  for (const candidate of candidates) {
    const displayMention = formatMentionDisplay(candidate.label);
    const mentionPattern = new RegExp(`(^|\\s)(${displayMention.replace(/[.*+?^${}()|[\\]\\]/g, "\\$&")})(?=\\s|$)`, "g");
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
  }
  return null;
}

function formatMentionSecondaryCopy(candidate: MentionCandidate) {
  return `${candidate.label} mention`;
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
  /** Called when user confirms leaving a group conversation. */
  onLeaveConversation?: (conversationId: string) => Promise<void>;
  /** Called when group creator confirms dissolving a conversation. */
  onDeleteConversation?: (conversationId: string) => Promise<void>;
  /** Whether the current user is the creator/owner of this group conversation. */
  isGroupCreator?: boolean;
  /** M235: called when user renames the group chat; receives (conversationId, newTitle). */
  onRenameConversation?: (conversationId: string, title: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const [failedUpload, setFailedUpload] = useState<FailedUploadState | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<ChatAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [activeMentionIndex, setActiveMentionIndex] = useState(0);
  // Confirmation dialog state for leave/delete group operations (M234).
  const [confirmAction, setConfirmAction] = useState<"leave" | "delete" | null>(null);
  const [isConfirmPending, setIsConfirmPending] = useState(false);
  // M235: inline group-name edit state.
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
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
  const isGroupChat =
    props.detail?.kind_label === "Group chat" ||
    props.detail?.kind_label === "Agent-to-agent direct chat";
  const isMentionMenuOpen = isGroupChat && filteredMentionCandidates.length > 0 && Boolean(mentionQuery);

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
    const mention = `${formatMentionDisplay(candidate.label)} `;
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
      const mentionTokenRange = getMentionDisplayTokenRange(draft, event.currentTarget.selectionStart, event.currentTarget.selectionEnd, mentionCandidates);
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
    const text = encodeMentionDraft(draft.trim(), mentionCandidates);
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
    <section
      className={`im-card relative flex h-full flex-col overflow-hidden ${props.isMobile ? "min-h-0" : "min-h-[420px]"}`}
    >
      <div className="flex items-start gap-3 border-b border-[var(--im-border)] px-4 py-3">
        {props.isMobile && (
          <Link to="/chat" className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">
            Back
          </Link>
        )}
        <div className="min-w-0 flex-1">
          {/* M235: group chats show an inline-editable title; others show a plain heading */}
          {props.detail.kind_label === "Group chat" && props.onRenameConversation ? (
            isEditingTitle ? (
              <input
                className="im-input w-full text-lg font-bold"
                value={titleDraft}
                autoFocus
                onChange={(e) => setTitleDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    const trimmed = titleDraft.trim();
                    if (trimmed) {
                      void props.onRenameConversation!(props.detail!.conversation_id, trimmed);
                    }
                    setIsEditingTitle(false);
                  } else if (e.key === "Escape") {
                    setIsEditingTitle(false);
                  }
                }}
                onBlur={() => {
                  const trimmed = titleDraft.trim();
                  if (trimmed && trimmed !== props.detail!.title) {
                    void props.onRenameConversation!(props.detail!.conversation_id, trimmed);
                  }
                  setIsEditingTitle(false);
                }}
              />
            ) : (
              <div className="flex items-center gap-1">
                <h2 className="im-title text-lg font-bold">{props.detail.title}</h2>
                <button
                  type="button"
                  aria-label="编辑群聊名称"
                  className="rounded px-1 py-0.5 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  onClick={() => {
                    setTitleDraft(props.detail!.title);
                    setIsEditingTitle(true);
                  }}
                >
                  ✏
                </button>
              </div>
            )
          ) : (
            <h2 className="im-title text-lg font-bold">{props.detail.title}</h2>
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
        {/* M234: group chat leave/delete buttons shown when handlers are provided */}
        {props.detail.kind_label === "Group chat" && (props.onLeaveConversation || props.onDeleteConversation) ? (
          <div className="flex shrink-0 flex-col gap-1">
            {props.onLeaveConversation && (
              <button
                type="button"
                className="im-btn im-btn-muted shrink-0 text-xs"
                onClick={() => setConfirmAction("leave")}
              >
                退出群聊
              </button>
            )}
            {props.isGroupCreator && props.onDeleteConversation && (
              <button
                type="button"
                className="im-btn shrink-0 border border-rose-300 bg-rose-50 text-xs text-rose-700 hover:bg-rose-100"
                onClick={() => setConfirmAction("delete")}
              >
                解散群聊
              </button>
            )}
          </div>
        ) : null}
      </div>
      {/* M234: confirmation dialog for leave/delete group */}
      {confirmAction && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={confirmAction === "delete" ? "解散群聊确认" : "退出群聊确认"}
          className="absolute inset-0 z-20 flex items-center justify-center bg-black/30"
        >
          <div className="mx-4 w-full max-w-sm rounded-2xl border border-[var(--im-border)] bg-white px-6 py-5 shadow-xl">
            <h3 className="text-base font-bold text-slate-900">
              {confirmAction === "delete" ? "解散群聊" : "退出群聊"}
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              {confirmAction === "delete"
                ? "解散后所有成员将无法继续使用此群聊，且所有消息将被删除。此操作不可撤销，确认继续？"
                : "退出后你将离开此群聊，其他成员不受影响。确认退出？"}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="im-btn im-btn-muted"
                disabled={isConfirmPending}
                onClick={() => setConfirmAction(null)}
              >
                取消
              </button>
              <button
                type="button"
                className={confirmAction === "delete" ? "im-btn border border-rose-400 bg-rose-600 text-white hover:bg-rose-700" : "im-btn im-btn-primary"}
                disabled={isConfirmPending}
                onClick={async () => {
                  if (!props.detail) return;
                  setIsConfirmPending(true);
                  try {
                    if (confirmAction === "delete") {
                      await props.onDeleteConversation?.(props.detail.conversation_id);
                    } else {
                      await props.onLeaveConversation?.(props.detail.conversation_id);
                    }
                  } finally {
                    setIsConfirmPending(false);
                    setConfirmAction(null);
                  }
                }}
              >
                {isConfirmPending ? "处理中…" : confirmAction === "delete" ? "确认解散" : "确认退出"}
              </button>
            </div>
          </div>
        </div>
      )}
      <UsageStrip usage={props.usage} />
      <div
        ref={listRef}
        className="min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-y-contain px-4 py-4 [-webkit-overflow-scrolling:touch]"
      >
        <div data-testid="message-list-stack" className="flex min-h-full flex-col justify-end">
          {props.detail.messages.length === 0 ? (
            <EmptyThreadState />
          ) : (
            props.detail.messages.map((message) => <MessageBubble key={message.message_id} message={message} isGroupChat={isGroupChat} />)
          )}
        </div>
      </div>
      <form
        ref={formRef}
        className={`border-t border-[var(--im-border)] p-3 ${props.isMobile ? "pb-[max(0.75rem,env(safe-area-inset-bottom,0px))]" : ""}`}
        onSubmit={onSubmit}
      >
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
                      <span className={isActive ? "text-slate-200" : "text-slate-400"}>{formatMentionSecondaryCopy(candidate)}</span>
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
