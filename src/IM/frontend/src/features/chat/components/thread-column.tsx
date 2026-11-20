import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Reply } from "lucide-react";
import { useTranslation } from "react-i18next";
import { authFetchJson } from "../../auth/auth-fetch";
import { createMessage } from "../chat-api";
import type { Message, ReplyReference } from "../chat-types";

/** Topic column using the same chat pane, bubble and composer as the main timeline. */
export function ThreadColumn({
  conversationId,
  root,
  selfUserId,
  incoming,
  onClose,
  onSent,
}: {
  conversationId: string;
  root: Message;
  selfUserId?: string | null;
  incoming?: Message[];
  onClose(): void;
  onSent(message: Message): void;
}) {
  const { t } = useTranslation();
  const [items, setItems] = useState<Message[]>([]);
  const [following, setFollowing] = useState(true);
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<ReplyReference | undefined>();
  const [error, setError] = useState<string | null>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  useEffect(() => {
    let live = true;
    void authFetchJson<{following: boolean; items: {message: Message}[]}>(
      `/im/v1/conversations/${encodeURIComponent(conversationId)}/threads/${encodeURIComponent(root.id)}`,
      undefined,
      "readThread",
    ).then(page => {
      if (!live) return;
      setFollowing(page.following);
      setItems(page.items.map(item => item.message));
    }).catch(() => { if (live) setError(t("chat.messagePane.sendError")); });
    return () => { live = false; };
  }, [conversationId, root.id, t]);
  useEffect(() => {
    const extra = (incoming ?? []).filter(message => message.thread_root_message_id === root.id);
    if (!extra.length) return;
    setItems(current => {
      const known = new Set(current.map(message => message.id));
      const added = extra.filter(message => !known.has(message.id));
      return added.length ? [...current, ...added] : current;
    });
  }, [incoming, root.id]);
  useLayoutEffect(() => {
    const node = scrollerRef.current;
    if (node && stickRef.current) node.scrollTop = node.scrollHeight;
  }, [items]);
  function trackScroll() {
    const node = scrollerRef.current;
    if (!node) return;
    stickRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 48;
  }
  async function send() {
    const text = draft.trim();
    if (!text) return;
    setError(null);
    try {
      const created = await createMessage({
        conversationId,
        content: text,
        threadRootMessageId: root.id,
        ...(replyTo ? {replyToMessageId: replyTo.message_id} : {}),
      });
      stickRef.current = true;
      setItems(current => current.some(message => message.id === created.id) ? current : [...current, created]);
      setDraft("");
      setReplyTo(undefined);
      onSent(created);
    } catch {
      setError(t("chat.messagePane.sendError"));
    }
  }
  async function toggleFollow() {
    const next = !following;
    await authFetchJson(`/im/v1/conversations/${encodeURIComponent(conversationId)}/threads/${encodeURIComponent(root.id)}/follow`,
      {method: "POST", body: JSON.stringify({following: next})}, "followThread");
    setFollowing(next);
  }
  function quote(message: Message) {
    setReplyTo({message_id: message.id, sender: message.sender, content: message.content, attachments: message.attachments ?? []});
  }
  return (
    <aside className="chat-thread-column" aria-label={t("chat.messagePane.threadTitle")}>
      <header className="chat-pane-header">
        <button type="button" className="chat-pane-back" onClick={onClose} aria-label={t("common.back", "返回")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m12 5-7 7 7 7M5 12h14" /></svg>
        </button>
        <div className="chat-pane-header-body">
          <h2 className="chat-pane-title">{t("chat.messagePane.threadTitle")}</h2>
          <div className="chat-pane-header-meta">{t("chat.messagePane.threadCount", {n: items.length})}</div>
        </div>
        <button type="button" className="chat-pane-config" aria-pressed={following} onClick={() => void toggleFollow()}>
          {following ? t("chat.messagePane.following") : t("chat.messagePane.follow")}
        </button>
      </header>
      <div ref={scrollerRef} className="chat-pane-messages" onScroll={trackScroll}>
        <div className="chat-pane-message-list">
          <ThreadBubble message={root} selfUserId={selfUserId} onReply={() => quote(root)} />
          <div className="chat-thread-replies" role="separator">{t("chat.messagePane.threadCount", {n: items.length})}</div>
          {items.map(message => (
            <ThreadBubble key={message.id} message={message} selfUserId={selfUserId} onReply={() => quote(message)} />
          ))}
          {error && <p role="alert" className="tasks-notice">{error}</p>}
        </div>
      </div>
      <form className="chat-pane-composer" onSubmit={event => { event.preventDefault(); void send(); }}>
        <div className="chat-pane-composer-dropzone">
        {replyTo && <div className="chat-composer-reply" data-testid="thread-composer-reply">
          <div>
            <strong>{t("chat.messagePane.reply")} {replyTo.sender.display_name ?? replyTo.sender.id}</strong>
            <span>{replyTo.content}</span>
          </div>
          <button type="button" aria-label={t("common.close", "取消")} onClick={() => setReplyTo(undefined)}>×</button>
        </div>}
          <div className="chat-composer-input">
            <div className="chat-pane-composer-row">
              <div className="chat-composer-highlight-wrapper">
                <textarea className="chat-pane-composer-input" rows={2} value={draft} placeholder={t("chat.messagePane.threadPlaceholder")}
                  aria-label={t("chat.messagePane.threadTitle")}
                  onChange={event => setDraft(event.target.value)}
                  onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} />
              </div>
              <button type="submit" className="chat-pane-composer-send" disabled={!draft.trim()} aria-label={t("chat.messagePane.send", "发送")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 19V5m-6 6 6-6 6 6" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </form>
    </aside>
  );
}

function ThreadBubble({message, selfUserId, onReply}: {message: Message; selfUserId?: string | null; onReply(): void}) {
  const {t} = useTranslation();
  const mine = message.sender.id === selfUserId || message.sender_user_id === selfUserId;
  return (
    <div id={`thread-message-${message.id}`} className={mine ? "chat-bubble chat-bubble--user" : "chat-bubble chat-bubble--agent"}
      onContextMenu={event => { event.preventDefault(); onReply(); }}>
      <div className="chat-bubble-column">
        {!mine && <div className="chat-bubble-meta"><span className="chat-bubble-sender">{message.sender.display_name ?? message.sender.id}</span></div>}
        <div className="chat-bubble-card">
          {message.reply_to && <button type="button" className="chat-message-quote" onClick={() => document.getElementById(`thread-message-${message.reply_to!.message_id}`)?.scrollIntoView({block: "center", behavior: "smooth"})}>
            <strong>{message.reply_to.sender.display_name ?? message.reply_to.sender.id}</strong>
            <span>{message.reply_to.content}</span>
          </button>}
          <div className={`chat-message-body${mine ? " chat-bubble-content" : ""}`}>{message.content}</div>
          <div className="chat-message-toolbar" role="toolbar">
            <div className="chat-message-actions chat-message-actions--horizontal">
              <button type="button" className="chat-message-action" aria-label={t("chat.messagePane.reply")} title={t("chat.messagePane.reply")} onClick={onReply}>
                <Reply size={16} strokeWidth={1.8} aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
