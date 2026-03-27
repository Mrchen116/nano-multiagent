import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { createDirectConversation } from "../../chat/chat-api";
import { AllowlistSelector } from "./allowlist-selector";
import { AgentConfig, getAgentDetailState, updateAgentConfig } from "./im-agent-config-api";

type AgentConfigFormState = AgentConfig;

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function normalizeText(value: string) {
  return value.trim();
}

function normalizeAgentConfig(config: AgentConfigFormState): AgentConfigFormState {
  return {
    ...config,
    display_name: normalizeText(config.display_name),
    description: normalizeText(config.description),
    system_prompt: config.system_prompt.trim(),
    skills: normalizeAllowlist(config.skills),
    tool_allowlist: normalizeAllowlist(config.tool_allowlist),
    default_model: normalizeText(config.default_model ?? "") || null
  };
}

function validateDraft(draft: AgentConfigFormState) {
  const errors: Partial<Record<"display_name" | "system_prompt", string>> = {};

  if (!draft.display_name) {
    errors.display_name = "Display name is required.";
  }

  if (!draft.system_prompt) {
    errors.system_prompt = "System prompt is required.";
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

function resolveModelOptions(modelOptions: string[] | undefined, currentModel: string | null) {
  const resolved = Array.from(new Set((modelOptions ?? []).map((value) => value.trim()).filter(Boolean)));
  if (currentModel && !resolved.includes(currentModel)) {
    resolved.unshift(currentModel);
  }
  return resolved;
}

function platformDefaultLabel(model: string | null | undefined) {
  return model ? `Platform default (${model})` : "Platform default";
}

function modelOptionLabel(model: string, platformDefaultModel: string | null | undefined, isAvailable: boolean) {
  if (!isAvailable) {
    return `${model} (unavailable now)`;
  }
  if (model === platformDefaultModel) {
    return `${model} (platform default)`;
  }
  return model;
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

  const detailQuery = useQuery({
    queryKey: ["settings", "agents", agentId, "detail-state"],
    queryFn: () => getAgentDetailState(agentId),
    staleTime: 30_000
  });

  useEffect(() => {
    if (detailQuery.data?.config) {
      setDraft(detailQuery.data.config);
      setErrorMessage(null);
    }
  }, [detailQuery.data]);

  const capabilities = detailQuery.data?.capabilities;
  const owningNode = detailQuery.data?.owningNode ?? null;
  const normalizedDraft = useMemo(() => (draft ? normalizeAgentConfig(draft) : null), [draft]);
  const normalizedServerState = useMemo(() => (detailQuery.data?.config ? normalizeAgentConfig(detailQuery.data.config) : null), [detailQuery.data]);
  const availableModels = useMemo(
    () => resolveModelOptions(capabilities?.model_options, draft?.default_model ?? null),
    [capabilities?.model_options, draft?.default_model]
  );
  const platformDefaultModel = capabilities?.platform_default_model ?? null;
  const validationErrors = useMemo(() => (normalizedDraft ? validateDraft(normalizedDraft) : {}), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const isDirty = normalizedDraft && normalizedServerState ? JSON.stringify(normalizedDraft) !== JSON.stringify(normalizedServerState) : false;
  const queryErrorDetail =
    detailQuery.error instanceof Error ? detailQuery.error.message.split(" failed: ").at(-1) ?? detailQuery.error.message : "Unable to load this agent.";

  const mutation = useMutation({
    mutationFn: (next: AgentConfigFormState) => {
      const { updated_at: _updatedAt, owner_id: _ownerId, agent_id: _agentId, workspace_root: _workspaceRoot, workspace_is_default: _workspaceIsDefault, node_id: _nodeId, node_name: _nodeName, node_status: _nodeStatus, ...payload } = next;
      return updateAgentConfig(agentId, payload);
    },
    onSuccess: async (updated) => {
      setErrorMessage(null);
      setSaved(true);
      setHasAttemptedSave(false);
      if (updated && capabilities) {
        setDraft(updated);
        queryClient.setQueryData(["settings", "agents", agentId, "detail-state"], {
          config: updated,
          capabilities,
          owningNode
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents", agentId, "detail-state"] });
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

  function markTouched(field: "display_name" | "system_prompt") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "display_name" | "system_prompt") {
    return (hasAttemptedSave || touched[field]) && validationErrors[field];
  }

  if (detailQuery.isLoading && !draft) {
    return <p className="text-sm text-slate-500">Loading agent profile...</p>;
  }

  if (detailQuery.isError && !draft) {
    return (
      <section className="grid gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">Could not load this agent.</p>
          <p className="text-sm text-rose-600">{queryErrorDetail}</p>
        </div>
        <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void detailQuery.refetch()}>
          Retry
        </button>
      </section>
    );
  }

  if (!draft || !normalizedDraft || !capabilities) {
    return <p className="text-sm text-slate-500">Loading agent profile...</p>;
  }

  const displayedNodeName = draft.node_name ?? capabilities.node_name ?? owningNode?.node_name ?? draft.node_id ?? capabilities.node_id;
  const displayedNodeId = draft.node_id ?? capabilities.node_id;
  const displayedNodeStatus = draft.node_status ?? capabilities.node_status ?? owningNode?.status ?? "unknown";

  return (
    <form
      className="flex h-full flex-col gap-4"
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
        <div className="max-w-2xl space-y-2">
          <h2 className="im-title text-xl font-bold">Agent settings</h2>
          <p className="text-sm text-slate-500">Review the saved role, access, and runtime details without losing the current profile state.</p>
        </div>
        <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{draft.agent_id}</div>
      </div>

      <div className="grid gap-4">
        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Identity</h3>
            <p className="im-section-copy">Keep the profile name and purpose concise so reviewers can scan this page quickly.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="grid gap-1">
              <Label.Root htmlFor="agent-id">Agent ID</Label.Root>
              <input id="agent-id" className="im-input bg-slate-50 text-slate-500" value={draft.agent_id} disabled />
            </div>
            <div className="grid gap-1">
              <Label.Root htmlFor="owner-id">Owner</Label.Root>
              <input id="owner-id" className="im-input bg-slate-50 text-slate-500" value={draft.owner_id || "—"} disabled />
            </div>
          </div>
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
        </section>

        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Behavior</h3>
            <p className="im-section-copy">Prompt and reply policy are the main behavior levers. Keep the rest of the page out of the way while editing them.</p>
          </div>
          <div className="grid gap-1">
            <Label.Root htmlFor="system-prompt">System Prompt</Label.Root>
            <textarea
              id="system-prompt"
              className="im-input min-h-40"
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
          <div className="grid gap-1 md:max-w-sm">
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
            <p id="group-policy-help" className="text-xs text-slate-500">{policyDescription(draft.group_reply_policy)}</p>
          </div>
        </section>

        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Access & model</h3>
            <p className="im-section-copy">Keep the allowlist minimal and verify whether the saved model still matches the live runtime choices.</p>
          </div>
          <div className="grid gap-3 2xl:grid-cols-2">
            <AllowlistSelector
              id="skills-allowlist"
              label="Skills"
              selected={draft.skills}
              options={capabilities.skills}
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
              helpText="Choose only the reusable skills this agent needs right now. Saved non-standard items stay under review instead of filling the main path."
              emptySelectionText="No skill selected. Leave blank if this agent should inherit platform defaults."
              onChange={(skills) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, skills });
              }}
            />
            <AllowlistSelector
              id="tool-allowlist"
              label="Tools"
              selected={draft.tool_allowlist}
              options={capabilities.tools}
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
              showDescriptions={false}
              helpText="Choose only the tools this agent needs right now. Saved non-standard items stay under review instead of filling the main path."
              emptySelectionText="No tool selected yet. Keep this empty if the agent should inherit platform defaults."
              onChange={(toolAllowlist) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, tool_allowlist: toolAllowlist });
              }}
            />
          </div>
          <div className="grid gap-1 md:max-w-sm">
            <Label.Root htmlFor="default-model">Default Model</Label.Root>
            <select
              id="default-model"
              className="im-input"
              value={draft.default_model ?? ""}
              aria-describedby="default-model-help"
              disabled={detailQuery.isLoading && availableModels.length === 0}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, default_model: event.target.value || null });
              }}
            >
              <option value="">{platformDefaultLabel(platformDefaultModel)}</option>
              {availableModels.map((model) => {
                const isAvailable = (capabilities.model_options ?? []).includes(model);
                return (
                  <option key={model} value={model}>
                    {modelOptionLabel(model, platformDefaultModel, isAvailable)}
                  </option>
                );
              })}
            </select>
            <p id="default-model-help" className="text-xs text-slate-500">
              Choose from the models the current runtime exposes. Leave this on {platformDefaultLabel(platformDefaultModel)} to inherit the platform setting.
            </p>
          </div>
        </section>

        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Workspace</h3>
            <p className="im-section-copy">Workspace is assigned by the owning node and remains read-only in the frontend.</p>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
            <div className="grid gap-4">
              <section id="workspace-settings" className="im-subtle-card grid gap-3">
                <div className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Current workspace</p>
                  <p className="break-all font-mono text-sm text-slate-900">{draft.workspace_root}</p>
                  <p className="text-xs text-slate-500">Read-only runtime path. The owning node assigns and validates this workspace.</p>
                </div>
              </section>

              <dl className="im-subtle-card grid gap-2 text-sm text-slate-600">
                <div className="flex items-center justify-between gap-3">
                  <dt>Profile Version</dt>
                  <dd className="font-semibold text-slate-900">{draft.profile_version}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Updated</dt>
                  <dd className="text-right text-slate-900">{formatUpdatedAt(draft.updated_at)}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Owning Node</dt>
                  <dd className="font-semibold text-slate-900">{displayedNodeId || "—"}</dd>
                </div>
              </dl>
            </div>

            <div className="grid gap-4">
              <section className="im-subtle-card grid gap-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Owning node</p>
                    <p className="text-sm font-semibold text-slate-900">{displayedNodeName}</p>
                    <p className="text-xs text-slate-500">{displayedNodeId}</p>
                  </div>
                  <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${nodeStatusClasses(displayedNodeStatus)}`}>{displayedNodeStatus}</span>
                </div>
                <div className="grid gap-1 text-xs text-slate-600">
                  <div className="flex items-center justify-between gap-3">
                    <dt>Capabilities updated</dt>
                    <dd>{capabilities.capabilities_updated_at ?? "—"}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt>Assigned agents</dt>
                    <dd>{owningNode?.agent_count ?? "—"}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt>Last heartbeat</dt>
                    <dd>{owningNode?.last_heartbeat_at || "—"}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt>Runtime version</dt>
                    <dd>{owningNode?.version || "—"}</dd>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </section>
      </div>

      <div className="rounded-[1.25rem] border border-[var(--im-border)] bg-white/80 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
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
      </div>
    </form>
  );
}
