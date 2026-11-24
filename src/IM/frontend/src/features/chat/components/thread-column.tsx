import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowUp, Paperclip, Reply, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { authFetchJson } from "../../auth/auth-fetch";
import { createMessage } from "../chat-api";
import type { Conversation, Message, MentionCandidate, ReplyReference } from "../chat-types";
import { AttachmentDropzone } from "../attachments/attachment-dropzone";
import { ComposerAttachmentCard, useUploadRetryClock } from "../attachments/composer-attachment-card";
import { AttachmentUploadError, pastedImages, uploadOneAttachment } from "../attachments/use-attachment-upload";
import type { ComposerUpload } from "./composer-draft-store";
import type { InteractionReplyInput } from "../interactive/types";
import { MentionPicker } from "./mention-picker";
import { MENTION_RE, reconstructWireContent, type DraftMention } from "./mention-parser";

import { Avatar, colorForAgentSeed, initialsOf } from "./avatar";

interface ThreadPage {
  root: Message;
  following: boolean;
  items: {message: Message}[];
}

interface ThreadColumnProps {
  conversation: Conversation;
  rootId: string;
  targetId?: string | null;
  selfUserId?: string | null;
  mentionCandidates: MentionCandidate[];
  isMobile: boolean;
  onRead?(id: string): void;
  onSent(message: Message): void;
  onClose(): void;
  renderBody(message: Message, sendCard:(input:InteractionReplyInput, key:string)=>Promise<Message>,
    submissionId:string | undefined, locate:(id:string)=>void): ReactNode;
  renderQuote(reference: ReplyReference): ReactNode;
}

/** A reader and composer scoped to one root, including its own scroll and draft state. */
export function ThreadColumn({ conversation, rootId, targetId, selfUserId, mentionCandidates, isMobile,
  onRead, onSent, onClose, renderBody, renderQuote }: ThreadColumnProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const key = ["chat", "thread", conversation.id, rootId, selfUserId];
  const path = `/im/v1/conversations/${encodeURIComponent(conversation.id)}/threads/${encodeURIComponent(rootId)}`;
  const {data, isError, refetch} = useQuery({
    queryKey: key, queryFn: ({signal}) => authFetchJson<ThreadPage>(path, {signal}, "readThread"), gcTime: 0
  });
  const [draft, setDraft] = useState("");
  const [uploads, setUploads] = useState<ComposerUpload[]>([]);
  const retryClock = useUploadRetryClock(uploads);
  const fileInput = useRef<HTMLInputElement>(null);
  const uploadsReady = uploads.every(item => item.status === "ready");
  const [mentions, setMentions] = useState<DraftMention[]>([]);
  const [replyTo, setReplyTo] = useState<Message>();
  const [sending, setSending] = useState(false);
  const [updatingFollow, setUpdatingFollow] = useState(false);
  const [error, setError] = useState("");
  const [highlight, setHighlight] = useState<string>();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const locatedRef = useRef<string | null>(null);
  const readRef = useRef<string | undefined>(undefined);
  const attempt = useRef<{payload: string; key: string} | undefined>(undefined);
  const lastId = data?.items.at(-1)?.message.id;
  const canWrite = conversation.can_write !== false;
  const mentionMatch = conversation.type === "group" ? MENTION_RE.exec(draft) : null;

  function markVisibleTail() {
    if (stickRef.current && document.visibilityState !== "hidden" && lastId && readRef.current !== lastId) {
      readRef.current = lastId;
      onRead?.(lastId);
    }
  }
  function locate(id: string) {
    const element = document.getElementById(`thread-message-${id}`);
    if (!element) return false;
    setHighlight(id);
    element.scrollIntoView?.({block: "center"});
    element.focus({preventScroll: true});
    trackScroll();
    return true;
  }
  function trackScroll() {
    const node = scrollerRef.current;
    if (!node) return;
    stickRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 48;
    markVisibleTail();
  }
  useLayoutEffect(() => {
    if (!data) return;
    if (targetId && targetId !== locatedRef.current && locate(targetId)) {
      locatedRef.current = targetId;
      return;
    }
    const node = scrollerRef.current;
    if (node && stickRef.current) {
      node.scrollTop = node.scrollHeight;
      markVisibleTail();
    }
  }, [data, targetId]);
  useLayoutEffect(() => {
    document.addEventListener("visibilitychange", markVisibleTail);
    return () => document.removeEventListener("visibilitychange", markVisibleTail);
  }, [lastId, onRead]);

  async function upload(item: ComposerUpload) {
    const update = (patch: Partial<ComposerUpload>) =>
      setUploads(current => current.map(existing => existing.id === item.id ? {...existing, ...patch} : existing));
    update({status: "uploading"});
    try {
      update({status: "ready", attachment: await uploadOneAttachment(item.file, conversation.id)});
    } catch (cause) {
      update({status: "failed", code: cause instanceof AttachmentUploadError ? cause.code : "network",
        retryAt: cause instanceof AttachmentUploadError ? cause.retryAt : undefined});
    }
  }
  function addFiles(files: File[]) {
    if (sending || !files.length) return;
    if (files.length + uploads.length > 5) {
      setError(t("chat.messagePane.threadFileLimit"));
      return;
    }
    setError("");
    const items: ComposerUpload[] = files.map(file => ({id: crypto.randomUUID(), file, status: "queued"}));
    setUploads(current => [...current, ...items]);
    items.forEach(item => void upload(item));
  }

  function appendReply(created:Message) {
    stickRef.current = true;
    queryClient.setQueryData<ThreadPage>(key, page => page && ({...page, following: true,
      items: page.items.some(item => item.message.id === created.id) ? page.items : [...page.items, {message: created}]}));
    onSent(created);
  }
  async function sendCard(input:InteractionReplyInput, idempotencyKey:string) {
    const created = await createMessage({conversationId:conversation.id, threadRootMessageId:rootId, content:"",
      interactionReply:input, idempotencyKey});
    appendReply(created);
    return created;
  }
  const submissions=new Map(data?.items.map(item => item.message)
    .filter(m => m.sender_user_id===selfUserId && m.interaction_reply)
    .map(m => [m.interaction_reply!.source_message_id,m.id]));
  async function send() {
    const text = reconstructWireContent(draft.trim(), mentions);
    const attachments = uploads.flatMap(item => item.attachment ? [item.attachment] : []);
    if ((!text && !attachments.length) || !uploadsReady || sending) return;
    setSending(true);
    setError("");
    const payload = JSON.stringify([text, replyTo?.id, attachments]);
    if (attempt.current?.payload !== payload) attempt.current = {payload, key: crypto.randomUUID()};
    try {
      const created = await createMessage({conversationId: conversation.id, content: text,
        ...(attachments.length ? {attachments} : {}), threadRootMessageId: rootId, replyToMessageId: replyTo?.id, idempotencyKey: attempt.current.key});
      appendReply(created);
      setDraft("");
      setUploads([]);
      setMentions([]);
      setReplyTo(undefined);
      attempt.current = undefined;
    } catch {
      setError(t("chat.messagePane.sendError"));
    } finally {
      setSending(false);
    }
  }
  async function toggleFollow() {
    if (!data || updatingFollow) return;
    setUpdatingFollow(true);
    setError("");
    try {
      const following = !data.following;
      await authFetchJson(path + "/follow", {method: "POST", body: JSON.stringify({following})}, "followThread");
      queryClient.setQueryData<ThreadPage>(key, page => page && {...page, following});
      void queryClient.invalidateQueries({queryKey: ["chat", "conversations"]});
    } catch {
      setError(t("chat.messagePane.threadFollowError"));
    } finally {
      setUpdatingFollow(false);
    }
  }
  function bubble(message: Message) {
    const sender = message.sender;
    const name = sender.display_name || sender.id;
    const time = new Date(message.created_at);
    const agent = sender.type === "agent" && !message.pa_agent_id;
    return <div key={message.id} id={`thread-message-${message.id}`} tabIndex={-1}
      className={`chat-thread-message${highlight === message.id ? " im-work-message-target" : ""}`}>
      <Avatar initials={initialsOf(name)} color={colorForAgentSeed(name)} size={30} agentId={agent ? sender.id : undefined}
        personal={agent && sender.role === "personal"} avatarVariant={sender.avatar_variant} />
      <div className="chat-thread-message-body">
        <div className="chat-thread-byline">
          <strong>{name}</strong>
          {message.pa_agent_id && <span>{t("pa.sentOnBehalf")}</span>}
          {message.delegation && <span>{message.delegation.label}</span>}
          <time dateTime={message.created_at}>{time.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</time>
        </div>
        <div className="chat-bubble-card">
          {message.reply_to && <button type="button" className="chat-message-quote" onClick={() => locate(message.reply_to!.message_id)}>
            <strong>{message.reply_to.sender.display_name ?? message.reply_to.sender.id}</strong>
            <span>{renderQuote(message.reply_to)}</span>
          </button>}
          {renderBody(message,sendCard,submissions.get(message.id),locate)}
          {canWrite && ["completed", "sent", "pending"].includes(message.delivery_status) && <div className="chat-message-toolbar" role="toolbar">
            <button type="button" className="chat-message-action" aria-label={t("chat.messagePane.reply")}
              onClick={() => { setReplyTo(message); inputRef.current?.focus(); }}><Reply size={16} /></button>
          </div>}
        </div>
      </div>
    </div>;
  }
  return <aside className="chat-thread-column" aria-label={t("chat.messagePane.threadTitle")}>
    <header className="chat-pane-header">
      {isMobile && <button type="button" className="chat-pane-back" onClick={onClose} aria-label={t("common.back", "Back")}><ArrowLeft size={20}/></button>}
      <h2 className="chat-pane-title chat-pane-header-body">{t("chat.messagePane.threadTitle")}</h2>
      {conversation.type === "group" && canWrite && data && <button type="button" className="chat-pane-config"
        disabled={updatingFollow} aria-pressed={data.following} onClick={() => void toggleFollow()}>
        {t(data.following ? "chat.messagePane.following" : "chat.messagePane.follow")}
      </button>}
      {!isMobile && <button type="button" className="chat-pane-back" onClick={onClose} aria-label={t("common.close", "Close")}><X size={18}/></button>}
    </header>
    <div ref={scrollerRef} className="chat-pane-messages" onScroll={trackScroll}>
      <div className="chat-pane-message-list">
        {data && <>{bubble(data.root)}
          <div className="chat-thread-replies" role="separator">{t("chat.messagePane.threadCount", {n: data.items.length})}</div>
          {data.items.map(item => bubble(item.message))}
        </>}
        {!data && !isError && <p role="status">{t("common.loading")}</p>}
        {isError && <button className="tasks-button" onClick={() => void refetch()}>{t("chat.messagePane.threadRetry")}</button>}
      </div>
    </div>
    {error && <p role="alert" className="tasks-notice">{error}</p>}
    {canWrite && data && <form className="chat-pane-composer" onSubmit={event => { event.preventDefault(); void send(); }}>
      {replyTo && <div className="chat-composer-reply"><div><strong>{t("chat.messagePane.reply")} {replyTo.sender.display_name ?? replyTo.sender.id}</strong>
        <span>{renderQuote({message_id: replyTo.id, sender: replyTo.sender, content: replyTo.content, attachments: replyTo.attachments})}</span></div>
        <button type="button" aria-label={t("common.cancel")} onClick={() => setReplyTo(undefined)}>×</button></div>}
      <AttachmentDropzone className="chat-pane-composer-dropzone" onAdd={addFiles} disabled={sending}>
        <div className="chat-composer-input">
        {uploads.length > 0 && <div className="chat-pane-composer-chips">
          {uploads.map(item => <ComposerAttachmentCard key={item.id} item={item} busy={sending} retryClock={retryClock}
            onRemove={() => setUploads(current => current.filter(file => file.id !== item.id))} onRetry={() => void upload(item)} />)}
        </div>}
        <div className="chat-pane-composer-row">
        <input ref={fileInput} type="file" hidden multiple onChange={event => {
          addFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}/>
        <button type="button" className="chat-message-action" disabled={sending} aria-label={t("chat.messagePane.threadAttach")}
          onClick={() => fileInput.current?.click()}><Paperclip size={18}/></button>
        {mentionMatch && <MentionPicker candidates={mentionCandidates} query={mentionMatch[1]} onClose={() => setDraft(draft.replace(MENTION_RE, ""))}
          onSelect={candidate => {
            const label = "@" + candidate.display_name;
            setDraft(draft.slice(0, mentionMatch.index) + label + " ");
            setMentions([...mentions, {label, type: "user", target_id: candidate.user_id}]);
            inputRef.current?.focus();
          }}/>}
        <div className="chat-composer-highlight-wrapper"><textarea ref={inputRef} className="chat-pane-composer-input" rows={2}
          value={draft} disabled={sending} placeholder={t("chat.messagePane.threadPlaceholder")} aria-label={t("chat.messagePane.threadTitle")}
          onPaste={event => {
            const files = pastedImages(event.clipboardData);
            if (files.length) { event.preventDefault(); addFiles(files); }
          }}
          onChange={event => setDraft(event.target.value)} onKeyDown={event => {
            if (event.key === "Enter" && !isMobile && !mentionMatch && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void send();
            }
          }}/></div>
        <button type="submit" className="chat-pane-composer-send" disabled={sending || !uploadsReady || (!draft.trim() && !uploads.length)} aria-label={t("chat.messagePane.send", "Send")}>
          <ArrowUp size={18}/></button>
      </div></div></AttachmentDropzone>
    </form>}
  </aside>;
}
