import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { ChatMessage, ConversationDetail } from "../types";

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

export function MessagePane(props: {
  detail: ConversationDetail | null;
  isMobile: boolean;
  isSending: boolean;
  onSend: (content: string) => void;
}) {
  const [draft, setDraft] = useState("");

  if (!props.detail) {
    return (
      <section className="im-card hidden h-full min-h-[420px] items-center justify-center text-slate-500 lg:flex">
        Select a conversation
      </section>
    );
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) {
      return;
    }
    props.onSend(text);
    setDraft("");
  };

  return (
    <section className="im-card flex h-full min-h-[420px] flex-col overflow-hidden">
      <div className="flex items-center gap-3 border-b border-[var(--im-border)] px-4 py-3">
        {props.isMobile && (
          <Link to="/chat" className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">
            Back
          </Link>
        )}
        <h2 className="im-title text-lg font-bold">{props.detail.title}</h2>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {props.detail.messages.map((message) => (
          <MessageBubble key={message.message_id} message={message} />
        ))}
      </div>
      <form className="border-t border-[var(--im-border)] p-3" onSubmit={onSubmit}>
        <div className="flex items-center gap-2">
          <button type="button" className="im-btn im-btn-muted" aria-label="Attachment picker">
            +
          </button>
          <input
            className="im-input"
            placeholder="Type message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit" className="im-btn im-btn-primary" disabled={props.isSending}>
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
