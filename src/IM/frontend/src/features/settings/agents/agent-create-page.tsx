import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createDirectConversation } from "../../chat/chat-api";
import { AllowlistSelector } from "./allowlist-selector";
import { createAgent, CreateAgentRequest, getAgentAllowlistOptions, listNodes } from "./im-agent-config-api";

type CreateAgentFormState = CreateAgentRequest & {
  workspace_root_input: string;
};

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function normalizeText(value: string) {
  return value.trim();
}

function normalizeDraft(draft: CreateAgentFormState): CreateAgentFormState {
  return {
    ...draft,
    agent_id: normalizeText(draft.agent_id),
    display_name: normalizeText(draft.display_name),
    description: normalizeText(draft.description),
    system_prompt: draft.system_prompt.trim(),
    skills: normalizeAllowlist(draft.skills),
    tool_allowlist: normalizeAllowlist(draft.tool_allowlist),
    default_model: normalizeText(draft.default_model ?? "") || null,
    workspace_root_input: draft.workspace_root_input.trim(),
    node_id: draft.node_id || null
  };
}

function validateDraft(draft: CreateAgentFormState) {
  const errors: Partial<Record<"agent_id" | "display_name" | "system_prompt" | "workspace_root_input", string>> = {};

  if (!draft.agent_id) {
    errors.agent_id = "Agent ID is required.";
  } else if (/\s/.test(draft.agent_id)) {
    errors.agent_id = "Agent ID cannot contain spaces.";
  }

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

function policyDescription(policy: CreateAgentRequest["group_reply_policy"]) {
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

const EMPTY_DRAFT: CreateAgentFormState = {
  agent_id: "",
  owner_id: "",
  display_name: "",
  description: "",
  system_prompt: "",
  skills: [],
  tool_allowlist: [],
  group_reply_policy: "MENTION",
  default_model: null,
  workspace_root_input: "",
  node_id: null
};

export function AgentCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<CreateAgentFormState>(EMPTY_DRAFT);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const nodesQuery = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });
  const allowlistOptionsQuery = useQuery({
    queryKey: ["settings", "agents", "allowlist-options"],
    queryFn: getAgentAllowlistOptions,
    staleTime: 30_000
  });

  useEffect(() => {
    const defaultSystemPrompt = allowlistOptionsQuery.data?.default_system_prompt?.trim() ?? "";
    if (!defaultSystemPrompt) {
      return;
    }
    setDraft((current) => {
      if (current.system_prompt.trim().length > 0) {
        return current;
      }
      return { ...current, system_prompt: defaultSystemPrompt };
    });
  }, [allowlistOptionsQuery.data?.default_system_prompt]);

  const normalizedDraft = useMemo(() => normalizeDraft(draft), [draft]);
  const validationErrors = useMemo(() => validateDraft(normalizedDraft), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const managedWorkspacePreview = useMemo(
    () => `~/nano-assistant/workspace/${normalizedDraft.agent_id || "<agent-id>"}`,
    [normalizedDraft.agent_id]
  );
  const availableModels = useMemo(
    () => resolveModelOptions(allowlistOptionsQuery.data?.model_options, draft.default_model),
    [allowlistOptionsQuery.data?.model_options, draft.default_model]
  );
  const platformDefaultModel = allowlistOptionsQuery.data?.platform_default_model ?? null;
  const nodes = nodesQuery.data ?? [];
  const selectedNode = nodes.find((node) => node.node_id === draft.node_id) ?? null;
  const nodeErrorDetail =
    nodesQuery.error instanceof Error ? nodesQuery.error.message.split(" failed: ").at(-1) ?? nodesQuery.error.message : "Unable to load nodes.";
  const allowlistErrorDetail =
    allowlistOptionsQuery.error instanceof Error
      ? allowlistOptionsQuery.error.message.split(" failed: ").at(-1) ?? allowlistOptionsQuery.error.message
      : "Unable to load selectable skills and tools.";

  const mutation = useMutation({
    mutationFn: (next: CreateAgentFormState) => {
      const { workspace_root_input, ...rest } = next;
      return createAgent({
        ...rest,
        workspace_root: workspace_root_input || null
      });
    },
    onSuccess: async (created) => {
      setErrorMessage(null);
      setCreatedAgentId(created.agent_id);
      queryClient.setQueryData(["settings", "agents", created.agent_id], created);
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "nodes"] });
      await navigate(`/settings/agents/${created.agent_id}`);
    },
    onError: (error) => {
      setCreatedAgentId(null);
      setErrorMessage(error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Create failed");
    }
  });
  const openDirectChatMutation = useMutation({
    mutationFn: (agentId: string) => createDirectConversation({ agentId }),
    onSuccess: async ({ conversation_id }) => {
      setErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      navigate(`/chat/${conversation_id}`);
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Open direct chat failed");
    }
  });

  function markTouched(field: "agent_id" | "display_name" | "system_prompt" | "workspace_root_input") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "agent_id" | "display_name" | "system_prompt" | "workspace_root_input") {
    return (hasSubmitted || touched[field]) && validationErrors[field];
  }

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        setHasSubmitted(true);
        setErrorMessage(null);

        if (hasValidationErrors) {
          return;
        }

        mutation.mutate(normalizedDraft);
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="im-title text-xl font-bold">New Agent</h2>
          <p className="text-sm text-slate-500">Create a production-ready runtime profile with clear defaults before handing it to operators.</p>
        </div>
        <Link className="text-sm font-semibold text-teal-700 hover:underline" to="/settings/agents">
          Back to Agents
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <div className="grid gap-4">
          <div className="grid gap-1 md:grid-cols-2 md:gap-3">
            <div className="grid gap-1">
              <Label.Root htmlFor="agent-id">Agent ID</Label.Root>
              <input
                id="agent-id"
                className="im-input"
                value={draft.agent_id}
                aria-invalid={Boolean(shouldShowError("agent_id"))}
                aria-describedby="agent-id-help"
                onBlur={() => markTouched("agent_id")}
                onChange={(event) => {
                  setCreatedAgentId(null);
                  setErrorMessage(null);
                  setDraft({ ...draft, agent_id: event.target.value });
                }}
              />
              <p id="agent-id-help" className="text-xs text-slate-500">
                Stable slug used in URLs and runtime routing. Example: `agent-sales-assist`.
              </p>
              {shouldShowError("agent_id") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.agent_id}</p> : null}
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
                  setCreatedAgentId(null);
                  setErrorMessage(null);
                  setDraft({ ...draft, display_name: event.target.value });
                }}
              />
              <p id="display-name-help" className="text-xs text-slate-500">
                Human-friendly name shown to operators and PMs in Settings.
              </p>
              {shouldShowError("display_name") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.display_name}</p> : null}
            </div>
          </div>

          <div className="grid gap-1">
            <Label.Root htmlFor="description">Description</Label.Root>
            <input
              id="description"
              className="im-input"
              value={draft.description}
              aria-describedby="description-help"
              onChange={(event) => {
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, description: event.target.value });
              }}
            />
            <p id="description-help" className="text-xs text-slate-500">
              Explain the business role in one sentence so the next reviewer understands when to use this agent.
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
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, system_prompt: event.target.value });
              }}
            />
            <p id="system-prompt-help" className="text-xs text-slate-500">
              We prefill the personal_assistant product template here. Edit it before saving so it matches this agent.
            </p>
            {shouldShowError("system_prompt") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.system_prompt}</p> : null}
          </div>

          <div className="grid gap-3 md:grid-cols-2 md:gap-3">
            <AllowlistSelector
              id="skills-allowlist"
              label="Skills Allowlist"
              selected={draft.skills}
              options={allowlistOptionsQuery.data?.skills}
              isLoading={allowlistOptionsQuery.isLoading}
              errorMessage={allowlistOptionsQuery.isError ? allowlistErrorDetail : null}
              onRetry={() => void allowlistOptionsQuery.refetch()}
              helpText="Choose from the skills the running system currently exposes. Leave blank to inherit platform defaults."
              emptySelectionText="No skill selected. Leave blank if this agent should inherit platform defaults."
              onChange={(skills) => {
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, skills });
              }}
            />
            <AllowlistSelector
              id="tool-allowlist"
              label="Tool Allowlist"
              selected={draft.tool_allowlist}
              options={allowlistOptionsQuery.data?.tools}
              isLoading={allowlistOptionsQuery.isLoading}
              errorMessage={allowlistOptionsQuery.isError ? allowlistErrorDetail : null}
              onRetry={() => void allowlistOptionsQuery.refetch()}
              showDescriptions={false}
              helpText="Choose from the tools the running system currently exposes. Use the smallest safe surface area for production workflows."
              emptySelectionText="No tool selected yet. Keep this empty if the agent should inherit platform defaults."
              onChange={(toolAllowlist) => {
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, tool_allowlist: toolAllowlist });
              }}
            />
          </div>

          <div className="grid gap-1 md:grid-cols-2 md:gap-3">
            <div className="grid gap-1">
              <Label.Root htmlFor="group-reply-policy">Group Reply Policy</Label.Root>
              <select
                id="group-reply-policy"
                className="im-input"
                aria-describedby="group-reply-policy-help"
                value={draft.group_reply_policy}
                onChange={(event) => {
                  setCreatedAgentId(null);
                  setErrorMessage(null);
                  setDraft({ ...draft, group_reply_policy: event.target.value });
                }}
              >
                <option value="ALWAYS">ALWAYS</option>
                <option value="MENTION">MENTION</option>
                <option value="NO_REPLY">NO_REPLY</option>
              </select>
              <p id="group-reply-policy-help" className="text-xs text-slate-500">
                {policyDescription(draft.group_reply_policy)}
              </p>
            </div>
            <div className="grid gap-1">
              <Label.Root htmlFor="default-model">Default Model</Label.Root>
              <select
                id="default-model"
                className="im-input"
                value={draft.default_model ?? ""}
                aria-describedby="default-model-help"
                disabled={allowlistOptionsQuery.isLoading && availableModels.length === 0}
                onChange={(event) => {
                  setCreatedAgentId(null);
                  setErrorMessage(null);
                  setDraft({ ...draft, default_model: event.target.value || null });
                }}
              >
                <option value="">{platformDefaultLabel(platformDefaultModel)}</option>
                {availableModels.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
              <p id="default-model-help" className="text-xs text-slate-500">
                Choose from the models the current runtime exposes. Leave this on {platformDefaultLabel(platformDefaultModel)} to inherit the platform setting.
              </p>
            </div>
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
              onChange={(event) => setDraft({ ...draft, workspace_root_input: event.target.value })}
            />
            <p id="workspace-root-help" className="text-xs text-slate-500">
              Editable setting. Use an absolute path or `~/...`. Leave blank to let the gateway create the managed default workspace for this agent.
            </p>
            {shouldShowError("workspace_root_input") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.workspace_root_input}</p> : null}
          </div>
        </div>

        <aside className="grid gap-3 rounded-2xl border border-[var(--im-border)] bg-white/75 p-4">
          <section className="grid gap-2 rounded-xl border border-[var(--im-border)] bg-slate-50 p-3">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Current workspace preview</p>
              <p className="break-all font-mono text-sm text-slate-900">
                {normalizedDraft.workspace_root_input || managedWorkspacePreview}
              </p>
              <p className="text-xs text-slate-500">
                Read-only preview. Leave the editable workspace field blank to use the managed default shown here.
              </p>
            </div>
          </section>

          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Node binding</p>
            <p className="text-sm text-slate-600">Bind now if you want immediate runtime placement, or leave unbound and assign later.</p>
          </div>

          <div className="grid gap-1">
            <Label.Root htmlFor="node-id">Node</Label.Root>
            <select
              id="node-id"
              className="im-input"
              value={draft.node_id ?? ""}
              disabled={nodesQuery.isLoading && nodes.length === 0}
              onChange={(event) => {
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, node_id: event.target.value || null });
              }}
            >
              <option value="">Unbound</option>
              {nodes.map((node) => (
                <option key={node.node_id} value={node.node_id}>
                  {node.node_name} ({node.node_id}) · {node.status}
                </option>
              ))}
            </select>
          </div>

          {nodesQuery.isLoading ? <p className="text-xs text-slate-500">Loading nodes. You can still create an unbound agent now.</p> : null}

          {nodesQuery.isError ? (
            <div className="grid gap-2 rounded-xl border border-rose-200 bg-rose-50/80 p-3 text-sm text-rose-700">
              <p className="font-semibold">Could not load live node status.</p>
              <p className="text-xs text-rose-600">{nodeErrorDetail}</p>
              <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void nodesQuery.refetch()}>
                Retry nodes
              </button>
            </div>
          ) : selectedNode ? (
            <div className="grid gap-2 rounded-xl border border-[var(--im-border)] bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{selectedNode.node_name}</p>
                  <p className="text-xs text-slate-500">{selectedNode.node_id}</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${nodeStatusClasses(selectedNode.status)}`}>
                  {selectedNode.status}
                </span>
              </div>
              <dl className="grid gap-1 text-xs text-slate-600">
                <div className="flex items-center justify-between gap-3">
                  <dt>Assigned agents</dt>
                  <dd>{selectedNode.agent_count}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Last heartbeat</dt>
                  <dd>{selectedNode.last_heartbeat_at || "—"}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Runtime version</dt>
                  <dd>{selectedNode.version || "—"}</dd>
                </div>
              </dl>
            </div>
          ) : nodes.length === 0 ? (
            <p className="text-xs text-slate-500">No nodes are currently discoverable. Create the agent unbound and bind it when infrastructure is ready.</p>
          ) : (
            <p className="text-xs text-slate-500">No node selected yet. Leaving this unbound keeps the creation flow unblocked.</p>
          )}
        </aside>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--im-border)] pt-3">
        <div aria-live="polite" className="space-y-1 text-xs">
          {hasSubmitted && hasValidationErrors ? <p className="font-semibold text-rose-700">Complete the required fields before creating this agent.</p> : null}
          {errorMessage ? <p className="font-semibold text-rose-700">{errorMessage}</p> : null}
          {createdAgentId ? (
            <>
              <p className="font-semibold text-emerald-700">Agent created. Open its dedicated direct chat now or keep editing in Settings.</p>
              <p className="text-slate-500">Each agent keeps one stable reusable direct chat window. Reopen this same thread anytime instead of starting a new direct chat.</p>
            </>
          ) : !errorMessage && !hasValidationErrors ? (
            <p className="text-slate-500">Create a new runtime agent profile without leaving Settings.</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {createdAgentId ? (
            <button
              className="im-btn im-btn-muted w-fit"
              type="button"
              disabled={openDirectChatMutation.isPending}
              onClick={() => openDirectChatMutation.mutate(createdAgentId)}
            >
              {openDirectChatMutation.isPending ? "Opening direct chat…" : "Open direct chat"}
            </button>
          ) : null}
          <button className="im-btn im-btn-primary w-fit" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating Agent…" : "Create Agent"}
          </button>
        </div>
      </div>
    </form>
  );
}
