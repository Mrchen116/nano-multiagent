import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { authFetchJson } from "../../auth/auth-fetch";
import { createMessage } from "../chat-api";
import type { Message } from "../chat-types";

/** Topic column using the same chat pane, bubble and composer as the main timeline. */
export function ThreadColumn({
  conversationId,
  root,
  selfUserId,
  onClose,
  onSent,
}: {
  conversationId: string;
  root: Message;
  selfUserId?: string | null;
  onClose(): void;
  onSent(message: Message): void;
}) {
  const { t } = useTranslation();
  const [items, setItems] = useState<Message[]>([]);
  const [following, setFollowing] = useState(true);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
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
  async function send() {
    const text = draft.trim();
    if (!text) return;
    setError(null);
    try {
      const created = await createMessage({conversationId, content: text, threadRootMessageId: root.id});
      setItems(current => [...current, created]);
      setDraft("");
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
      <div className="chat-pane-messages">
        <div className="chat-pane-message-list">
          {[root, ...items].map(message => {
            const mine = message.sender.id === selfUserId || message.sender_user_id === selfUserId;
            return (
            <div key={message.id} className={mine ? "chat-bubble chat-bubble--user" : "chat-bubble chat-bubble--agent"}>
              <div className="chat-bubble-column">
                {!mine && <div className="chat-bubble-meta"><span className="chat-bubble-sender">{message.sender.display_name ?? message.sender.id}</span></div>}
                <div className="chat-bubble-card">
                  <div className={`chat-message-body${mine ? " chat-bubble-content" : ""}`}>{message.content}</div>
                </div>
              </div>
            </div>
            );
          })}
          {error && <p role="alert" className="tasks-notice">{error}</p>}
        </div>
      </div>
      <form className="chat-pane-composer" onSubmit={event => { event.preventDefault(); void send(); }}>
        <div className="chat-pane-composer-row">
          <textarea className="chat-pane-composer-input" rows={1} value={draft} placeholder={t("chat.messagePane.threadPlaceholder")}
            aria-label={t("chat.messagePane.threadTitle")}
            onChange={event => setDraft(event.target.value)}
            onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} />
          <button type="submit" className="chat-pane-composer-send" disabled={!draft.trim()} aria-label={t("chat.messagePane.send", "发送")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 19V5m-6 6 6-6 6 6" />
            </svg>
          </button>
        </div>
      </form>
    </aside>
  );
}
