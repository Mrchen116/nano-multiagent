import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ChatMessage, ChatStarter, ConversationDetail } from "../types";

const RELAY_UNAVAILABLE_MESSAGE = "No relay node is available. Connect an online node and retry.";

function toErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    if (error.message.includes("target_node_id is not connected")) {
      return RELAY_UNAVAILABLE_MESSAGE;
    }
    return error.message;
  }
  return "Message send failed. Retry when the relay node is available.";
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const mine = message.is_mine ?? message.sender_type === "user";
  return (
    <div className={`mb-3 flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={[
          "max-w-[80%] rounded-2xl px-3 py-2 text-sm",
          mine ? "bg-[#0f766e] text-white" : "bg-[#e5ebf2] text-slate-900"
        ].join(" ")}
      >
        <p className="text-[11px] opacity-75">{message.sender_name ?? message.sender_type}</p>
        <p className="mt-1 whitespace-pre-wrap">{message.content}</p>
        {message.delivery_status && (
          <p className="mt-1 text-[10px] uppercase tracking-wide opacity-70">{message.delivery_status}</p>
        )}
      </div>
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
            <dt className="font-semibold text-slate-700">Current route</dt>
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
  canSend: boolean;
  helperText: string | null;
  sendPlaceholder?: string;
  onSend: (content: string) => Promise<unknown>;
}) {
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

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

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !props.canSend) {
      return;
    }
    setSendError(null);
    try {
      await props.onSend(text);
      setDraft("");
    } catch (error) {
      setSendError(toErrorMessage(error));
      // Preserve the draft so the user can retry after reading the failure feedback.
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
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-4">
        <div data-testid="message-list-stack" className="flex min-h-full flex-col justify-end">
          {props.detail.messages.map((message) => (
            <MessageBubble key={message.message_id} message={message} />
          ))}
        </div>
      </div>
      <form className="border-t border-[var(--im-border)] p-3" onSubmit={onSubmit}>
        {props.helperText && <p className="mb-2 text-xs text-amber-700">{props.helperText}</p>}
        {sendError && (
          <p role="alert" className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {sendError}
          </p>
        )}
        <div className="flex items-center gap-2">
          <button type="button" className="im-btn im-btn-muted" aria-label="Attachment picker">
            +
          </button>
          <input
            className="im-input"
            placeholder={props.sendPlaceholder ?? (props.canSend ? "Type message" : "Bind this Gateway to enable chat")}
            value={draft}
            disabled={!props.canSend}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit" className="im-btn im-btn-primary" disabled={props.isSending || !props.canSend}>
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
