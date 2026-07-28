import * as Dialog from "@radix-ui/react-dialog";
import React, {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent,
  type FormEvent,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent
} from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { useTranslation } from "../../../i18n";
import {
  classifyChatLink,
  extractCodeText,
  resolveContextMenuModality,
  serializeMessageBody,
  shouldKeepNativeContextMenu,
  type ContextMenuContextFacts,
  type RecentPointerRecord
} from "./message-content-policy";
import { AttachmentChip } from "../attachments/attachment-chip";
import { AttachmentDropzone } from "../attachments/attachment-dropzone";
import { uploadOneAttachment } from "../attachments/use-attachment-upload";
import {
  classifyConversationKind,
  type Actor,
  type Attachment,
  type Conversation,
  type MentionCandidate,
  type Message,
  type TimelineItem
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
  /** Typed timeline keeps durable non-message entries out of MessageBubble. */
  timeline?: TimelineItem[];
  /** Compatibility input for callers not yet upgraded to the typed timeline. */
  messages?: Message[];
  mentionCandidates: MentionCandidate[];
  draftSeed?: { id: string; text: string } | null;
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
  onSend(text: string, attachments: Attachment[]): void | Promise<void>;
  onBack?(): void;
  onOpenConfig?(): void;
  /** Send mutation error message, shown as an in-app toast. */
  sendError?: string | null;
  /** Current logged-in user id; used to distinguish local send appends from external user messages. */
  selfUserId?: string | null;
  /** Whether a message is currently being sent. */
  isSending?: boolean;
  /** feat-445-M1: this is a direct user↔agent chat (fork is only offered here). */
  isDirectChat?: boolean;
  /** feat-445-M1: the agent's node is online (fork requires a live agent). */
  agentOnline?: boolean;
  /** feat-445-M1: fork from one completed agent reply (by message id). */
  onFork?(messageId: string): void;
  /** feat-445-M2 #7: a fork is in flight — disable fork buttons to block double-submit. */
  forkPending?: boolean;
  /** Older history page exists above the currently loaded messages. */
  hasMoreHistory?: boolean | null;
  /** Older history request is in flight. */
  isLoadingHistory?: boolean;
  /** Trigger loading the next older history page. */
  onLoadOlder?(): void;
  /** Test seam: overrides the real upload helper so vitest can stub uploads. */
  uploadAttachment?(file: File): Promise<Attachment>;
  /** Reports each rejected attachment to the page-level error owner. */
  onAttachmentUploadError?(error: unknown): void;
}

const MENTION_RE = /@([^@\s]*)$/;
const NEAR_BOTTOM_PX = 80;

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
 * string + attachment snapshot, clearing those values only after async success.
 * A failed send keeps the draft and attachments available for retry.
 * Mention picker activates only when `classifyConversationKind` resolves to
 * `group` or `agent-network` (matches spec Q5 — mention only meaningful when
 * there are 2+ agents to disambiguate).
 */
export function MessagePane({
  conversation,
  timeline,
  messages: messagesProp,
  mentionCandidates,
  draftSeed = null,
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
  selfUserId = null,
  isSending,
  isDirectChat = false,
  agentOnline = false,
  onFork,
  forkPending = false,
  hasMoreHistory = null,
  isLoadingHistory = false,
  onLoadOlder,
  uploadAttachment = uploadOneAttachment,
  onAttachmentUploadError
}: MessagePaneProps) {
  const { t } = useTranslation();
  const messages = messagesProp ?? timeline?.flatMap((item) => item.type === "message" ? [item.message] : []) ?? [];
  const renderedTimeline = timeline ?? messages.map((message) => ({ type: "message" as const, message }));
  const anchoredMessageIds = new Set(messages.map((message) => message.id));
  const [draft, setDraft] = useState("");
  const [draftMentions, setDraftMentions] = useState<DraftMention[]>([]);
  const [pending, setPending] = useState<Attachment[]>([]);
  const [composerSending, setComposerSending] = useState(false);
  // feat-430: Esc / click-outside hides the slash picker but keeps the `/` text;
  // any further typing re-opens it (reset on draft change).
  const [slashDismissed, setSlashDismissed] = useState(false);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const mirrorRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const slashWrapRef = useRef<HTMLDivElement | null>(null);
  const historyWasLoadingRef = useRef(false);
  const historyAnchorRef = useRef<{
    messageId: string;
    scrollTop: number;
    scrollHeight: number;
  } | null>(null);
  const skipNextMessageAutoScrollRef = useRef(false);
  const lastMessageIdRef = useRef<string | null>(null);
  const nearBottomRef = useRef(true);
  const forceScrollToBottomRef = useRef(false);
  const sendInFlightRef = useRef(false);
  const composerBusy = Boolean(isSending || composerSending);

  // feat-484-M1: pane-level copy coordination.
  const conversationGenerationRef = useRef(0);
  const surfaceTokenRef = useRef(0);
  const attemptTokenRef = useRef(0);
  const noticeTokenRef = useRef(0);
  const noticeTimerRef = useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const latestCopyAttemptRef = useRef<{
    attemptToken: number;
    conversationGeneration: number;
    surfaceToken: number | null;
  } | null>(null);

  type ActiveMessageAction = {
    surfaceToken: number;
    conversationId: string;
    messageId: string;
    bodyElement: HTMLElement;
    surface: "context-menu" | "action-sheet";
    anchor: { x: number; y: number } | null;
    trigger: HTMLElement | null;
  };

  const [activeMessageAction, setActiveMessageAction] = useState<ActiveMessageAction | null>(null);

  type CopyNotice = {
    noticeToken: number;
    attemptToken: number;
    conversationGeneration: number;
    kind: "success" | "error";
    message: string;
  } | null;

  const [copyNotice, setCopyNotice] = useState<CopyNotice>(null);

  useEffect(() => {
    if (!draftSeed) return;
    setDraft(draftSeed.text);
    const el = composerRef.current;
    if (el) {
      requestAnimationFrame(() => {
        el.setSelectionRange(draftSeed.text.length, draftSeed.text.length);
      });
    }
  }, [draftSeed?.id]);

  useLayoutEffect(() => {
    // Bump generation before new conversation paint so any in-flight copy from the
    // previous conversation becomes a no-op.
    conversationGenerationRef.current += 1;
    setActiveMessageAction(null);
    setCopyNotice(null);
    if (noticeTimerRef.current !== null) {
      window.clearTimeout(noticeTimerRef.current);
      noticeTimerRef.current = null;
    }
  }, [conversation.id]);

  function closeActionSurface(reason: "copy-success" | "branch" | "dismiss") {
    setActiveMessageAction((current) => {
      if (!current) return null;
      const trigger = current.trigger;
      const shouldRestoreFocus = reason !== "copy-success" || trigger?.isConnected === true;
      if (shouldRestoreFocus && trigger?.isConnected) {
        requestAnimationFrame(() => trigger.focus({ preventScroll: true }));
      }
      return null;
    });
  }

  function showCopyNotice(kind: "success" | "error") {
    noticeTokenRef.current += 1;
    const token = noticeTokenRef.current;
    const generation = conversationGenerationRef.current;
    const message = kind === "success"
      ? t("chat.messagePane.copySuccess")
      : t("chat.messagePane.copyError");
    setCopyNotice({ noticeToken: token, attemptToken: latestCopyAttemptRef.current?.attemptToken ?? token, conversationGeneration: generation, kind, message });
    if (noticeTimerRef.current !== null) {
      window.clearTimeout(noticeTimerRef.current);
    }
    noticeTimerRef.current = window.setTimeout(() => {
      setCopyNotice((current) => {
        if (!current) return null;
        if (current.noticeToken !== token || current.conversationGeneration !== generation) return current;
        return null;
      });
    }, kind === "success" ? 1600 : 4000);
  }

  function publishCopyResult(
    attemptToken: number,
    kind: "success" | "error",
    surfaceToken: number | null
  ) {
    const latest = latestCopyAttemptRef.current;
    if (!latest) return;
    if (latest.attemptToken !== attemptToken) return;
    if (latest.conversationGeneration !== conversationGenerationRef.current) return;

    if (surfaceToken !== null) {
      const surface = activeMessageAction;
      if (!surface || surface.surfaceToken !== surfaceToken) return;
    }

    if (kind === "success") {
      closeActionSurface("copy-success");
    }
    showCopyNotice(kind);
  }

  function requestCopy(payload: {
    conversationId: string;
    messageId: string;
    bodyElement?: HTMLElement;
    codeElement?: HTMLElement;
    surfaceToken?: number;
  }) {
    if (payload.conversationId !== conversation.id) return;
    const currentGeneration = conversationGenerationRef.current;

    const target = payload.codeElement ?? payload.bodyElement;
    if (!target) return;
    if (!target.isConnected) return;

    const text = payload.codeElement
      ? extractCodeText(payload.codeElement)
      : serializeMessageBody(payload.bodyElement!);

    const writeText = navigator.clipboard?.writeText;
    if (!writeText) {
      attemptTokenRef.current += 1;
      const attemptToken = attemptTokenRef.current;
      latestCopyAttemptRef.current = { attemptToken, conversationGeneration: currentGeneration, surfaceToken: payload.surfaceToken ?? null };
      publishCopyResult(attemptToken, "error", payload.surfaceToken ?? null);
      return;
    }

    attemptTokenRef.current += 1;
    const attemptToken = attemptTokenRef.current;
    latestCopyAttemptRef.current = { attemptToken, conversationGeneration: currentGeneration, surfaceToken: payload.surfaceToken ?? null };

    writeText
      .call(navigator.clipboard, text)
      .then(() => publishCopyResult(attemptToken, "success", payload.surfaceToken ?? null))
      .catch(() => publishCopyResult(attemptToken, "error", payload.surfaceToken ?? null));
  }

  function requestMessageMenu(payload: {
    messageId: string;
    bodyElement: HTMLElement;
    x: number;
    y: number;
    trigger: HTMLElement | null;
  }) {
    if (payload.bodyElement?.isConnected !== true) return;
    surfaceTokenRef.current += 1;
    setActiveMessageAction({
      surfaceToken: surfaceTokenRef.current,
      conversationId: conversation.id,
      messageId: payload.messageId,
      bodyElement: payload.bodyElement,
      surface: "context-menu",
      anchor: { x: payload.x, y: payload.y },
      trigger: payload.trigger,
    });
  }

  function requestActionSheet(payload: {
    messageId: string;
    bodyElement: HTMLElement;
    trigger: HTMLElement | null;
  }) {
    if (payload.bodyElement?.isConnected !== true) return;
    surfaceTokenRef.current += 1;
    setActiveMessageAction({
      surfaceToken: surfaceTokenRef.current,
      conversationId: conversation.id,
      messageId: payload.messageId,
      bodyElement: payload.bodyElement,
      surface: "action-sheet",
      anchor: null,
      trigger: payload.trigger,
    });
  }


  const kind = classifyConversationKind(conversation);
  const isGroup = kind === "group" || kind === "agent-network";
  const mentionMatch = isGroup ? MENTION_RE.exec(draft) : null;
  const mentionQuery = mentionMatch?.[1] ?? null;

  // feat-430: slash picker triggers only at the START of the composer (决策 6) and
  // never simultaneously with the @ mention picker. Available in single and group chats.
  const slashMatch =
    mentionQuery === null && !slashDismissed ? matchSlashTrigger(draft) : null;
  const minComposerRows = isMobile ? 1 : 2;
  const maxComposerRows = isMobile ? 4 : 5;
  const composerRows = Math.min(
    maxComposerRows,
    Math.max(minComposerRows, draft.split("\n").length)
  );

  function changeDraft(next: string) {
    setSlashDismissed(false);
    setDraft(next);
  }

  const placeholder = isGroup
    ? t("chat.messagePane.placeholderGroup")
    : t("chat.messagePane.placeholderDirect", { title: conversation.title });

  async function commit(text: string) {
    if (isSending || sendInFlightRef.current) return;
    const trimmed = text.trim();
    if (!trimmed && pending.length === 0) return;
    // bugfix-358 (composer): textarea 装可见 `@DisplayName`, wire XML 在此处重建。
    const wireContent = reconstructWireContent(trimmed, draftMentions);
    const submittedAttachments = pending;
    const submittedAttachmentUrls = new Set(submittedAttachments.map((attachment) => attachment.url));
    forceScrollToBottomRef.current = true;
    sendInFlightRef.current = true;
    setComposerSending(true);
    try {
      await onSend(wireContent, submittedAttachments);
    } catch {
      forceScrollToBottomRef.current = false;
      return;
    } finally {
      sendInFlightRef.current = false;
      setComposerSending(false);
    }
    setDraft("");
    setDraftMentions([]);
    setPending((current) => current.filter((attachment) => !submittedAttachmentUrls.has(attachment.url)));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void commit(draft);
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
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
      }
      return;
    }
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      if (mentionQuery !== null) return;
      e.preventDefault();
      void commit(draft);
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
    if (sendInFlightRef.current) return;
    for (const file of files) {
      try {
        // Sequential uploads keep the chip ordering deterministic and avoid
        // bursting `/im/v1/uploads` with N parallel large bodies.
        const att = await uploadAttachment(file);
        setPending((prev) => [...prev, att]);
      } catch (error) {
        onAttachmentUploadError?.(error);
      }
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    if (composerBusy) return;

    const itemImages = Array.from(event.clipboardData.items)
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter((file): file is File => file !== null);
    // Browsers commonly expose the same image through both collections. Files
    // are therefore compatibility fallback, never an additional source.
    const images = itemImages.length > 0
      ? itemImages
      : Array.from(event.clipboardData.files).filter((file) => file.type.startsWith("image/"));
    if (images.length === 0) return;

    event.preventDefault();
    void handleAdd(images);
  }

  function messageRows(): HTMLElement[] {
    const el = messagesContainerRef.current;
    if (!el) return [];
    return Array.from(el.querySelectorAll<HTMLElement>("[data-message-id]"));
  }

  function captureHistoryAnchor() {
    const el = messagesContainerRef.current;
    if (!el) return;
    const rows = messageRows();
    const anchor = rows.find((row) => row.offsetTop >= el.scrollTop) ?? rows[0] ?? null;
    historyAnchorRef.current = anchor
      ? {
        messageId: anchor.dataset.messageId ?? "",
        scrollTop: el.scrollTop,
        scrollHeight: el.scrollHeight
      }
      : null;
  }

  function restoreHistoryAnchor() {
    const el = messagesContainerRef.current;
    const anchor = historyAnchorRef.current;
    if (!el || !anchor) return;
    const row = messageRows().find((candidate) => candidate.dataset.messageId === anchor.messageId);
    if (row) {
      el.scrollTop = row.offsetTop;
    } else {
      el.scrollTop = anchor.scrollTop + (el.scrollHeight - anchor.scrollHeight);
    }
    updateNearBottom();
    skipNextMessageAutoScrollRef.current = true;
    historyAnchorRef.current = null;
  }

  function maybeLoadOlderFromScroll() {
    const el = messagesContainerRef.current;
    if (!el || hasMoreHistory !== true || isLoadingHistory || !onLoadOlder) return;
    const scrollable = el.scrollHeight - el.clientHeight;
    if (scrollable <= 0) return;
    if (el.scrollTop <= scrollable / 3) onLoadOlder();
  }

  function updateNearBottom() {
    const el = messagesContainerRef.current;
    if (!el) return;
    nearBottomRef.current = el.scrollHeight - el.clientHeight - el.scrollTop <= NEAR_BOTTOM_PX;
  }

  function handleMessagesScroll() {
    updateNearBottom();
    maybeLoadOlderFromScroll();
  }

  useEffect(() => {
    lastMessageIdRef.current = null;
    nearBottomRef.current = true;
    forceScrollToBottomRef.current = false;
    historyWasLoadingRef.current = false;
    historyAnchorRef.current = null;
    skipNextMessageAutoScrollRef.current = false;
  }, [conversation.id]);

  useEffect(() => {
    if (sendError) forceScrollToBottomRef.current = false;
  }, [sendError]);

  // Auto-scroll only when the user is already following the bottom, or when the
  // local user just sent a message. Prepending history and off-bottom arrivals
  // must not steal the reading position.
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    if (skipNextMessageAutoScrollRef.current) {
      skipNextMessageAutoScrollRef.current = false;
      return;
    }
    if (historyAnchorRef.current) return;
    const lastMessage = messages[messages.length - 1] ?? null;
    const lastMessageId = lastMessage?.id ?? null;
    const lastMessageChanged = lastMessageIdRef.current !== lastMessageId;
    const lastMessageIsSelfAuthored =
      lastMessage?.sender.type === "user" &&
      selfUserId !== null &&
      (lastMessage.sender_user_id === selfUserId || lastMessage.sender.id === selfUserId);
    const isInitialHydration = lastMessageIdRef.current === null;
    const shouldFollowBottom =
      isInitialHydration
      || (forceScrollToBottomRef.current && lastMessageChanged && lastMessageIsSelfAuthored)
      || nearBottomRef.current;
    lastMessageIdRef.current = lastMessageId;
    if (shouldFollowBottom) {
      el.scrollTop = el.scrollHeight;
      updateNearBottom();
    }
    forceScrollToBottomRef.current = false;
  }, [messages]);

  useLayoutEffect(() => {
    if (isLoadingHistory && !historyWasLoadingRef.current) {
      captureHistoryAnchor();
    }
    if (!isLoadingHistory && historyWasLoadingRef.current) {
      restoreHistoryAnchor();
    }
    historyWasLoadingRef.current = isLoadingHistory;
  }, [isLoadingHistory, messages]);

  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el || hasMoreHistory !== true || isLoadingHistory || !onLoadOlder) return;
    if (el.scrollHeight > 0 && el.scrollHeight <= el.clientHeight) onLoadOlder();
  }, [hasMoreHistory, isLoadingHistory, messages.length, onLoadOlder]);

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

      <div ref={messagesContainerRef} className="chat-pane-messages" onScroll={handleMessagesScroll}>
        {messages.length === 0 ? (
          <div className="chat-pane-empty">
            <div className="chat-pane-empty-icon" aria-hidden="true">✨</div>
            <p className="chat-pane-empty-title">{t("chat.messagePane.emptyTitle")}</p>
            <p className="chat-pane-empty-sub">{t("chat.messagePane.emptySubtitle")}</p>
          </div>
        ) : (
          <>
            {(isLoadingHistory || hasMoreHistory === false) && (
              <div className="chat-history-status" role="status">
                {isLoadingHistory && <span className="chat-history-spinner" aria-hidden="true" />}
                {isLoadingHistory
                  ? t("chat.messagePane.historyLoading")
                  : t("chat.messagePane.historyEnd")}
              </div>
            )}
            {renderedTimeline.map((item) => {
              if (item.type === "agent_config_changed") {
                return anchoredMessageIds.has(item.before_message_id)
                  ? <ConfigurationBoundaryDivider key={item.id} />
                  : null;
              }
              const m = item.message;
              return (
                <MessageBubble
                  key={m.id}
                  message={m}
                  conversationId={conversation.id}
                  isMobile={isMobile}
                  participants={conversation.participants}
                  isDirectChat={isDirectChat}
                  agentOnline={agentOnline}
                  onFork={onFork}
                  forkPending={forkPending}
                  onCopyRequest={requestCopy}
                  onMenuRequest={requestMessageMenu}
                  onSheetRequest={requestActionSheet}
                />
              );
            })}
          </>
        )}
      </div>

      <form className="chat-pane-composer" onSubmit={handleSubmit}>
        <AttachmentDropzone className="chat-pane-composer-dropzone" onAdd={handleAdd} disabled={composerBusy}>
          {pending.length > 0 && (
            <div className="chat-pane-composer-chips">
              {pending.map((att) => (
                <AttachmentChip
                  key={att.url}
                  attachment={att}
                  onRemove={() => {
                    if (sendInFlightRef.current) return;
                    setPending((prev) => prev.filter((p) => p.url !== att.url));
                  }}
                  removeDisabled={composerBusy}
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
                onPaste={handlePaste}
                disabled={composerBusy}
                onScroll={() => {
                  if (mirrorRef.current && composerRef.current) {
                    mirrorRef.current.scrollTop = composerRef.current.scrollTop;
                  }
                }}
                placeholder={placeholder}
                rows={composerRows}
                className="chat-pane-composer-input chat-composer-highlight-input"
              />
            </div>
            <button
              type="submit"
              className="chat-pane-composer-send"
              disabled={composerBusy || (!draft.trim() && pending.length === 0)}
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

      {/* feat-484-M1: single pane-level copy snackbar / live region. */}
      {copyNotice && (
        <div
          className={`chat-copy-notice chat-copy-notice--${copyNotice.kind}`}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {copyNotice.message}
        </div>
      )}

      {/* feat-484-M1: single pane-level context menu for mouse right-clicks. */}
      {activeMessageAction?.surface === "context-menu" && activeMessageAction.anchor && (
        <div
          ref={(el) => {
            if (el && activeMessageAction.anchor) {
              const { x, y } = activeMessageAction.anchor;
              const menuWidth = el.offsetWidth || 160;
              const menuHeight = el.offsetHeight || 80;
              el.style.left = `${Math.min(Math.max(8, x), Math.max(8, window.innerWidth - menuWidth))}px`;
              el.style.top = `${Math.min(Math.max(8, y), Math.max(8, window.innerHeight - menuHeight))}px`;
            }
          }}
          role="menu"
          className="chat-message-menu"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              closeActionSurface("dismiss");
            }
          }}
        >
          <MessageActionList
            message={messages.find((m) => m.id === activeMessageAction.messageId)!}
            isDirectChat={isDirectChat}
            agentOnline={agentOnline}
            forkPending={forkPending}
            surface="context-menu"
            onCopy={() =>
              requestCopy({
                conversationId: activeMessageAction.conversationId,
                messageId: activeMessageAction.messageId,
                bodyElement: activeMessageAction.bodyElement,
                surfaceToken: activeMessageAction.surfaceToken,
              })
            }
            onFork={() => {
              if (agentOnline && !forkPending && onFork) {
                closeActionSurface("branch");
                onFork(activeMessageAction.messageId);
              }
            }}
            onClose={() => closeActionSurface("dismiss")}
          />
        </div>
      )}

      {/* feat-484-M1: mobile/coarse action sheet. */}
      <Dialog.Root
        open={activeMessageAction?.surface === "action-sheet"}
        onOpenChange={(open) => {
          if (!open) closeActionSurface("dismiss");
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="chat-action-sheet-overlay" />
          <Dialog.Content
            className="chat-action-sheet-content"
            onCloseAutoFocus={(e) => {
              const trigger = activeMessageAction?.trigger;
              if (trigger?.isConnected) {
                trigger.focus({ preventScroll: true });
              } else {
                e.preventDefault();
              }
            }}
          >
            <Dialog.Title className="chat-action-sheet-title">
              {t("chat.messagePane.messageActions")}
            </Dialog.Title>
            <Dialog.Description className="sr-only">
              {t("chat.messagePane.messageActions")}
            </Dialog.Description>
            {activeMessageAction && (
              <MessageActionList
                message={messages.find((m) => m.id === activeMessageAction.messageId)!}
                isDirectChat={isDirectChat}
                agentOnline={agentOnline}
                forkPending={forkPending}
                surface="action-sheet"
                onCopy={() =>
                  requestCopy({
                    conversationId: activeMessageAction.conversationId,
                    messageId: activeMessageAction.messageId,
                    bodyElement: activeMessageAction.bodyElement,
                    surfaceToken: activeMessageAction.surfaceToken,
                  })
                }
                onFork={() => {
                  if (agentOnline && !forkPending && onFork) {
                    closeActionSurface("branch");
                    onFork(activeMessageAction.messageId);
                  }
                }}
                onClose={() => closeActionSurface("dismiss")}
              />
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}

function ConfigurationBoundaryDivider() {
  return (
    <div className="chat-configuration-boundary" role="separator" aria-label="Agent 配置已更新">
      <span>Agent 配置已更新 · 后续请求将不再命中此前的上下文缓存</span>
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

function MessageActionList({
  message,
  isDirectChat = false,
  agentOnline = false,
  forkPending = false,
  surface = "context-menu",
  onCopy,
  onFork,
  onClose,
}: {
  message: Message;
  isDirectChat?: boolean;
  agentOnline?: boolean;
  forkPending?: boolean;
  surface?: "toolbar" | "context-menu" | "action-sheet";
  onCopy: () => void;
  onFork: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const isAgent = message.sender.type === "agent";
  const forkEligible =
    isAgent &&
    message.delivery_status === "completed" &&
    isDirectChat &&
    Boolean(message.kernel_message_id);

  const forkAvailable = forkEligible && agentOnline && !forkPending;
  const forkReason = forkEligible
    ? forkPending
      ? t("chat.messagePane.branchPending")
      : agentOnline
        ? null
        : t("chat.messagePane.branchOffline")
    : null;

  function handleFork() {
    if (forkAvailable) {
      onFork();
    }
  }

  const layout = surface === "toolbar" ? "horizontal" : "vertical";
  const itemRole = surface === "context-menu" ? "menuitem" : undefined;
  const isCompact = surface !== "toolbar";

  return (
    <div className={`chat-message-actions chat-message-actions--${layout}`} role="group" aria-label={t("chat.messagePane.messageActions")} data-testid={`message-actions-${message.id}`}>
      <button
        type="button"
        role={itemRole}
        className="chat-message-action chat-message-action--copy"
        data-testid={`message-copy-${message.id}`}
        onClick={onCopy}
        aria-label={t("chat.messagePane.copyMessage")}
        title={t("chat.messagePane.copyMessage")}
      >
        {surface === "toolbar" ? "⎘" : t("chat.messagePane.copyMessage")}
      </button>
      {forkEligible && (
        <button
          type="button"
          role={itemRole}
          className="chat-message-action chat-message-action--branch"
          data-testid={`message-branch-${message.id}`}
          onClick={handleFork}
          aria-disabled={!forkAvailable}
          aria-label={t("chat.messagePane.branchFromHere")}
          title={forkReason ?? t("chat.messagePane.branchFromHere")}
        >
          {surface === "toolbar" ? "⑂" : t("chat.messagePane.branchFromHere")}
          {isCompact && forkReason && (
            <span className="chat-message-action-reason">{forkReason}</span>
          )}
        </button>
      )}
      {isCompact && (
        <button
          type="button"
          role={itemRole}
          className="chat-message-action chat-message-action--cancel"
          onClick={onClose}
        >
          {t("common.cancel")}
        </button>
      )}
    </div>
  );
}

function MessageBubble({
  message,
  conversationId,
  isMobile,
  participants,
  isDirectChat = false,
  agentOnline = false,
  onFork,
  forkPending = false,
  onCopyRequest,
  onMenuRequest,
  onSheetRequest,
}: {
  message: Message;
  conversationId: string;
  isMobile?: boolean;
  participants?: Actor[];
  isDirectChat?: boolean;
  agentOnline?: boolean;
  onFork?(messageId: string): void;
  forkPending?: boolean;
  onCopyRequest(payload: {
    conversationId: string;
    messageId: string;
    bodyElement?: HTMLElement;
    codeElement?: HTMLElement;
    surfaceToken?: number;
  }): void;
  onMenuRequest(payload: {
    messageId: string;
    bodyElement: HTMLElement;
    x: number;
    y: number;
    trigger: HTMLElement | null;
  }): void;
  onSheetRequest(payload: {
    messageId: string;
    bodyElement: HTMLElement;
    trigger: HTMLElement | null;
  }): void;
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

  const forkEligible =
    isAgent &&
    deliveryStatus === "completed" &&
    isDirectChat &&
    Boolean(message.kernel_message_id);
  const forkAvailable = forkEligible && agentOnline && !forkPending;

  const cardRef = useRef<HTMLDivElement | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const moreButtonRef = useRef<HTMLButtonElement | null>(null);
  const recentPointerRef = useRef<RecentPointerRecord | null>(null);

  function recordPointer(e: ReactPointerEvent<HTMLElement>) {
    const native = e.nativeEvent;
    const secondaryKind =
      native.button === 2 ? "button-2" :
      native.button === 0 && native.ctrlKey ? "control-primary" :
      null;
    if (native.pointerType === "mouse" && secondaryKind === null) return;
    recentPointerRef.current = {
      messageId: message.id,
      pointerType: native.pointerType,
      button: native.button,
      ctrlKey: native.ctrlKey,
      clientX: native.clientX,
      clientY: native.clientY,
      timeStamp: native.timeStamp,
    };
  }

  function handleContextMenu(e: React.MouseEvent<HTMLDivElement>) {
    const body = bodyRef.current;
    if (!body) return;

    const native = e.nativeEvent as MouseEvent & { pointerType?: string };
    const contextFacts: ContextMenuContextFacts = {
      messageId: message.id,
      pointerType: native.pointerType,
      button: native.button,
      buttons: native.buttons,
      ctrlKey: native.ctrlKey,
      clientX: native.clientX,
      clientY: native.clientY,
      timeStamp: native.timeStamp,
    };
    const modality = resolveContextMenuModality(contextFacts, recentPointerRef.current);
    const keepNative = shouldKeepNativeContextMenu(
      modality,
      body,
      native.target,
      native.clientX,
      native.clientY,
      window.getSelection(),
      document
    );

    if (keepNative) {
      recentPointerRef.current = null;
      return;
    }

    e.preventDefault();
    onMenuRequest({
      messageId: message.id,
      bodyElement: body,
      x: native.clientX,
      y: native.clientY,
      trigger: cardRef.current,
    });
  }

  function handleCopy() {
    const body = bodyRef.current;
    if (!body) return;
    onCopyRequest({ conversationId, messageId: message.id, bodyElement: body });
  }

  function handleFork() {
    if (forkAvailable && onFork) {
      onFork(message.id);
    }
  }

  function handleMore() {
    const body = bodyRef.current;
    if (!body) return;
    onSheetRequest({
      messageId: message.id,
      bodyElement: body,
      trigger: moreButtonRef.current,
    });
  }

  // feat-414: running tick state.
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
    <div
      data-message-id={message.id}
      className={`chat-bubble chat-bubble--${isUser ? "user" : "agent"} flex ${rowFlex} gap-2 items-end`}
    >
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
        <div
          ref={cardRef}
          data-testid={`message-bubble-${message.id}`}
          className="chat-bubble-card"
          onPointerDown={recordPointer}
          onContextMenu={handleContextMenu}
        >
          {message.content && (
            <div ref={bodyRef} className="chat-message-body">
              {isUser
                ? renderInlineContent(message.content, participants)
                : <MarkdownContent content={message.content} participants={participants} onCopyCode={(codeElement) => onCopyRequest({ conversationId, messageId: message.id, codeElement })} />}
            </div>
          )}
          {message.attachments && message.attachments.length > 0 && (
            <div className="chat-bubble-attachments">
              {message.attachments.map((att) => (
                <AttachmentChip key={att.url} attachment={att} />
              ))}
            </div>
          )}
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

          {/* Desktop fine-pointer / keyboard toolbar. */}
          <div
            ref={toolbarRef}
            className="chat-message-toolbar"
            role="toolbar"
            aria-label={t("chat.messagePane.messageActions")}
          >
            <MessageActionList
              message={message}
              isDirectChat={isDirectChat}
              agentOnline={agentOnline}
              forkPending={forkPending}
              surface="toolbar"
              onCopy={handleCopy}
              onFork={handleFork}
              onClose={() => {}}
            />
          </div>
        </div>

        <div className={`chat-bubble-status mt-[2px] flex items-center gap-2 text-[11px] text-[oklch(0.55 0.01 240)] ${statusAlign}`}>
          <span data-testid={`message-timestamp-${message.id}`}>{ts}</span>
          {deliveryStatus === "running" && (
            <span className="flex items-center gap-1" style={{ color: "oklch(0.65 0.15 60)" }}>
              <span
                className="inline-block w-[6px] h-[6px] rounded-full animate-pulse"
                style={{ backgroundColor: "oklch(0.70 0.18 60)" }}
              />
              {elapsedDisplay != null ? `⏱ ${elapsedDisplay}` : t("chat.messagePane.running")}
            </span>
          )}
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

          {/* Compact / coarse More trigger. Always rendered; CSS decides visibility. */}
          <button
            ref={moreButtonRef}
            type="button"
            className="chat-message-more"
            data-testid={`message-more-${message.id}`}
            onClick={handleMore}
            aria-label={t("chat.messagePane.messageActions")}
            aria-haspopup="dialog"
          >
            ⋯
          </button>
        </div>
      </div>
    </div>
  );
}


function MarkdownContent({
  content,
  participants,
  onCopyCode,
}: {
  content: string;
  participants?: Actor[];
  onCopyCode?(codeElement: HTMLElement): void;
}) {
  const { t } = useTranslation();
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
    span: (props: any) => {
      const { node: _node, children, ...rest } = props;
      const targetId = rest["data-mention-target-id"] as string | undefined;

      if (!targetId) {
        // Plain span — pass through untouched.
        return <span {...rest}>{children}</span>;
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
    a: (props: any) => {
      const { node: _node, children, href, ...rest } = props;
      const label = React.Children.toArray(children).map((c) =>
        typeof c === "string" ? c : ""
      ).join("");
      const disposition = classifyChatLink(href ?? "", label, window.location.href);
      if (disposition === "unsupported") {
        return <span className="im-md-link-unsupported">{children}</span>;
      }
      if (disposition === "system") {
        return <a {...rest} href={href} className="im-md-link-system">{children}</a>;
      }
      const isExternal = disposition === "external";
      let isNamedExternal = false;
      if (isExternal) {
        try {
          const normalizedLabel = new URL(label, window.location.href);
          const normalizedHref = new URL(href ?? "", window.location.href);
          isNamedExternal = normalizedLabel.href !== normalizedHref.href;
        } catch {
          isNamedExternal = true;
        }
      }
      return (
        <a
          {...rest}
          href={href}
          target={isExternal ? "_blank" : undefined}
          rel={isExternal ? "noopener noreferrer" : undefined}
          className={`im-md-link ${isExternal ? "im-md-link--external" : ""}`}
          aria-label={
            isExternal
              ? t("chat.messagePane.linkOpensInNewTab", { label: label || href })
              : undefined
          }
        >
          {children}
          {isNamedExternal && <span className="im-md-link-indicator" aria-hidden="true" />}
        </a>
      );
    },
    pre: (props: any) => {
      const { node: _node, children, ...rest } = props;
      return (
        <div className="im-code-block" data-clipboard-exclude>
          <button
            type="button"
            className="im-code-copy"
            onClick={(e) => {
              const codeEl = (e.currentTarget.parentElement?.querySelector("pre > code") ??
                e.currentTarget.parentElement?.querySelector("code")) as HTMLElement | null;
              if (codeEl && onCopyCode) onCopyCode(codeEl);
            }}
            aria-label={t("chat.messagePane.copyCode")}
            title={t("chat.messagePane.copyCode")}
          >
            ⎘
          </button>
          <pre {...rest}>{children}</pre>
        </div>
      );
    },
  }), [participantMap, onCopyCode, t]);

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
