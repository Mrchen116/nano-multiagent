import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createAgent, CreateAgentRequest, listNodes } from "./im-agent-config-api";

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeText(value: string) {
  return value.trim();
}

function normalizeDraft(draft: CreateAgentRequest): CreateAgentRequest {
  return {
    ...draft,
    agent_id: normalizeText(draft.agent_id),
    display_name: normalizeText(draft.display_name),
    description: normalizeText(draft.description),
    system_prompt: draft.system_prompt.trim(),
    skills: splitList(draft.skills.join(",")),
    tool_allowlist: splitList(draft.tool_allowlist.join(",")),
    default_model: normalizeText(draft.default_model ?? "") || null,
    node_id: draft.node_id || null
  };
}

function validateDraft(draft: CreateAgentRequest) {
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

const EMPTY_DRAFT: CreateAgentRequest = {
  agent_id: "",
  owner_id: "",
  display_name: "",
  description: "",
  system_prompt: "",
  skills: [],
  tool_allowlist: [],
  group_reply_policy: "MENTION",
  default_model: null,
  node_id: null
};

export function AgentCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<CreateAgentRequest>(EMPTY_DRAFT);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const nodesQuery = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });

  const normalizedDraft = useMemo(() => normalizeDraft(draft), [draft]);
  const validationErrors = useMemo(() => validateDraft(normalizedDraft), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const nodes = nodesQuery.data ?? [];
  const selectedNode = nodes.find((node) => node.node_id === draft.node_id) ?? null;
  const nodeErrorDetail =
    nodesQuery.error instanceof Error ? nodesQuery.error.message.split(" failed: ").at(-1) ?? nodesQuery.error.message : "Unable to load nodes.";

  const mutation = useMutation({
    mutationFn: (next: CreateAgentRequest) => createAgent(next),
    onSuccess: async (created) => {
      setErrorMessage(null);
      queryClient.setQueryData(["settings", "agents", created.agent_id], created);
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "nodes"] });
      await navigate(`/settings/agents/${created.agent_id}`);
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Create failed");
    }
  });

  function markTouched(field: "agent_id" | "display_name" | "system_prompt") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "agent_id" | "display_name" | "system_prompt") {
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
                onChange={(event) => setDraft({ ...draft, agent_id: event.target.value })}
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
                onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
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
              onChange={(event) => setDraft({ ...draft, description: event.target.value })}
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
              onChange={(event) => setDraft({ ...draft, system_prompt: event.target.value })}
            />
            <p id="system-prompt-help" className="text-xs text-slate-500">
              Capture role, guardrails, and preferred tone. This is the primary behavior contract for the agent.
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
                onChange={(event) => setDraft({ ...draft, skills: splitList(event.target.value) })}
              />
              <p id="skills-help" className="text-xs text-slate-500">
                Comma-separated. Leave blank if the agent should inherit platform defaults.
              </p>
            </div>
            <div className="grid gap-1">
              <Label.Root htmlFor="tool-allowlist">Tool Allowlist</Label.Root>
              <input
                id="tool-allowlist"
                className="im-input"
                value={draft.tool_allowlist.join(", ")}
                aria-describedby="tools-help"
                onChange={(event) => setDraft({ ...draft, tool_allowlist: splitList(event.target.value) })}
              />
              <p id="tools-help" className="text-xs text-slate-500">
                Comma-separated. Use the smallest safe surface area for production workflows.
              </p>
            </div>
          </div>

          <div className="grid gap-1 md:grid-cols-2 md:gap-3">
            <div className="grid gap-1">
              <Label.Root htmlFor="group-reply-policy">Group Reply Policy</Label.Root>
              <select
                id="group-reply-policy"
                className="im-input"
                aria-describedby="group-reply-policy-help"
                value={draft.group_reply_policy}
                onChange={(event) => setDraft({ ...draft, group_reply_policy: event.target.value })}
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
              <input
                id="default-model"
                className="im-input"
                value={draft.default_model ?? ""}
                aria-describedby="default-model-help"
                onChange={(event) => setDraft({ ...draft, default_model: event.target.value || null })}
              />
              <p id="default-model-help" className="text-xs text-slate-500">
                Optional. Set a business-approved model override, or leave blank to follow the platform default.
              </p>
            </div>
          </div>
        </div>

        <aside className="grid gap-3 rounded-2xl border border-[var(--im-border)] bg-white/75 p-4">
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
              onChange={(event) => setDraft({ ...draft, node_id: event.target.value || null })}
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
          {!errorMessage && !hasValidationErrors ? <p className="text-slate-500">Create a new runtime agent profile without leaving Settings.</p> : null}
        </div>
        <button className="im-btn im-btn-primary w-fit" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Creating Agent…" : "Create Agent"}
        </button>
      </div>
    </form>
  );
}
