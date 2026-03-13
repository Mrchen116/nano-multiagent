import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createAgent, CreateAgentRequest, listNodes } from "./im-agent-config-api";

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
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

  const nodesQuery = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });

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

  const nodes = nodesQuery.data ?? [];

  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate(draft);
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="im-title text-xl font-bold">New Agent</h2>
        <Link className="text-sm font-semibold text-teal-700 hover:underline" to="/settings/agents">
          Back to Agents
        </Link>
      </div>

      <div className="grid gap-1 md:grid-cols-2">
        <div className="grid gap-1">
          <Label.Root htmlFor="agent-id">Agent ID</Label.Root>
          <input
            id="agent-id"
            className="im-input"
            value={draft.agent_id}
            onChange={(event) => setDraft({ ...draft, agent_id: event.target.value })}
          />
        </div>
        <div className="grid gap-1">
          <Label.Root htmlFor="display-name">Display Name</Label.Root>
          <input
            id="display-name"
            className="im-input"
            value={draft.display_name}
            onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
          />
        </div>
      </div>

      <div className="grid gap-1">
        <Label.Root htmlFor="description">Description</Label.Root>
        <input
          id="description"
          className="im-input"
          value={draft.description}
          onChange={(event) => setDraft({ ...draft, description: event.target.value })}
        />
      </div>

      <div className="grid gap-1">
        <Label.Root htmlFor="system-prompt">System Prompt</Label.Root>
        <textarea
          id="system-prompt"
          className="im-input min-h-28"
          value={draft.system_prompt}
          onChange={(event) => setDraft({ ...draft, system_prompt: event.target.value })}
        />
      </div>

      <div className="grid gap-1 md:grid-cols-2">
        <div className="grid gap-1">
          <Label.Root htmlFor="skills-allowlist">Skills Allowlist</Label.Root>
          <input
            id="skills-allowlist"
            className="im-input"
            value={draft.skills.join(", ")}
            onChange={(event) => setDraft({ ...draft, skills: splitList(event.target.value) })}
          />
        </div>
        <div className="grid gap-1">
          <Label.Root htmlFor="tool-allowlist">Tool Allowlist</Label.Root>
          <input
            id="tool-allowlist"
            className="im-input"
            value={draft.tool_allowlist.join(", ")}
            onChange={(event) => setDraft({ ...draft, tool_allowlist: splitList(event.target.value) })}
          />
        </div>
      </div>

      <div className="grid gap-1 md:grid-cols-2">
        <div className="grid gap-1">
          <Label.Root htmlFor="group-reply-policy">Group Reply Policy</Label.Root>
          <select
            id="group-reply-policy"
            className="im-input"
            value={draft.group_reply_policy}
            onChange={(event) => setDraft({ ...draft, group_reply_policy: event.target.value })}
          >
            <option value="ALWAYS">ALWAYS</option>
            <option value="MENTION">MENTION</option>
            <option value="NO_REPLY">NO_REPLY</option>
          </select>
        </div>
        <div className="grid gap-1">
          <Label.Root htmlFor="default-model">Default Model</Label.Root>
          <input
            id="default-model"
            className="im-input"
            value={draft.default_model ?? ""}
            onChange={(event) => setDraft({ ...draft, default_model: event.target.value || null })}
          />
        </div>
      </div>

      <div className="grid gap-1">
        <Label.Root htmlFor="node-id">Node</Label.Root>
        <select
          id="node-id"
          className="im-input"
          value={draft.node_id ?? ""}
          onChange={(event) => setDraft({ ...draft, node_id: event.target.value || null })}
        >
          <option value="">Unbound</option>
          {nodes.map((node) => (
            <option key={node.node_id} value={node.node_id}>
              {node.node_name} ({node.node_id})
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-500">Create a new runtime agent profile without leaving Settings.</p>
        {errorMessage && <p className="text-xs font-bold text-rose-700">{errorMessage}</p>}
      </div>

      <button className="im-btn im-btn-primary w-fit" type="submit" disabled={mutation.isPending || nodesQuery.isLoading}>
        Create Agent
      </button>
    </form>
  );
}
