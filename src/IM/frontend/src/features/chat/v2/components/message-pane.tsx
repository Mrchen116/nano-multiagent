import React, { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

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
import { Avatar, colorForAgentSeed } from "./avatar";
import { KindBadge } from "./kind-badge";
import { parseMentions } from "./mention-parser";
import { MentionPicker } from "./mention-picker";
import { NodeChip } from "./node-chip";
import { PermissionCard } from "./permission-card";
import { SlashPicker } from "./slash-picker";
import {
  matchSlashTrigger,
  type SlashCandidate,
  type SlashSkillCandidate,
} from "./slash-candidates";
import { TokenChip } from "./token-chip";
import { formatDuration, ToolCallsPanel } from "./tool-calls-panel";
import { remarkMention } from "./remark-mention";

export interface MessagePaneProps {
  conversation: Conversation;
  messages: Message[];
  mentionCandidates: MentionCandidate[];
  /** feat-430: enabled skills for this conversation's agent(s), for the slash picker. */
  slashSkills?: SlashSkillCandidate[];
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
  slashSkills = [],
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
  // feat-430: Esc / click-outside hides the slash picker but keeps the `/` text;
  // any further typing re-opens it (reset on draft change).
  const [slashDismissed, setSlashDismissed] = useState(false);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const mirrorRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const slashWrapRef = useRef<HTMLDivElement | null>(null);

  const kind = classifyConversationKind(conversation);
  const isGroup = kind === "group" || kind === "agent-network";
  const mentionMatch = isGroup ? MENTION_RE.exec(draft) : null;
  const mentionQuery = mentionMatch?.[1] ?? null;

  // feat-430: slash picker triggers only at the START of the composer (决策 6) and
  // never simultaneously with the @ mention picker. Available in single and group chats.
  const slashMatch =
    mentionQuery === null && !slashDismissed ? matchSlashTrigger(draft) : null;

  function changeDraft(next: string) {
    setSlashDismissed(false);
    setDraft(next);
  }

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
    // feat-430: while the slash picker is open it owns Arrow/Enter/Tab/Esc (its own
    // window keydown handler). Here we only stop Enter from sending the raw `/...` text.
    if (slashMatch !== null) {
      if (!isMobile && e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
      }
      return;
    }
    if (!isMobile && e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      if (mentionQuery !== null) return;
      e.preventDefault();
      commit(draft);
    }
  }

  function handleSlashSelect(c: SlashCandidate) {
    // 命令补 `/name `、skill 补 `/skill:name `（尾随空格），光标置末尾、保持焦点（决策 6）。
    const insert = c.kind === "command" ? `/${c.name} ` : `/skill:${c.name} `;
    changeDraft(insert);
    const el = composerRef.current;
    if (el) {
      el.focus();
      // Defer cursor placement until the controlled value re-renders.
      requestAnimationFrame(() => {
        el.setSelectionRange(insert.length, insert.length);
      });
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

  // feat-430: clicking outside the slash picker and composer dismisses it while
  // preserving the typed `/` text (spec: Esc / 点面板外关闭).
  const slashOpen = slashMatch !== null;
  useEffect(() => {
    if (!slashOpen) return;
    function onDocMouseDown(e: MouseEvent) {
      const target = e.target as Node;
      if (slashWrapRef.current?.contains(target)) return;
      if (composerRef.current?.contains(target)) return;
      setSlashDismissed(true);
    }
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [slashOpen]);

  return (
    <section className="chat-pane" aria-label={conversation.title}>
      <header className="chat-pane-header">
        {onBack && (
          <button type="button" className="chat-pane-back" onClick={onBack} aria-label="Back">‹</button>
        )}
        <Avatar
          // 只有 direct-agent 用该 agent 的头像；群 / agent-network 用群名 initials +
          // 群色(紫)，与左侧会话列表的群头像一致，不再误用第一个 agent 的头像。
          initials={kind === "direct-agent" ? (agentInitials ?? conversation.title.slice(0, 2)) : conversation.title.slice(0, 2)}
          color={kind === "direct-agent" ? (agentColor ?? "oklch(0.52 0.14 270)") : "oklch(0.52 0.14 270)"}
          size={34}
          status={kind === "direct-agent" ? nodeStatus : null}
        />
        <div className="chat-pane-header-body">
          <h2 className="chat-pane-title">{conversation.title}</h2>
          <div className="chat-pane-header-meta">
            {!isMobile && (
              <span className="chat-pane-participants">
                {conversation.participants.map((p, i) => (
                  <span
                    key={p.id}
                    className={p.is_stale ? "opacity-40" : undefined}
                    title={p.is_stale ? "Offline — agent no longer advertised by its Gateway" : undefined}
                  >
                    {p.display_name ?? p.id}
                    {i < conversation.participants.length - 1 ? " · " : ""}
                  </span>
                ))}
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
            {slashMatch !== null && (
              <div ref={slashWrapRef}>
                <SlashPicker
                  skills={slashSkills}
                  query={slashMatch.prefix}
                  skillMode={slashMatch.skillMode}
                  isGroup={isGroup}
                  onSelect={handleSlashSelect}
                  onClose={() => setSlashDismissed(true)}
                />
              </div>
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
                onChange={(e) => changeDraft(e.target.value)}
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
    ? colorForAgentSeed(message.sender.display_name)
    : "oklch(0.52 0.14 270)";
  const rowFlex = isUser ? "flex-row-reverse" : "flex-row";
  const statusAlign = isUser ? "justify-end" : "justify-start";
  const deliveryStatus = message.delivery_status;

  // feat-414 决策 2: running 时前端本地 tick（锚 message.created_at），
  // completed 后用后端权威 elapsed_ms 定格，不再 tick。
  const [tickMs, setTickMs] = useState<number>(() => {
    if (deliveryStatus !== "running") return 0;
    return Math.max(0, Date.now() - new Date(message.created_at).getTime());
  });
  useEffect(() => {
    if (deliveryStatus !== "running") return;
    const origin = new Date(message.created_at).getTime();
    const id = setInterval(() => setTickMs(Date.now() - origin), 1000);
    return () => clearInterval(id);
  }, [deliveryStatus, message.created_at]);

  // completed 用权威后端值；running 用前端本地 tick；其余（user/failed）不展示。
  const elapsedDisplay: string | null = isAgent
    ? deliveryStatus === "completed" && message.elapsed_ms != null
      ? formatDuration(message.elapsed_ms)
      : deliveryStatus === "running"
        ? formatDuration(tickMs)
        : null
    : null;

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
          {/* feat-439-M2: 过程盘在有工具调用 OR 有思考段时渲染（无思考不留空壳）。 */}
          {isAgent &&
            ((message.tool_calls && message.tool_calls.length > 0) ||
              (message.thinking && message.thinking.length > 0)) && (
              <ToolCallsPanel
                toolCalls={message.tool_calls ?? []}
                thinking={message.thinking}
              />
            )}
          {isAgent && deliveryStatus === "completed" && message.token_usage && (
            <TokenChip usage={message.token_usage} dataTestId={`message-token-chip-${message.id}`} />
          )}
          {/* feat-434 决策 1/3: 待决审批卡收进气泡内最下方（不再飘在气泡外的墙）。只渲染
              pending —— 已决审批已并入工具行的闸门区，独立已决卡取消（决策 3）。同一 message
              多次 ask 时，已决的并入工具面板，pending 的在此醒目可操作。 */}
          {isAgent && (message.permission_requests ?? [])
            .filter((req) => req.status !== "resolved")
            .map((req) => (
              <PermissionCard
                key={req.request_id}
                request={req}
                conversationId={message.conversation_id}
                messageId={message.id}
                onResolved={() => {/* WS event will update the message status */}}
              />
            ))}
        </div>
        <div className={`chat-bubble-status mt-[2px] flex items-center gap-2 text-[11px] text-[oklch(0.55 0.01 240)] ${statusAlign}`}>
          <span data-testid={`message-timestamp-${message.id}`}>{ts}</span>
          {deliveryStatus === "running" && (
            // feat-414: oklch 任意值含空格，Tailwind 会拆词导致类名失效；改用内联 style 确保颜色可靠渲染
            <span className="flex items-center gap-1" style={{ color: "oklch(0.65 0.15 60)" }}>
              <span
                className="inline-block w-[6px] h-[6px] rounded-full animate-pulse"
                style={{ backgroundColor: "oklch(0.70 0.18 60)" }}
              />
              {/* feat-414: running 态实时走 tick；有值时加 ⏱ 与 prototype.html 对齐，无值时回退文案 */}
              {elapsedDisplay != null ? `⏱ ${elapsedDisplay}` : t("chat.messagePane.running")}
            </span>
          )}
          {/* feat-414: completed agent 消息在时间戳右侧显示本轮墙钟，中性灰 */}
          {deliveryStatus === "completed" && elapsedDisplay && (
            <span
              data-testid={`message-elapsed-${message.id}`}
              className="text-[oklch(0.55 0.01 240)]"
            >
              ⏱ {elapsedDisplay}
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

// CR-3: remarkPlugins 和无闭包依赖的 table/th/td components 提到模块级常量，
// 避免每次 render 重建引用导致 react-markdown 重建 unified pipeline。

// CR-2: node prop 不透传 DOM（react-markdown v10 ExtraProps 传 node，不是合法 DOM attr）。
// CR-6: hast-util-to-jsx-runtime 已将 hast align → style.textAlign，直接透传 props
// 即可保留对齐（无需在 components 中二次转换 align 属性）。
const MD_REMARK_PLUGINS = [remarkGfm, remarkMention];
const MD_TABLE_COMPONENTS: Pick<Components, "table" | "th" | "td"> = {
  table: ({ node: _node, ...props }) => (
    <table {...props} className="im-md-table" />
  ),
  th: ({ node: _node, ...props }) => <th {...props} />,
  td: ({ node: _node, ...props }) => <td {...props} />,
};

/**
 * MarkdownContent — 渲染 agent/对方气泡的块级 Markdown 内容。
 *
 * bugfix-413: 改用 react-markdown + remark-gfm 取代手写渲染器，彻底支持
 * CommonMark/GFM（标题/分隔线/引用块/嵌套列表/链接/表格/代码块）。
 * @mention 经 remarkMention 插件在 mdast 层切出，注入带 data-* 属性的 <span>，
 * 再由 components.span 映射渲染成 .chat-mention-chip。
 *
 * 对外 props 签名不变，调用点（message-pane.tsx:401）零改动。
 * raw HTML 安全：不引 rehype-raw，agent 输出的 <script> 等一律转义为字面量。
 */
function MarkdownContent({
  content,
  participants,
}: {
  content: string;
  participants?: Actor[];
}) {
  // CR-3: participantMap 和 components 用 useMemo，仅 participants 变化时重建，
  // 保证 react-markdown 的 components 引用稳定，不触发不必要的 pipeline 重建。
  const participantMap = useMemo(() => {
    const map = new Map<string, string>();
    if (participants) {
      for (const p of participants) {
        map.set(p.id, p.display_name ?? p.id);
      }
    }
    return map;
  }, [participants]);

  const components: Components = useMemo(() => ({
    ...MD_TABLE_COMPONENTS,
    // CR-2: node prop 不透传 DOM。
    // remarkMention sets data-mention-target-id on the injected <span>.
    span: ({ node: _node, children, ...props }) => {
      const targetId = (props as Record<string, unknown>)["data-mention-target-id"] as string | undefined;

      if (!targetId) {
        // Plain span — pass through untouched.
        return <span {...props}>{children}</span>;
      }

      const displayName = participantMap.get(targetId);
      if (displayName) {
        return (
          <span className="chat-mention-chip" data-target-id={targetId}>
            @{displayName}
          </span>
        );
      }
      // Unknown target_id: same fallback as the prior renderInlineContent path.
      return (
        <span className="chat-mention-chip chat-mention-chip--unknown">
          @unknown
        </span>
      );
    },
  }), [participantMap]);

  return (
    <div className="im-md">
      <ReactMarkdown
        remarkPlugins={MD_REMARK_PLUGINS}
        components={components}
      >
        {content}
      </ReactMarkdown>
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

function formatHM(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}
