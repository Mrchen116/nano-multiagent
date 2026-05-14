import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

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
  /** Agent color for header avatar (direct-agent conversations). */
  agentColor?: string | null;
  /** Agent initials for header avatar (direct-agent conversations). */
  agentInitials?: string | null;
  /** Compact mobile chat header (< 768px). Desktop layout (R7-5 Node chip + ⚙ + KindBadge + participants) is preserved when false/undefined. */
  isMobile?: boolean;
  onSend(text: string, attachments: Attachment[]): void;
  onBack?(): void;
  onOpenConfig?(): void;
  /** Send mutation error message, shown as an in-app toast. */
  sendError?: string | null;
  /** Whether a message is currently being sent. */
  isSending?: boolean;
  /** Test seam: overrides the real upload helper so vitest can stub uploads. */
  uploadAttachment?(file: File): Promise<Attachment>;
}

const MENTION_RE = /@([^@\s]*)$/;

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
  agentColor,
  agentInitials,
  isMobile = false,
  onSend,
  onBack,
  onOpenConfig,
  sendError,
  isSending,
  uploadAttachment = uploadOneAttachment
}: MessagePaneProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Attachment[]>([]);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);

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
    if (mentionQuery !== null && e.key === "Escape") {
      e.preventDefault();
      setDraft((d) => d.replace(MENTION_RE, ""));
      return;
    }
    if (!isMobile && e.key === "Enter" && !e.shiftKey) {
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

  // Auto-scroll: when messages change, scroll the internal message container to
  // the bottom (not the whole page).  Uses scrollTop instead of scrollIntoView so
  // only the pane scrolls.
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <section className="chat-pane" aria-label={conversation.title}>
      <header className="chat-pane-header">
        {onBack && (
          <button type="button" className="chat-pane-back" onClick={onBack} aria-label="Back">‹</button>
        )}
        <Avatar
          initials={agentInitials ?? conversation.title.slice(0, 2)}
          color={agentColor ?? undefined}
          size={34}
          status={kind === "direct-agent" ? nodeStatus : null}
        />
        <div className="chat-pane-header-body">
          <h2 className="chat-pane-title">{conversation.title}</h2>
          <div className="chat-pane-header-meta">
            {!isMobile && (
              <span className="chat-pane-participants">
                {conversation.participants.map((p) => p.display_name ?? p.id).join(" · ")}
              </span>
            )}
            {kind === "direct-agent" && <NodeChip nodeName={nodeName ?? null} status={nodeStatus} />}
          </div>
        </div>
        {!isMobile && <KindBadge kind={kind} />}
        {onOpenConfig && (
          isMobile ? (
            <button
              type="button"
              className="chat-pane-config chat-pane-config-icon"
              onClick={onOpenConfig}
              aria-label={t("chat.messagePane.config")}
            >
              ⚙
            </button>
          ) : (
            <button type="button" className="chat-pane-config" onClick={onOpenConfig} aria-label={t("chat.messagePane.config")}>
              ⚙ {t("chat.messagePane.config")}
            </button>
          )
        )}
      </header>

      <div ref={messagesContainerRef} className="chat-pane-messages">
        {messages.length === 0 ? (
          <div className="chat-pane-empty">
            <div className="chat-pane-empty-icon" aria-hidden="true">✨</div>
            <p className="chat-pane-empty-title">{t("chat.messagePane.emptyTitle")}</p>
            <p className="chat-pane-empty-sub">{t("chat.messagePane.emptySubtitle")}</p>
          </div>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} isMobile={isMobile} />)
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
              rows={isMobile ? 1 : 2}
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
          {!isMobile && (
            <p className="chat-pane-composer-help">
              {isGroup ? t("chat.messagePane.helpDesktopGroup") : t("chat.messagePane.helpDesktop")}
            </p>
          )}
        </AttachmentDropzone>
      </form>
    </section>
  );
}

function MessageBubble({ message, isMobile }: { message: Message; isMobile?: boolean }) {
  const { t } = useTranslation();
  const isSystem = message.sender.type === "system";
  const isUser = message.sender.type === "user";
  const isAgent = message.sender.type === "agent";
  const initials = (message.sender.display_name ?? message.sender.id).slice(0, 2).toUpperCase();
  const ts = formatHM(message.created_at);
  const senderColor = message.sender.type === "agent" && message.sender.display_name
    ? colorForSeed(message.sender.display_name)
    : "oklch(0.52 0.14 270)";
  const rowFlex = isUser ? "flex-row-reverse" : "flex-row";
  const statusAlign = isUser ? "justify-end" : "justify-start";
  const deliveryStatus = message.delivery_status;

  if (isSystem) {
    return (
      <div className="chat-bubble-system">
        {message.content}
      </div>
    );
  }

  return (
    <div className={`chat-bubble chat-bubble--${isUser ? "user" : "agent"} flex ${rowFlex} gap-2 items-end`}>
      {!isUser && (
        <span
          data-testid={`message-avatar-${message.id}`}
          className="inline-flex shrink-0 items-center justify-center w-[30px] h-[30px] rounded-full text-white text-[12px] font-semibold"
          style={{ backgroundColor: senderColor }}
          aria-hidden
        >
          {initials}
        </span>
      )}
      <div className="flex flex-col min-w-0">
        {!isUser && (
          <div className="chat-bubble-meta">
            <span className="chat-bubble-sender" style={{ color: senderColor }}>
              {message.sender.display_name ?? message.sender.id}
            </span>
          </div>
        )}
        <div data-testid={`message-bubble-${message.id}`} className="chat-bubble-card">
          {message.content && (
            isUser
              ? <div className="chat-bubble-content">{message.content}</div>
              : <MarkdownContent content={message.content} />
          )}
          {message.attachments && message.attachments.length > 0 && (
            <div className="chat-bubble-attachments">
              {message.attachments.map((att) => (
                <AttachmentChip key={att.url} attachment={att} />
              ))}
            </div>
          )}
          {isAgent && message.tool_calls && message.tool_calls.length > 0 && (
            <ToolCallsPanel toolCalls={message.tool_calls} />
          )}
          {isAgent && deliveryStatus === "completed" && message.token_usage && (
            <TokenChip usage={message.token_usage} dataTestId={`message-token-chip-${message.id}`} />
          )}
        </div>
        <div className={`chat-bubble-status mt-[2px] flex items-center gap-2 text-[11px] text-[oklch(0.55 0.01 240)] ${statusAlign}`}>
          <span data-testid={`message-timestamp-${message.id}`}>{ts}</span>
          {deliveryStatus === "running" && (
            <span className="flex items-center gap-1 text-[oklch(0.65 0.15 60)]">
              <span className="inline-block w-[6px] h-[6px] rounded-full bg-[oklch(0.70 0.18 60)] animate-pulse" />
              {t("chat.messagePane.running")}
            </span>
          )}
          {deliveryStatus === "failed" && (
            <span className="text-[oklch(0.55 0.15 25)]">{t("chat.messagePane.failed")}</span>
          )}
        </div>
      </div>
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/);
  return (
    <div className="im-md">
      {blocks.map((block, idx) => {
        if (block.startsWith("```") && block.endsWith("```")) {
          const code = block.replace(/^```[^\n]*\n?/, "").replace(/\n?```$/, "");
          return <pre key={idx}><code>{code}</code></pre>;
        }
        if (/^\s*[-*]\s+/m.test(block)) {
          const items = block.split("\n").filter(Boolean).map((line) => line.replace(/^\s*[-*]\s+/, ""));
          return <ul key={idx}>{items.map((item, itemIdx) => <li key={itemIdx}>{renderInlineMarkdown(item)}</li>)}</ul>;
        }
        if (/^\s*\d+\.\s+/m.test(block)) {
          const items = block.split("\n").filter(Boolean).map((line) => line.replace(/^\s*\d+\.\s+/, ""));
          return <ol key={idx}>{items.map((item, itemIdx) => <li key={itemIdx}>{renderInlineMarkdown(item)}</li>)}</ol>;
        }
        return <p key={idx}>{renderInlineMarkdown(block)}</p>;
      })}
    </div>
  );
}

function renderInlineMarkdown(text: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={idx}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={idx}>{part.slice(2, -2)}</strong>;
    }
    return <span key={idx}>{part}</span>;
  });
}

function colorForSeed(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash << 5) - hash + seed.charCodeAt(i);
  const hue = Math.abs(hash) % 360;
  return `oklch(0.55 0.15 ${hue})`;
}

function formatHM(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}
