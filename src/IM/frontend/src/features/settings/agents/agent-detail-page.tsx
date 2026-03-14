import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { createDirectConversation } from "../../chat/chat-api";
import { AgentConfig, getAgentConfig, listNodes, updateAgentConfig } from "./im-agent-config-api";

type AgentConfigFormState = AgentConfig & {
  workspace_root_input: string;
};

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeText(value: string) {
  return value.trim();
}

function toFormState(config: AgentConfig): AgentConfigFormState {
  return {
    ...config,
    workspace_root_input: config.workspace_is_default ? "" : config.workspace_root
  };
}

function normalizeAgentConfig(config: AgentConfigFormState): AgentConfigFormState {
  return {
    ...config,
    display_name: normalizeText(config.display_name),
    description: normalizeText(config.description),
    system_prompt: config.system_prompt.trim(),
    skills: splitList(config.skills.join(",")),
    tool_allowlist: splitList(config.tool_allowlist.join(",")),
    default_model: normalizeText(config.default_model ?? "") || null,
    workspace_root_input: config.workspace_root_input.trim(),
    bound_nodes: config.bound_nodes ?? []
  };
}

function validateDraft(draft: AgentConfigFormState) {
  const errors: Partial<Record<"display_name" | "system_prompt" | "workspace_root_input", string>> = {};

  if (!draft.display_name) {
    errors.display_name = "Display name is required.";
  }

  if (!draft.system_prompt) {
    errors.system_prompt = "System prompt is required.";
  }

  if (draft.workspace_root_input && !draft.workspace_root_input.startsWith("/") && !draft.workspace_root_input.startsWith("~/")) {
    errors.workspace_root_input = "Workspace path must be absolute or start with ~/.";
  }

  return errors;
}

function policyDescription(policy: AgentConfig["group_reply_policy"]) {
  switch (policy) {
    case "ALWAYS":
      return "Reply to every group message for high-touch concierge or assistant roles.";
    case "NO_REPLY":
      return "Stay silent in groups and only work through direct or routed interactions.";
    case "MENTION":
    default:
      return "Reply only when explicitly mentioned. Recommended for most shared channels.";
  }
}

function nodeStatusClasses(status: string) {
  switch (status.toLowerCase()) {
    case "online":
      return "bg-emerald-100 text-emerald-700";
    case "degraded":
      return "bg-amber-100 text-amber-700";
    default:
      return "bg-slate-200 text-slate-600";
  }
}

function formatUpdatedAt(value?: string | null) {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

export function AgentDetailPage() {
  const { agentId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AgentConfigFormState | null>(null);
  const [saved, setSaved] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasAttemptedSave, setHasAttemptedSave] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const query = useQuery({
    queryKey: ["settings", "agents", agentId],
    queryFn: () => getAgentConfig(agentId),
    staleTime: 30_000
  });
  const nodesQuery = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });

  useEffect(() => {
    if (query.data) {
      setDraft(toFormState(query.data));
      setErrorMessage(null);
    }
  }, [query.data]);

  const normalizedDraft = useMemo(() => (draft ? normalizeAgentConfig(draft) : null), [draft]);
  const normalizedServerState = useMemo(() => (query.data ? normalizeAgentConfig(toFormState(query.data)) : null), [query.data]);
  const validationErrors = useMemo(() => (normalizedDraft ? validateDraft(normalizedDraft) : {}), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const isDirty = normalizedDraft && normalizedServerState ? JSON.stringify(normalizedDraft) !== JSON.stringify(normalizedServerState) : false;
  const queryErrorDetail =
    query.error instanceof Error ? query.error.message.split(" failed: ").at(-1) ?? query.error.message : "Unable to load this agent.";
  const nodeErrorDetail =
    nodesQuery.error instanceof Error ? nodesQuery.error.message.split(" failed: ").at(-1) ?? nodesQuery.error.message : "Unable to load node status.";

  const mutation = useMutation({
    mutationFn: (next: AgentConfigFormState) => {
      const { workspace_root_input, workspace_is_default: _workspaceIsDefault, bound_nodes: _boundNodes, updated_at: _updatedAt, owner_id: _ownerId, agent_id: _agentId, workspace_root: _workspaceRoot, ...payload } = next;
      return updateAgentConfig(agentId, {
        ...payload,
        workspace_root: workspace_root_input || null
      });
    },
    onSuccess: async (updated) => {
      setErrorMessage(null);
      setSaved(true);
      setHasAttemptedSave(false);
      if (updated) {
        setDraft(toFormState(updated));
      }
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents", agentId] });
      setTimeout(() => setSaved(false), 1600);
    },
    onError: (error) => {
      setSaved(false);
      setErrorMessage(error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Save failed");
    }
  });
  const openDirectChatMutation = useMutation({
    mutationFn: () => createDirectConversation({ agentId }),
    onSuccess: async ({ conversation_id }) => {
      setErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      navigate(`/chat/${conversation_id}`);
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Open direct chat failed");
    }
  });

  function markTouched(field: "display_name" | "system_prompt" | "workspace_root_input") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "display_name" | "system_prompt" | "workspace_root_input") {
    return (hasAttemptedSave || touched[field]) && validationErrors[field];
  }

  if (query.isLoading && !draft) {
    return <p className="text-sm text-slate-500">Loading agent profile...</p>;
  }

  if (query.isError && !draft) {
    return (
      <section className="grid gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">Could not load this agent.</p>
          <p className="text-sm text-rose-600">{queryErrorDetail}</p>
        </div>
        <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void query.refetch()}>
          Retry
        </button>
      </section>
    );
  }

  if (!draft || !normalizedDraft) {
    return <p className="text-sm text-slate-500">Loading agent profile...</p>;
  }

  const liveNodes = nodesQuery.data ?? [];
  const liveNodeLookup = new Map(liveNodes.map((node) => [node.node_id, node]));
  const boundNodes = (draft.bound_nodes ?? []).map((nodeId) => liveNodeLookup.get(nodeId) ?? { node_id: nodeId, node_name: nodeId, status: "unknown", last_heartbeat_at: "", agent_count: 0, version: "" });

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        setHasAttemptedSave(true);
        setErrorMessage(null);

        if (hasValidationErrors || !isDirty || !normalizedDraft) {
          return;
        }

        mutation.mutate(normalizedDraft);
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="im-title text-xl font-bold">Agent Detail</h2>
          <p className="text-sm text-slate-500">Make safe prompt and routing updates with explicit save feedback before operators rely on them.</p>
        </div>
        <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{draft.agent_id}</div>
      </div>

      <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <div className="grid gap-4">
          <div className="grid gap-1 md:grid-cols-2 md:gap-3">
            <div className="grid gap-1">
              <Label.Root htmlFor="agent-id">Agent ID</Label.Root>
              <input id="agent-id" className="im-input bg-slate-50 text-slate-500" value={draft.agent_id} disabled />
            </div>
            <div className="grid gap-1">
              <Label.Root htmlFor="owner-id">Owner</Label.Root>
              <input id="owner-id" className="im-input bg-slate-50 text-slate-500" value={draft.owner_id || "—"} disabled />
            </div>
          </div>

          <section id="workspace-settings" className="grid gap-3 rounded-2xl border border-[var(--im-border)] bg-slate-50/80 p-4">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Current workspace</p>
              <p className="break-all font-mono text-sm text-slate-900">{draft.workspace_root}</p>
              <p className="text-xs text-slate-500">
                {draft.workspace_is_default
                  ? "Read-only runtime path. This agent is currently using the managed default workspace."
                  : "Read-only runtime path. This agent is currently using a custom workspace override."}
              </p>
            </div>

            <div className="grid gap-1">
              <Label.Root htmlFor="workspace-root">Workspace Path Setting</Label.Root>
              <input
                id="workspace-root"
                className="im-input"
                value={draft.workspace_root_input}
                aria-invalid={Boolean(shouldShowError("workspace_root_input"))}
                aria-describedby="workspace-root-help"
                placeholder="Leave blank to use the managed default workspace"
                onBlur={() => markTouched("workspace_root_input")}
                onChange={(event) => {
                  setSaved(false);
                  setErrorMessage(null);
                  setDraft({ ...draft, workspace_root_input: event.target.value });
                }}
              />
              <p id="workspace-root-help" className="text-xs text-slate-500">
                Editable setting. Enter an absolute path or `~/...`. Leave blank to keep the managed default path for this agent.
              </p>
              {shouldShowError("workspace_root_input") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.workspace_root_input}</p> : null}
            </div>
          </section>

          <div className="grid gap-1">
            <Label.Root htmlFor="display-name">Display Name</Label.Root>
            <input
              id="display-name"
              className="im-input"
              value={draft.display_name}
              aria-invalid={Boolean(shouldShowError("display_name"))}
              aria-describedby="display-name-help"
              onBlur={() => markTouched("display_name")}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, display_name: event.target.value });
              }}
            />
            <p id="display-name-help" className="text-xs text-slate-500">
              Use a clear operator-facing name so reviewers can identify this profile from the list instantly.
            </p>
            {shouldShowError("display_name") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.display_name}</p> : null}
          </div>

          <div className="grid gap-1">
            <Label.Root htmlFor="description">Description</Label.Root>
            <input
              id="description"
              className="im-input"
              value={draft.description ?? ""}
              aria-describedby="description-help"
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, description: event.target.value });
              }}
            />
            <p id="description-help" className="text-xs text-slate-500">
              Keep this short and outcome-oriented so product reviewers can confirm the business purpose quickly.
            </p>
          </div>

          <div className="grid gap-1">
            <Label.Root htmlFor="system-prompt">System Prompt</Label.Root>
            <textarea
              id="system-prompt"
              className="im-input min-h-32"
              value={draft.system_prompt}
              aria-invalid={Boolean(shouldShowError("system_prompt"))}
              aria-describedby="system-prompt-help"
              onBlur={() => markTouched("system_prompt")}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, system_prompt: event.target.value });
              }}
            />
            <p id="system-prompt-help" className="text-xs text-slate-500">
              Treat this as the runtime contract. Small changes here can materially alter behavior.
            </p>
            {shouldShowError("system_prompt") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.system_prompt}</p> : null}
          </div>

          <div className="grid gap-1 md:grid-cols-2 md:gap-3">
            <div className="grid gap-1">
              <Label.Root htmlFor="skills-allowlist">Skills Allowlist</Label.Root>
              <input
                id="skills-allowlist"
                className="im-input"
                value={draft.skills.join(", ")}
                aria-describedby="skills-help"
                onChange={(event) => {
                  setSaved(false);
                  setErrorMessage(null);
                  setDraft({ ...draft, skills: splitList(event.target.value) });
                }}
              />
              <p id="skills-help" className="text-xs text-slate-500">Comma-separated skills exposed to this agent.</p>
            </div>
            <div className="grid gap-1">
              <Label.Root htmlFor="tool-allowlist">Tool Allowlist</Label.Root>
              <input
                id="tool-allowlist"
                className="im-input"
                value={draft.tool_allowlist.join(", ")}
                aria-describedby="tools-help"
                onChange={(event) => {
                  setSaved(false);
                  setErrorMessage(null);
                  setDraft({ ...draft, tool_allowlist: splitList(event.target.value) });
                }}
              />
              <p id="tools-help" className="text-xs text-slate-500">Comma-separated tools approved for this agent.</p>
            </div>
          </div>

          <div className="grid gap-1 md:grid-cols-2 md:gap-3">
            <div className="grid gap-1">
              <Label.Root htmlFor="group-reply-policy">Group Reply Policy</Label.Root>
              <select
                id="group-reply-policy"
                className="im-input"
                aria-describedby="group-policy-help"
                value={draft.group_reply_policy}
                onChange={(event) => {
                  setSaved(false);
                  setErrorMessage(null);
                  setDraft({ ...draft, group_reply_policy: event.target.value as AgentConfig["group_reply_policy"] });
                }}
              >
                <option value="ALWAYS">ALWAYS</option>
                <option value="MENTION">MENTION</option>
                <option value="NO_REPLY">NO_REPLY</option>
              </select>
              <p id="group-policy-help" className="text-xs text-slate-500">
                {policyDescription(draft.group_reply_policy)}
              </p>
            </div>
            <div className="grid gap-1">
              <Label.Root htmlFor="default-model">Default Model</Label.Root>
              <input
                id="default-model"
                className="im-input"
                value={draft.default_model ?? ""}
                aria-describedby="default-model-help"
                onChange={(event) => {
                  setSaved(false);
                  setErrorMessage(null);
                  setDraft({ ...draft, default_model: event.target.value });
                }}
              />
              <p id="default-model-help" className="text-xs text-slate-500">
                Leave blank to inherit the platform default, or pin a known-good model for this profile.
              </p>
            </div>
          </div>
        </div>

        <aside className="grid gap-3 rounded-2xl border border-[var(--im-border)] bg-white/75 p-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Live status</p>
            <p className="text-sm text-slate-600">Keep an eye on versioning, last update time, and node placement while editing behavior.</p>
          </div>

          <dl className="grid gap-2 text-sm text-slate-600">
            <div className="flex items-center justify-between gap-3">
              <dt>Profile Version</dt>
              <dd className="font-semibold text-slate-900">{draft.profile_version}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt>Updated</dt>
              <dd className="text-right text-slate-900">{formatUpdatedAt(draft.updated_at)}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt>Bound Nodes</dt>
              <dd className="font-semibold text-slate-900">{draft.bound_nodes?.length ?? 0}</dd>
            </div>
          </dl>

          {nodesQuery.isLoading ? <p className="text-xs text-slate-500">Loading live node status...</p> : null}
          {nodesQuery.isError ? <p className="text-xs font-semibold text-amber-700">Live node status unavailable: {nodeErrorDetail}</p> : null}

          {boundNodes.length > 0 ? (
            <div className="grid gap-2">
              {boundNodes.map((node) => (
                <section key={node.node_id} className="rounded-xl border border-[var(--im-border)] bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{node.node_name}</p>
                      <p className="text-xs text-slate-500">{node.node_id}</p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${nodeStatusClasses(node.status)}`}>{node.status}</span>
                  </div>
                  <dl className="mt-2 grid gap-1 text-xs text-slate-600">
                    <div className="flex items-center justify-between gap-3">
                      <dt>Assigned agents</dt>
                      <dd>{node.agent_count}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt>Last heartbeat</dt>
                      <dd>{node.last_heartbeat_at || "—"}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt>Runtime version</dt>
                      <dd>{node.version || "—"}</dd>
                    </div>
                  </dl>
                </section>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">This agent is currently unbound. Save behavior changes first, then assign runtime capacity when ready.</p>
          )}
        </aside>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--im-border)] pt-3">
        <div aria-live="polite" className="space-y-1 text-xs">
          <p className="text-slate-500">Profile Version: {draft.profile_version}</p>
          {hasAttemptedSave && hasValidationErrors ? <p className="font-semibold text-rose-700">Fix the required fields before saving.</p> : null}
          {errorMessage ? <p className="font-semibold text-rose-700">{errorMessage}</p> : null}
          {!errorMessage && mutation.isPending ? <p className="font-semibold text-sky-700">Saving changes...</p> : null}
          {!errorMessage && !mutation.isPending && isDirty ? <p className="font-semibold text-amber-700">Unsaved changes</p> : null}
          {!errorMessage && saved ? <p className="font-semibold text-emerald-700">Saved</p> : null}
          {!errorMessage && !mutation.isPending && !isDirty && !saved ? <p className="text-slate-500">All changes saved.</p> : null}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            className="im-btn im-btn-muted w-fit"
            type="button"
            disabled={openDirectChatMutation.isPending}
            onClick={() => openDirectChatMutation.mutate()}
          >
            {openDirectChatMutation.isPending ? "Opening direct chat…" : "Open direct chat"}
          </button>
          <button className="im-btn im-btn-primary w-fit" type="submit" disabled={mutation.isPending || !isDirty}>
            {mutation.isPending ? "Saving…" : isDirty ? "Save Agent" : "No Changes to Save"}
          </button>
        </div>
      </div>
    </form>
  );
}
