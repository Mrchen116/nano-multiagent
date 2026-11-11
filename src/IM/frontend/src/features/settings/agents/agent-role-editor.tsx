import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "../../../i18n";
import { AgentConfigRequestError, getAgentRole, saveAgentRole, type AgentRoleDocument } from "./im-agent-config-api";

const roleLimit = 2000;

export function useAgentRoleEditor(agentId: string, online: boolean) {
  const client = useQueryClient();
  const queryKey = ["settings", "agents", agentId, "role"];
  const [draft, setDraft] = useState<AgentRoleDocument | null>(null);
  const [message, setMessage] = useState<"saved" | "conflict" | "unconfirmed" | "tooLong" | null>(null);
  const role = useQuery({
    queryKey,
    queryFn: ({ signal }) => getAgentRole(agentId, signal),
    enabled: online,
    retry: false,
    gcTime: 0,
  });
  const save = useMutation({
    mutationFn: (document: AgentRoleDocument) => saveAgentRole(agentId, document),
    onSuccess: async saved => {
      await client.cancelQueries({ queryKey, exact: true });
      client.setQueryData(queryKey, saved);
      setDraft(null);
      setMessage("saved");
    },
    onError: async error => {
      if (error instanceof AgentConfigRequestError && error.code === "role_too_long") {
        setMessage("tooLong");
        return;
      }
      setMessage(error instanceof AgentConfigRequestError && error.code === "role_conflict" ? "conflict" : "unconfirmed");
      if (online) await role.refetch();
    },
  });
  const current = role.data;
  const content = draft?.content ?? current?.content ?? "";
  const dirty = draft !== null && draft.content !== current?.content;
  const available = online && current !== undefined && role.isSuccess && role.isFetchedAfterMount && !role.isFetching && !save.isPending;
  const changed = dirty && current !== undefined && draft.version !== current.version;
  return {
    current, content, dirty, message, changed, available,
    loading: role.isFetching,
    saving: save.isPending,
    denied: role.error instanceof AgentConfigRequestError && [401, 403, 404].includes(role.error.status),
    tooLong: content.length > roleLimit,
    reload: () => { if (online) void role.refetch(); },
    canReload: online && !role.isFetching && !save.isPending,
    edit(next: string) {
      if (!available) return;
      setDraft(next === current.content ? null : {content: next, version: draft ? draft.version : current.version});
      if (next === current.content || message === "saved" || message === "tooLong") setMessage(null);
    },
    discard() { setDraft(null); setMessage(null); },
    async save() {
      if (!available || !dirty || content.length > roleLimit) return;
      setMessage(null);
      await save.mutateAsync({content, version: current.version});
    },
  };
}

export function AgentRoleEditor({editor}: {editor: ReturnType<typeof useAgentRoleEditor>}) {
  const { t } = useTranslation();
  const id = useId();
  const label = (key: string) => t(`agents.form.behavior.roleAgreement.${key}`);
  if (editor.denied) return null;
  return (
    <div className="im-agent-field">
      <label htmlFor={id}>{label("title")}</label>
      <p id={`${id}-help`} className="im-agent-field-help">{label("help")}</p>
      {editor.current !== undefined && <>
        {editor.current.content === "" && !editor.dirty && <p className="im-agent-field-help">{label("unset")}</p>}
        <textarea
          id={id}
          className="im-agent-textarea"
          rows={4}
          value={editor.content}
          aria-describedby={`${id}-help`}
          aria-invalid={editor.tooLong}
          disabled={!editor.available}
          onChange={event => editor.edit(event.target.value)}
        />
      </>}
      {!editor.available && !editor.saving && <p className="im-agent-field-help" role="status">{label(editor.loading ? "loading" : "unavailable")}</p>}
      {!editor.available && editor.canReload && <div>
        <button type="button" className="im-settings-action" onClick={editor.reload}>{t("agents.settings.retry")}</button>
      </div>}
      {(editor.message || editor.changed || editor.tooLong) && <p className="im-agent-field-help" role="status">
        {label(editor.tooLong ? "tooLong" : editor.message ?? "conflict")}
      </p>}
      {editor.current && editor.dirty && (!editor.available || editor.changed || editor.message === "conflict" || editor.message === "unconfirmed") && <div>
        <p className="im-agent-field-help">{label(editor.available ? "latest" : "lastRead")}</p>
        <p className="im-agent-field-help whitespace-pre-wrap break-words">{editor.current.content || label("unset")}</p>
      </div>}
    </div>
  );
}
