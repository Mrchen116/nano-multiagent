import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { createDirectConversation } from "../../chat/chat-api";
import { AllowlistSelector } from "./allowlist-selector";
import { AgentSummary, createNodeAgent, getNodeCreateState, NodeAgentCreateRequest } from "./im-agent-config-api";

type CreateAgentFormState = NodeAgentCreateRequest;

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
    default_model: normalizeText(draft.default_model ?? "") || null
  };
}

function validateDraft(draft: CreateAgentFormState) {
  const errors: Partial<Record<"agent_id" | "display_name" | "system_prompt", string>> = {};

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

  return errors;
}

function policyDescription(policy: CreateAgentFormState["group_reply_policy"]) {
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
  default_model: null
};

export function AgentCreatePage() {
  const { nodeId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<CreateAgentFormState>(EMPTY_DRAFT);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const createStateQuery = useQuery({
    queryKey: ["settings", "nodes", nodeId, "create-state"],
    queryFn: () => getNodeCreateState(nodeId),
    staleTime: 30_000
  });

  useEffect(() => {
    const defaultSystemPrompt = createStateQuery.data?.capabilities.default_system_prompt?.trim() ?? "";
    if (!defaultSystemPrompt) {
      return;
    }
    setDraft((current) => {
      if (current.system_prompt.trim().length > 0) {
        return current;
      }
      return { ...current, system_prompt: defaultSystemPrompt };
    });
  }, [createStateQuery.data?.capabilities.default_system_prompt]);

  const normalizedDraft = useMemo(() => normalizeDraft(draft), [draft]);
  const validationErrors = useMemo(() => validateDraft(normalizedDraft), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const capabilities = createStateQuery.data?.capabilities;
  const node = createStateQuery.data?.node ?? null;
  const availableModels = capabilities?.model_options ?? [];
  const nodeLabel = capabilities?.node_name ?? node?.node_name ?? nodeId;
  const nodeStatus = capabilities?.node_status ?? node?.status ?? "unknown";
  const isNodeOnline = nodeStatus.toLowerCase() === "online";
  const queryErrorDetail =
    createStateQuery.error instanceof Error
      ? createStateQuery.error.message.split(" failed: ").at(-1) ?? createStateQuery.error.message
      : "Unable to load this node.";

  const mutation = useMutation({
    mutationFn: (next: CreateAgentFormState) => createNodeAgent(nodeId, next),
    onSuccess: async (created) => {
      setErrorMessage(null);
      setCreatedAgentId(created.agent_id);
      queryClient.setQueryData(["settings", "agents", created.agent_id], created);
      queryClient.setQueryData(["settings", "agents"], (current: AgentSummary[] | undefined) => {
        if (!current) {
          return [created];
        }
        const next = current.filter((agent) => agent.agent_id !== created.agent_id);
        return [created, ...next];
      });
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "nodes"] });
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

  function markTouched(field: "agent_id" | "display_name" | "system_prompt") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "agent_id" | "display_name" | "system_prompt") {
    return (hasSubmitted || touched[field]) && validationErrors[field];
  }

  if (createStateQuery.isLoading && !capabilities) {
    return <p className="text-sm text-slate-500">Loading node creation flow...</p>;
  }

  if (createStateQuery.isError && !capabilities) {
    return (
      <section className="grid gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">Could not load this node.</p>
          <p className="text-sm text-rose-600">{queryErrorDetail}</p>
        </div>
        <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void createStateQuery.refetch()}>
          Retry
        </button>
      </section>
    );
  }

  if (!capabilities) {
    return <p className="text-sm text-slate-500">Loading node creation flow...</p>;
  }

  return (
    <form
      className="flex h-full flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        setHasSubmitted(true);
        setErrorMessage(null);

        if (hasValidationErrors || !isNodeOnline) {
          return;
        }

        mutation.mutate(normalizedDraft);
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl space-y-2">
          <h2 className="im-title text-xl font-bold">Create Agent on {nodeLabel}</h2>
          <p className="text-sm text-slate-500">Start from one online node so runtime choices match the node that will actually host this agent.</p>
        </div>
        <Link className="text-sm font-semibold text-teal-700 hover:underline" to="/settings/nodes">
          Back to Nodes
        </Link>
      </div>

      <section className="im-section-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="im-section-heading">Owning node</h3>
            <p className="im-section-copy">Only online bound nodes can host a new agent.</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${nodeStatusClasses(nodeStatus)}`}>{nodeStatus}</span>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="im-subtle-card grid gap-1">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Node</p>
            <p className="text-sm font-semibold text-slate-900">{nodeLabel}</p>
            <p className="text-xs text-slate-500">{nodeId}</p>
          </div>
          <div className="im-subtle-card grid gap-1">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Capabilities updated</p>
            <p className="text-sm text-slate-900">{capabilities.capabilities_updated_at ?? "—"}</p>
            {!isNodeOnline ? <p className="text-xs font-semibold text-rose-700">This node is not online, so creation is blocked.</p> : null}
          </div>
        </div>
      </section>

      <div className="grid gap-4">
        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Identity</h3>
            <p className="im-section-copy">Name the agent clearly so operators can recognize its role at a glance.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
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
        </section>

        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Behavior</h3>
            <p className="im-section-copy">Start from the standard template, then tune behavior only where this agent truly differs.</p>
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
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, system_prompt: event.target.value });
              }}
            />
            <p id="system-prompt-help" className="text-xs text-slate-500">
              We prefill the standard personal assistant template here. Edit it before saving so it matches this agent.
            </p>
            {shouldShowError("system_prompt") ? <p className="text-xs font-semibold text-rose-700">{validationErrors.system_prompt}</p> : null}
          </div>
          <div className="grid gap-1 md:max-w-sm">
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
        </section>

        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Access & model</h3>
            <p className="im-section-copy">Keep the allowed surface area small and leave the model on platform default unless this agent needs a known override.</p>
          </div>
          <div className="grid gap-3 2xl:grid-cols-2">
            <AllowlistSelector
              id="skills-allowlist"
              label="Skills"
              selected={draft.skills}
              options={capabilities.skills}
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              helpText="Choose only the reusable skills this agent needs right now."
              emptySelectionText="No skill selected. Leave blank if this agent should inherit platform defaults."
              onChange={(skills) => {
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, skills });
              }}
            />
            <AllowlistSelector
              id="tool-allowlist"
              label="Tools"
              selected={draft.tool_allowlist}
              options={capabilities.tools}
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              showDescriptions={false}
              helpText="Choose only the tools this agent needs right now."
              emptySelectionText="No tool selected yet. Keep this empty if the agent should inherit platform defaults."
              onChange={(toolAllowlist) => {
                setCreatedAgentId(null);
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
              onChange={(event) => {
                setCreatedAgentId(null);
                setErrorMessage(null);
                setDraft({ ...draft, default_model: event.target.value || null });
              }}
            >
              <option value="">{platformDefaultLabel(capabilities.platform_default_model)}</option>
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            <p id="default-model-help" className="text-xs text-slate-500">
              Choose from the models the selected node currently exposes. Leave this on {platformDefaultLabel(capabilities.platform_default_model)} to inherit the platform setting.
            </p>
          </div>
        </section>

        <section className="im-section-card">
          <div className="space-y-1">
            <h3 className="im-section-heading">Workspace</h3>
            <p className="im-section-copy">Workspace root will be assigned by this node during creation and stays read-only afterwards.</p>
          </div>
          <div className="im-subtle-card grid gap-1">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Assigned workspace root</p>
            <p className="text-sm text-slate-900">Workspace root will be assigned by this node when the agent is created.</p>
          </div>
        </section>
      </div>

      <div className="rounded-[1.25rem] border border-[var(--im-border)] bg-white/80 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div aria-live="polite" className="space-y-1 text-xs">
            {hasSubmitted && hasValidationErrors ? <p className="font-semibold text-rose-700">Complete the required fields before creating this agent.</p> : null}
            {hasSubmitted && !hasValidationErrors && !isNodeOnline ? <p className="font-semibold text-rose-700">Bring this node online before creating an agent on it.</p> : null}
            {errorMessage ? <p className="font-semibold text-rose-700">{errorMessage}</p> : null}
            {createdAgentId ? (
              <>
                <p className="font-semibold text-emerald-700">Agent created. Open its dedicated direct chat now or keep editing in Settings.</p>
                <Link className="w-fit font-semibold text-teal-700 hover:underline" to={`/settings/agents/${createdAgentId}`}>
                  {draft.display_name.trim() || createdAgentId}
                </Link>
              </>
            ) : !errorMessage && !hasValidationErrors ? (
              <p className="text-slate-500">Create a new runtime agent profile on {nodeLabel} without leaving Settings.</p>
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
            <button className="im-btn im-btn-primary w-fit" type="submit" disabled={mutation.isPending || !isNodeOnline}>
              {mutation.isPending ? "Creating Agent…" : "Create Agent"}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
