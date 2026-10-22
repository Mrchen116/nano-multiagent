import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "../../i18n";
import { authFetchJson } from "../auth/auth-fetch";
import { listConversations } from "../chat/chat-api";
import type { Conversation } from "../chat/chat-types";
import { getTaskGraph, TaskGraphReadError, writeTaskGraph, type TaskGraph, type TaskMode, type TaskNode, type TaskStatus } from "./task-graphs-api";
import { actorName, editableTaskStatuses } from "./task-progress";

export type TaskEditTarget = { graph?: TaskGraph; node?: TaskNode; parent?: TaskNode; conversationId?: string; claim?: boolean };
export function TaskEditor({ target, onClose, onSaved }: { target: TaskEditTarget; onClose(): void; onSaved(graphId: string): void }) {
  const { t } = useTranslation();
  const { graph, node, parent } = target;
  const [title, setTitle] = useState(node?.title ?? "");
  const [description, setDescription] = useState(node?.description ?? "");
  const [result, setResult] = useState(node?.result ?? "");
  const [status, setStatus] = useState<TaskStatus>(target.claim ? "doing" : node?.status ?? "todo");
  const [mode, setMode] = useState<TaskMode>(node?.mode ?? (parent ? "none" : "dag"));
  const [assignee, setAssignee] = useState(node?.assignee ? `${node.assignee.type}:${node.assignee.id}` : "");
  const [conversationId, setConversationId] = useState(graph?.conversation?.id ?? target.conversationId ?? "");
  const [note, setNote] = useState("");
  const [revision, setRevision] = useState(graph?.revision);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<TaskNode | null>(null);
  const conversations = useQuery({ queryKey: ["task-write-conversations"], queryFn: listConversations, enabled: !graph });
  const members = useQuery({ queryKey: ["task-conversation", conversationId], queryFn: () => authFetchJson<Conversation>(`/im/v1/conversations/${encodeURIComponent(conversationId)}`), enabled: Boolean(conversationId) });
  const candidates = members.data?.participants.filter(actor => actor.type !== "system" && !actor.is_stale) ?? [];
  const writable = conversations.data?.filter(chat => chat.can_write && !chat.dissolved_at) ?? [];
  const heading = t(node ? "tasks.edit" : parent ? "tasks.createChild" : "tasks.createRoot");
  async function readLatest() {
    setBusy(true);
    try {
      const fresh = await getTaskGraph(graph!.graph_id);
      const current = fresh?.nodes.find(item => item.id === (node ?? parent)?.id);
      if (!fresh || !current) { setError(t("tasks.unavailable")); return; }
      if (!current.can_edit) { setError(t("tasks.readOnly")); return; }
      setLatest(current); setRevision(fresh.revision); setConflict(false); setRequestKey(crypto.randomUUID());
    } catch (err) { setError(err instanceof Error ? err.message : t("tasks.readFailed")); }
    finally { setBusy(false); }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || !conversationId || conflict) return;
    if ((latest ?? node)?.status === "done" && status === "doing" && !note.trim()) { setError(t("tasks.reworkRequired")); return; }
    setBusy(true); setError("");
    const [type, id] = assignee.split(":");
    const owner = assignee ? { type, id } : null;
    try {
      let saved;
      if (!graph) saved = await writeTaskGraph("", { title: title.trim(), description, result, status, mode, conversation_id: conversationId, assignee: owner, request_key: requestKey });
      else {
        const operations: Record<string, unknown>[] = [];
        if (node) {
          operations.push({ op: "update_task", node_id: node.id, patch: { title: title.trim(), description, result, status } });
          const prior = latest ?? node;
          if (target.claim) operations.push({ op: "claim_task", node_id: node.id });
          else if (assignee !== (prior.assignee ? `${prior.assignee.type}:${prior.assignee.id}` : "")) operations.push({ op: "set_assignee", node_id: node.id, assignee: owner });
        } else {
          if ((latest ?? parent)!.mode === "none") operations.push({ op: "update_task", node_id: parent!.id, patch: { mode: "dag" } });
          operations.push({ op: "add_task", client_ref: "new_task", container_id: parent!.id, title: title.trim(), description, result, status, mode, assignee: owner });
        }
        saved = await writeTaskGraph(`/${encodeURIComponent(graph.graph_id)}/apply`, { base_revision: revision, request_key: requestKey, operations, change_note: note });
      }
      onSaved(saved.graph_id ?? graph!.graph_id);
    } catch (err) {
      if (err instanceof TaskGraphReadError && err.status === 409) { setConflict(true); setError(t("tasks.conflict")); }
      else setError(err instanceof Error ? err.message : t("tasks.writeFailed"));
    } finally { setBusy(false); }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose(); }}><Dialog.Portal><Dialog.Overlay className="tasks-dialog-overlay tasks-edit-overlay" /><Dialog.Content className="tasks-edit-dialog" aria-describedby={undefined}>
    <div className="tasks-dialog-heading"><Dialog.Title>{heading}</Dialog.Title><Dialog.Close className="tasks-button" disabled={busy}>{t("tasks.close")}</Dialog.Close></div>
    <form className="tasks-edit-form" onSubmit={save}>
      {!graph ? <label>{t("tasks.conversation")}<select required value={conversationId} onChange={e => { setConversationId(e.target.value); setAssignee(""); }}><option value="">{t("tasks.chooseConversation")}</option>{writable.map(chat => <option value={chat.id} key={chat.id}>{chat.title}</option>)}</select></label> : <p>{t("tasks.conversation")}: {graph.conversation?.title}</p>}
      <label>{t("tasks.title")}<input autoFocus required value={title} onChange={e => setTitle(e.target.value)} /></label>
      <label>{t("tasks.description")}<textarea value={description} onChange={e => setDescription(e.target.value)} /></label><><label>{t("tasks.statusLabel")}<select value={status} onChange={e => setStatus(e.target.value as TaskStatus)}>{editableTaskStatuses((latest ?? node)?.status).map(value => <option value={value} key={value}>{t(`tasks.status.${value}`)}</option>)}</select></label><label>{t("tasks.result")}<textarea value={result} onChange={e => setResult(e.target.value)} /></label></>
      {!node && <label>{t("tasks.structure")}<select value={mode} onChange={e => setMode(e.target.value as TaskMode)}>{(parent ? ["none", "dag", "explore"] : ["dag", "explore"]).map(value => <option value={value} key={value}>{t(`tasks.mode.${value}`)}</option>)}</select></label>}
      {!target.claim && <label>{t("tasks.assignee")}<select value={assignee} onChange={e => setAssignee(e.target.value)}><option value="">{t("tasks.unassigned")}</option>{node?.assignee && assignee === `${node.assignee.type}:${node.assignee.id}` && !candidates.some(actor => `${actor.type}:${actor.id}` === assignee) && <option value={assignee}>{actorName(node.assignee)}</option>}{candidates.map(actor => <option key={`${actor.type}:${actor.id}`} value={`${actor.type}:${actor.id}`}>{actor.display_name ?? actor.id}</option>)}</select></label>}
      <p className="tasks-detail-note">{t("tasks.membersOnly")}</p>
      {graph && <label>{t("tasks.changeNote")}<input value={note} onChange={e => setNote(e.target.value)} placeholder={t("tasks.reworkRequired")} /></label>}
      {members.isError && <p role="alert">{t("tasks.readFailed")}</p>}
      {error && <p className="tasks-notice" role="alert">{error}</p>}
      {conflict && <button className="tasks-button" type="button" disabled={busy} onClick={() => void readLatest()}>{t("tasks.readLatest")}</button>}
      {latest && <section className="tasks-conflict"><h3>{t("tasks.latestRecord")}</h3><p>{latest.title} · {t(`tasks.status.${latest.status}`)} · {actorName(latest.assignee) || t("tasks.unassigned")}</p><p>{latest.description}</p><p>{latest.result}</p><small>{t("tasks.draftKept")}</small></section>}
      <button className="tasks-button tasks-button--primary" disabled={busy || conflict || !conversationId || !title.trim()}>{t(latest ? "tasks.retrySave" : "tasks.save")}</button>
    </form>
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
