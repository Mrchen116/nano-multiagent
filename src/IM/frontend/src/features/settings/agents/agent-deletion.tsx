import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { authFetchJson } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";

interface Workspace { path: string; witness: string }
interface DeletionOperation {
  operation_id: string;
  state: "waiting_node" | "deleting" | "failed" | "deleted";
  error_detail?: string;
  delete_workspace: boolean;
}
interface DeletionView {
  agent_id: string;
  eligible: boolean;
  reason?: string;
  revision: number;
  profile_version: number;
  workspace?: Workspace;
  operation?: DeletionOperation;
}
interface DeleteRequest {
  request_id: string;
  expected_revision: number;
  expected_profile_version: number;
  workspace_witness?: string;
}
const path = (id: string) => `/im/v1/agents/${encodeURIComponent(id)}/deletion`;

export function useAgentDeletion(agentId: string, enabled: boolean) {
  const self = useAuthStore(s => s.user?.id);
  const client = useQueryClient();
  const queryKey = ["agent-deletion", self, agentId];
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => authFetchJson<DeletionView>(path(agentId), { signal }, "Agent deletion"),
    enabled: enabled && !!agentId,
    refetchInterval: query => query.state.data?.operation?.state === "deleted" ? false : 3000,
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: async (request: DeleteRequest | { operation_id: string }) => authFetchJson<DeletionView>(
      path(agentId) + ("operation_id" in request ? "/retry" : ""),
      { method: "POST", body: JSON.stringify(request) },
      "Agent deletion",
    ),
    onSuccess: async result => {
      await client.cancelQueries({ queryKey });
      client.setQueryData(queryKey, result);
    },
    onError: () => { void client.invalidateQueries({ queryKey }); },
  });
  return { query, mutation };
}

type Deletion = ReturnType<typeof useAgentDeletion>;

export function AgentDeletionControls({ deletion, name, online, active = true }: {
  deletion: Deletion;
  name: string;
  online: boolean;
  active?: boolean;
}) {
  const { i18n } = useTranslation();
  const l = (zh: string, en: string) => i18n.language.startsWith("zh") ? zh : en;
  const navigate = useNavigate();
  const client = useQueryClient();
  const isMobile = useIsMobile();
  const [confirmation, setConfirmation] = useState<DeletionView | null>(null);
  const [deleteWorkspace, setDeleteWorkspace] = useState(false);
  const [requestId, setRequestId] = useState("");
  const view = deletion.query.data;
  const operation = view?.operation;
  const mutation = deletion.mutation;
  const done = operation?.state === "deleted";

  useEffect(() => {
    if (!active || !done) return;
    navigate("/settings/agents", { replace: true });
    for (const key of [["settings", "agents"], ["contacts"], ["public-agents"], ["chat", "agents"], ["chat", "conversations"], ["agent-work", view!.agent_id]]) {
      void client.invalidateQueries({ queryKey: key });
    }
  }, [active, done, navigate, client, view?.agent_id]);

  if (!active || !view) return null;
  if (!operation && !view.eligible && !confirmation) {
    const reason = view.reason === "node_offline" ? l("节点重新在线后可永久删除。", "Permanent deletion is available when the device comes online.")
      : view.reason === "node_upgrade_required" ? l("升级节点后可永久删除。", "Update the device to enable permanent deletion.")
      : view.reason === "stop_not_confirmed" ? l("确认停止后可永久删除。", "Permanent deletion is available once the stop is confirmed.")
      : l("当前无法永久删除此 Agent。", "This Agent cannot be permanently deleted right now.");
    return <p className="im-agent-field-help" role="status">{reason}</p>;
  }
  const scopeCurrent = !!confirmation && view.eligible && view.revision === confirmation.revision
    && view.profile_version === confirmation.profile_version
    && (!deleteWorkspace || view.workspace?.witness === confirmation.workspace?.witness);
  const canConfirm = scopeCurrent && online && !deletion.query.isError && !mutation.isPending;
  const submit = () => {
    if (!confirmation || !canConfirm) return;
    mutation.mutate({
      request_id: requestId,
      expected_revision: confirmation.revision,
      expected_profile_version: confirmation.profile_version,
      ...(deleteWorkspace && confirmation.workspace ? { workspace_witness: confirmation.workspace.witness } : {}),
    }, { onSuccess: () => setConfirmation(null) });
  };

  return <div className="im-agent-lifecycle-status" aria-live="polite">
    {operation ? <>
      <strong>{operation.state === "waiting_node" ? l("等待节点恢复", "Waiting for the device") :
        operation.state === "failed" ? l("清理失败", "Cleanup failed") :
        done ? l("已删除", "Deleted") : l("正在永久删除…", "Deleting permanently…")}</strong>
      {operation.error_detail && <span>{operation.error_detail}</span>}
      {operation.state === "failed" && <button type="button" className="im-settings-action" disabled={!online || mutation.isPending}
        onClick={() => mutation.mutate({ operation_id: operation.operation_id })}>{l("重试清理", "Retry cleanup")}</button>}
      {mutation.isError && <span role="alert">{mutation.error.message}</span>}
    </> : <Dialog.Root open={!!confirmation} onOpenChange={open => {
      if (open) { mutation.reset(); setDeleteWorkspace(false); setRequestId(crypto.randomUUID()); setConfirmation(view); }
      else if (!mutation.isPending) setConfirmation(null);
    }}>
      <Dialog.Trigger asChild>
        <button type="button" className="im-settings-action danger" disabled={!online || deletion.query.isError}>{l("永久删除 Agent", "Permanently delete Agent")}</button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className={isMobile ? "chat-modal-bottom-sheet" : "chat-modal-backdrop"}>
          <Dialog.Content className="chat-modal" onEscapeKeyDown={event => { if (mutation.isPending) event.preventDefault(); }}
            onPointerDownOutside={event => { if (mutation.isPending) event.preventDefault(); }}>
            <header className="chat-modal-header"><Dialog.Title>{l("永久删除", "Permanently delete")} {name}</Dialog.Title></header>
            <div className="chat-modal-body">
              <Dialog.Description>{l("此操作会永久清理该 Agent 的执行会话、子会话和工作记录。聊天正文、附件和发送者身份会保留。", "This permanently removes this Agent’s execution sessions, child sessions, and work records. Chat messages, attachments, and sender identity are kept.")}</Dialog.Description>
              {confirmation?.workspace && <label className="block">
                <input type="checkbox" checked={deleteWorkspace} disabled={mutation.isPending} onChange={e => setDeleteWorkspace(e.target.checked)} />
                {" "}{l("同时删除专用工作区", "Also delete the dedicated workspace")}
                <span className="block break-all">{confirmation.workspace.path}</span>
              </label>}
              {confirmation && !confirmation.workspace && <p>{l("工作区文件会保留。", "Workspace files are kept.")}</p>}
              {confirmation && !scopeCurrent && <p role="alert">{l("删除范围已变化，请关闭后重新确认。", "The deletion scope changed. Close and review it again.")}</p>}
              {!online && <p role="status">{l("等待设备重新在线。", "Waiting for the device to come online.")}</p>}
              {mutation.isError && <p role="alert">{mutation.error.message}</p>}
            </div>
            <footer className="chat-modal-footer">
              <Dialog.Close asChild><button type="button" className="chat-modal-btn-ghost" disabled={mutation.isPending}>{l("取消", "Cancel")}</button></Dialog.Close>
              <button type="button" className="chat-modal-btn-primary" disabled={!canConfirm} onClick={submit}>{mutation.isPending ? l("提交中…", "Submitting…") : l("确认永久删除", "Confirm permanent deletion")}</button>
            </footer>
          </Dialog.Content>
        </Dialog.Overlay>
      </Dialog.Portal>
    </Dialog.Root>}
  </div>;
}
