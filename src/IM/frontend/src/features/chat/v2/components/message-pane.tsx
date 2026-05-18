import React, { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { useTranslation } from "../../../../i18n";
import { AttachmentChip } from "../../attachments/attachment-chip";
import { AttachmentDropzone } from "../../attachments/attachment-dropzone";
import { uploadOneAttachment } from "../../attachments/use-attachment-upload";
import {
  classifyConversationKind,
  type Actor,
  type Attachment,
  type Conversation,
  type MentionCandidate,
  type Message
} from "../chat-types";
import { Avatar } from "./avatar";
import { KindBadge } from "./kind-badge";
import { parseMentions } from "./mention-parser";
import { MentionPicker } from "./mention-picker";
import { NodeChip } from "./node-chip";
import { PermissionCard } from "./permission-card";
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
 * Build the overlay mirror nodes for the composer textarea.
 *
 * bugfix-358 (composer): textarea 现在装可见形式 `@DisplayName`(不是 wire XML),
 * 字符宽度与视觉一致, IME 输入框光标定位自然对齐。mirror 仅做 `@word` 高亮装饰。
 * wire 转换(可见 → `<mention/>` XML)在 commit() send 前根据 draftMentions 状态完成。
 */
function buildMirrorNodes(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const MENTION_HIGHLIGHT_RE = /@[\w一-龥][^\s@]*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = MENTION_HIGHLIGHT_RE.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    nodes.push(<mark key={m.index} className="chat-composer-mention-highlight">{m[0]}</mark>);
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  // Mirror needs a trailing zero-width space so the last line has correct height.
  nodes.push("​");
  return nodes;
}

/**
 * One picker-originated mention range in the draft.
 *
 * bugfix-358 (composer): textarea 装可见 `@DisplayName` 文本, 此 state 跟踪每次 picker
 * 选中产生的 mention 元数据。commit 时按 label 在 draft 里精确替换为 wire XML。
 * 用户手敲删除 label 时, indexOf 找不到自然跳过——零清理逻辑。
 */
type DraftMention = {
  label: string;       // e.g. "@架构" — visible text inserted into textarea
  type: "agent" | "user";
  target_id: string;
};

/**
 * Reconstruct wire content from visible draft + picker-tracked mention metadata.
 *
 * 遍历每个 tracked mention,在 draft 中按 label 找第一处匹配替换为对应的 inline XML 标签。
 * 同一 label 多次出现(用户连续选同一 agent): 每次循环替换第一处, 下一轮自然替换下一处。
 * 用户已删除某 label: indexOf 返回 -1, 该项跳过——不会污染最终 wire 文本。
 */
function reconstructWireContent(draftText: string, mentions: DraftMention[]): string {
  let wire = draftText;
  for (const m of mentions) {
    const pos = wire.indexOf(m.label);
    if (pos === -1) continue;
    const xml = `<mention type="${m.type}" target_id="${m.target_id}"/>`;
    wire = wire.slice(0, pos) + xml + wire.slice(pos + m.label.length);
  }
  return wire;
}

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
  const [draftMentions, setDraftMentions] = useState<DraftMention[]>([]);
  const [pending, setPending] = useState<Attachment[]>([]);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const mirrorRef = useRef<HTMLDivElement | null>(null);
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
    // bugfix-358 (composer): textarea 装可见 `@DisplayName`, wire XML 在此处重建。
    const wireContent = reconstructWireContent(trimmed, draftMentions);
    onSend(wireContent, pending);
    setDraft("");
    setDraftMentions([]);
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
    if (!isMobile && e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      if (mentionQuery !== null) return;
      e.preventDefault();
      commit(draft);
    }
  }

  function handleMentionSelect(c: MentionCandidate) {
    if (!mentionMatch) return;
    // bugfix-358 (composer): 插入可见形式 `@DisplayName` 而非 XML, 同时旁路记录
    // mention 元数据 (label + target_id + type), commit 时统一替换为 wire XML。
    // 这样 textarea 字符宽度 = 视觉宽度, IME / 光标 / 撤销栈全部自然对齐。
    const label = `@${c.display_name}`;
    const before = draft.slice(0, draft.length - mentionMatch[0].length);
    setDraft(`${before}${label} `);
    setDraftMentions((prev) => [...prev, { label, type: "agent", target_id: c.agent_id }]);
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
          messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              isMobile={isMobile}
              participants={conversation.participants}
            />
          ))
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
            <div className="chat-composer-highlight-wrapper">
              <div
                ref={mirrorRef}
                className="chat-composer-highlight-mirror"
                aria-hidden="true"
              >
                {buildMirrorNodes(draft)}
              </div>
              <textarea
                ref={composerRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                onScroll={() => {
                  if (mirrorRef.current && composerRef.current) {
                    mirrorRef.current.scrollTop = composerRef.current.scrollTop;
                  }
                }}
                placeholder={placeholder}
                rows={isMobile ? 1 : 2}
                className="chat-pane-composer-input chat-composer-highlight-input"
              />
            </div>
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

function MessageBubble({
  message,
  isMobile,
  participants,
}: {
  message: Message;
  isMobile?: boolean;
  participants?: Actor[];
}) {
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
              ? <div className="chat-bubble-content">{renderInlineContent(message.content, participants)}</div>
              : <MarkdownContent content={message.content} participants={participants} />
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
        {isAgent && message.permission_request && (
          <PermissionCard
            request={message.permission_request}
            conversationId={message.conversation_id}
            messageId={message.id}
            onResolved={() => {/* WS event will update the message status */}}
          />
        )}
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

function MarkdownContent({
  content,
  participants,
}: {
  content: string;
  participants?: Actor[];
}) {
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
          return (
            <ul key={idx}>
              {items.map((item, itemIdx) => (
                <li key={itemIdx}>{renderInlineContent(item, participants)}</li>
              ))}
            </ul>
          );
        }
        if (/^\s*\d+\.\s+/m.test(block)) {
          const items = block.split("\n").filter(Boolean).map((line) => line.replace(/^\s*\d+\.\s+/, ""));
          return (
            <ol key={idx}>
              {items.map((item, itemIdx) => (
                <li key={itemIdx}>{renderInlineContent(item, participants)}</li>
              ))}
            </ol>
          );
        }
        return <p key={idx}>{renderInlineContent(block, participants)}</p>;
      })}
    </div>
  );
}

/**
 * Render a text segment that may contain inline mention tags and markdown emphasis.
 * bugfix-358: <mention type="agent"|"user" target_id="X"/> tags are rendered as
 * chip elements showing the current display_name from the participants dictionary.
 */
function renderInlineContent(
  text: string,
  participants?: Actor[],
): React.ReactNode {
  // Build a lookup map from wire ID to display_name for mention chip resolution.
  const participantMap = new Map<string, string>();
  if (participants) {
    for (const p of participants) {
      const displayName = p.display_name ?? p.id;
      participantMap.set(p.id, displayName);
    }
  }

  const segments = parseMentions(text);
  // Fast path: no mention segments — fall back to markdown-only rendering.
  if (segments.every((s) => s.kind === "text")) {
    return renderInlineMarkdown(text);
  }

  return segments.map((seg, idx) => {
    if (seg.kind === "mention") {
      const displayName = participantMap.get(seg.target_id);
      if (displayName) {
        return (
          <span key={idx} className="chat-mention-chip" data-target-id={seg.target_id}>
            @{displayName}
          </span>
        );
      }
      // Unknown target_id: silent degradation — no raw tag shown
      return (
        <span key={idx} className="chat-mention-chip chat-mention-chip--unknown">
          @unknown
        </span>
      );
    }
    // Text segment: apply inline markdown within it
    return <React.Fragment key={idx}>{renderInlineMarkdown(seg.text)}</React.Fragment>;
  });
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
