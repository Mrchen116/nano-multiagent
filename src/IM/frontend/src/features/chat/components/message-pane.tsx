import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ChatAttachment, ChatMessage, ChatStarter, ChatUsageView, ConversationDetail, UsageAgentView, UsageTotals } from "../types";
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

function SendErrorBanner({ message }: { message: string }) {
  return (
    <div role="alert" className="mb-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      <p className="font-semibold text-rose-900">{SEND_AVAILABILITY_MESSAGES.failureTitle}</p>
      <p className="mt-1">{message}</p>
      <p className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-rose-700">Next: Retry delivery</p>
    </div>
  );
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
        {message.delivery_status && (
          <p className="mt-1 text-[10px] uppercase tracking-wide opacity-70">{message.delivery_status}</p>
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

function PendingAttachments(props: {
  attachments: ChatAttachment[];
  isUploading: boolean;
}) {
  if (props.attachments.length === 0 && !props.isUploading) {
    return null;
  }
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      {props.attachments.map((attachment) => (
        <span
          key={`${attachment.url}:${attachment.file_name ?? "pending"}`}
          className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
        >
          {attachment.file_name ?? attachment.url}
        </span>
      ))}
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
        <p className="mt-3 text-sm text-slate-600">{starter.description}</p>
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
        <p className="mt-1">Use the conversation list to open other direct agent chats, agent-to-agent threads, or group chats.</p>
      </div>
      <div>
        <Link to={starter.actionHref} className="im-btn im-btn-primary inline-flex" aria-label={starter.actionLabel}>
          {starter.actionLabel}
        </Link>
      </div>
    </section>
  );
}

export function MessagePane(props: {
  detail: ConversationDetail | null;
  starter?: ChatStarter | null;
  isMobile: boolean;
  isSending: boolean;
  sendAvailability: SendAvailability;
  usage: ChatUsageView;
  onSend: (payload: { content: string; attachments: ChatAttachment[] }) => Promise<unknown>;
  onUploadAttachment: (file: File) => Promise<ChatAttachment>;
}) {
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<ChatAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  if (!props.detail) {
    if (props.starter) {
      return <DefaultAgentStarterCard starter={props.starter} />;
    }
    return (
      <section className="im-card hidden h-full min-h-[420px] items-center justify-center text-slate-500 lg:flex">
        Select a conversation
      </section>
    );
  }

  const onPickAttachment = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setSendError(null);
    setIsUploading(true);
    try {
      const uploaded = await props.onUploadAttachment(file);
      setPendingAttachments((current) => [...current, uploaded]);
    } catch (error) {
      setSendError(toErrorMessage(error));
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if ((!text && pendingAttachments.length === 0) || !props.sendAvailability.canSend || isUploading) {
      return;
    }
    setSendError(null);
    try {
      await props.onSend({ content: text, attachments: pendingAttachments });
      setDraft("");
      setPendingAttachments([]);
    } catch (error) {
      setSendError(toErrorMessage(error));
      // Preserve the draft and uploaded attachments so the user can retry after reading the failure feedback.
    }
  };

  return (
    <section className="im-card flex h-full min-h-[420px] flex-col overflow-hidden">
      <div className="flex items-center gap-3 border-b border-[var(--im-border)] px-4 py-3">
        {props.isMobile && (
          <Link to="/chat" className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">
            Back
          </Link>
        )}
        <div className="min-w-0">
          {props.detail.kind_label && (
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{props.detail.kind_label}</p>
          )}
          <h2 className="im-title text-lg font-bold">{props.detail.title}</h2>
          {props.detail.target_label && <p className="mt-1 text-xs text-slate-600">Target: {props.detail.target_label}</p>}
          {props.detail.discoverability_hint && (
            <p className="mt-1 text-xs text-slate-500">{props.detail.discoverability_hint}</p>
          )}
          {props.detail.ownership_label && (
            <p className="mt-1 text-xs text-slate-500">{props.detail.ownership_label}</p>
          )}
        </div>
      </div>
      <UsageStrip usage={props.usage} />
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-4">
        <div data-testid="message-list-stack" className="flex min-h-full flex-col justify-end">
          {props.detail.messages.map((message) => (
            <MessageBubble key={message.message_id} message={message} />
          ))}
        </div>
      </div>
      <form className="border-t border-[var(--im-border)] p-3" onSubmit={onSubmit}>
        <FailureStateBanner sendAvailability={props.sendAvailability} />
        {sendError && <SendErrorBanner message={sendError} />}
        <PendingAttachments attachments={pendingAttachments} isUploading={isUploading} />
        <div className="flex items-center gap-2">
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
          <input
            className="im-input"
            placeholder={props.sendAvailability.placeholder}
            value={draft}
            disabled={!props.sendAvailability.canSend}
            onChange={(event) => setDraft(event.target.value)}
          />
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
