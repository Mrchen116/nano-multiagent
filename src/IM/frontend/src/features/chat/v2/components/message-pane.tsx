import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { useTranslation } from "../../../../i18n";
import { AttachmentChip } from "../../attachments/attachment-chip";
import { AttachmentDropzone } from "../../attachments/attachment-dropzone";
import { uploadOneAttachment } from "../../attachments/use-attachment-upload";
import {
  classifyConversationKind,
  type Attachment,
  type Conversation,
  type MentionCandidate,
  type Message
} from "../chat-types";
import { Avatar } from "./avatar";
import { KindBadge } from "./kind-badge";
import { MentionPicker } from "./mention-picker";
import { NodeChip } from "./node-chip";
import { TokenChip } from "./token-chip";
import { ToolCallsPanel } from "./tool-calls-panel";

export interface MessagePaneProps {
  conversation: Conversation;
  messages: Message[];
  mentionCandidates: MentionCandidate[];
  nodeName?: string | null;
  nodeStatus?: "online" | "offline";
  onSend(text: string, attachments: Attachment[]): void;
  onBack?(): void;
  onOpenConfig?(): void;
  /** Test seam: overrides the real upload helper so vitest can stub uploads. */
  uploadAttachment?(file: File): Promise<Attachment>;
}

const MENTION_RE = /@(\w*)$/;

/**
 * Right-hand message pane — header (avatar / title / participants / node chip /
 * kind badge / ⚙) + messages list + composer (with @mention picker for groups).
 *
 * The component is fully controlled by the caller for `messages` and the
 * `onSend` callback fires when the user hits Send / Enter. The composer holds
 * draft text + pending attachments locally; on send it returns the trimmed
 * string + attachment list and clears both.
 * Mention picker activates only when `classifyConversationKind` resolves to
 * `group` or `agent-network` (matches spec Q5 — mention only meaningful when
 * there are 2+ agents to disambiguate).
 */
export function MessagePane({
  conversation,
  messages,
  mentionCandidates,
  nodeName,
  nodeStatus = "offline",
  onSend,
  onBack,
  onOpenConfig,
  uploadAttachment = uploadOneAttachment
}: MessagePaneProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Attachment[]>([]);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  const kind = classifyConversationKind(conversation);
  const isGroup = kind === "group" || kind === "agent-network";
  const mentionMatch = isGroup ? MENTION_RE.exec(draft) : null;
  const mentionQuery = mentionMatch?.[1] ?? null;

  const placeholder = isGroup
    ? t("chat.messagePane.placeholderGroup")
    : t("chat.messagePane.placeholderDirect", { title: conversation.title });

  function commit(text: string) {
    const trimmed = text.trim();
    if (!trimmed && pending.length === 0) return;
    onSend(trimmed, pending);
    setDraft("");
    setPending([]);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    commit(draft);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      commit(draft);
    }
  }

  function handleMentionSelect(c: MentionCandidate) {
    if (!mentionMatch) return;
    const before = draft.slice(0, draft.length - mentionMatch[0].length);
    setDraft(`${before}@${c.display_name} `);
    composerRef.current?.focus();
  }

  async function handleAdd(files: File[]) {
    for (const file of files) {
      try {
        // Sequential uploads keep the chip ordering deterministic and avoid
        // bursting `/im/v1/uploads` with N parallel large bodies.
        const att = await uploadAttachment(file);
        setPending((prev) => [...prev, att]);
      } catch {
        // Bubbling the error to a toast is the chat-workspace's job;
        // here we just drop the failing file so the rest still flow.
      }
    }
  }

  const latestUsage = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].token_usage) return messages[i].token_usage ?? null;
    }
    return null;
  }, [messages]);

  return (
    <section className="chat-pane" aria-label={conversation.title}>
      <header className="chat-pane-header">
        {onBack && (
          <button type="button" className="chat-pane-back" onClick={onBack} aria-label="Back">‹</button>
        )}
        <Avatar initials={conversation.title.slice(0, 2)} size={34} />
        <div className="chat-pane-header-body">
          <h2 className="chat-pane-title">{conversation.title}</h2>
          <div className="chat-pane-header-meta">
            <span className="chat-pane-participants">
              {conversation.participants.map((p) => p.display_name ?? p.id).join(" · ")}
            </span>
            <NodeChip nodeName={nodeName ?? null} status={nodeStatus} />
          </div>
        </div>
        <KindBadge kind={kind} />
        <TokenChip usage={latestUsage} />
        {onOpenConfig && (
          <button type="button" className="chat-pane-config" onClick={onOpenConfig} aria-label={t("chat.messagePane.config")}>
            ⚙ {t("chat.messagePane.config")}
          </button>
        )}
      </header>

      <div className="chat-pane-messages">
        {messages.length === 0 ? (
          <div className="chat-pane-empty">
            <p className="chat-pane-empty-title">{t("chat.messagePane.emptyTitle")}</p>
            <p className="chat-pane-empty-sub">{t("chat.messagePane.emptySubtitle")}</p>
          </div>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
      </div>

      <form className="chat-pane-composer" onSubmit={handleSubmit}>
        <AttachmentDropzone className="chat-pane-composer-dropzone" onAdd={handleAdd}>
          {pending.length > 0 && (
            <div className="chat-pane-composer-chips">
              {pending.map((att) => (
                <AttachmentChip
                  key={att.url}
                  attachment={att}
                  onRemove={() => setPending((prev) => prev.filter((p) => p.url !== att.url))}
                />
              ))}
            </div>
          )}
          <div className="chat-pane-composer-row">
            {isGroup && mentionQuery !== null && (
              <MentionPicker
                candidates={mentionCandidates}
                query={mentionQuery}
                onSelect={handleMentionSelect}
                onClose={() => setDraft((d) => d.replace(MENTION_RE, ""))}
              />
            )}
            <textarea
              ref={composerRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={2}
              className="chat-pane-composer-input"
            />
            <button
              type="submit"
              className="chat-pane-composer-send"
              disabled={!draft.trim() && pending.length === 0}
              aria-label="Send"
            >
              ↑
            </button>
          </div>
          <p className="chat-pane-composer-help">
            {isGroup ? t("chat.messagePane.helpDesktopGroup") : t("chat.messagePane.helpDesktop")}
          </p>
        </AttachmentDropzone>
      </form>
    </section>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.sender.type === "user";
  return (
    <div className={`chat-bubble chat-bubble--${isUser ? "user" : "agent"}`}>
      <div className="chat-bubble-meta">
        <span className="chat-bubble-sender">{message.sender.display_name ?? message.sender.id}</span>
      </div>
      {message.content && <div className="chat-bubble-content">{message.content}</div>}
      {message.attachments && message.attachments.length > 0 && (
        <div className="chat-bubble-attachments">
          {message.attachments.map((att) => (
            <AttachmentChip key={att.url} attachment={att} />
          ))}
        </div>
      )}
      {message.tool_calls && message.tool_calls.length > 0 && (
        <ToolCallsPanel toolCalls={message.tool_calls} />
      )}
    </div>
  );
}
