import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { AgentProfile, getAgent, updateAgent } from "../mock-settings-api";

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function AgentDetailPage() {
  const { agentId = "" } = useParams();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AgentProfile | null>(null);
  const [saved, setSaved] = useState(false);

  const query = useQuery({
    queryKey: ["settings", "agents", agentId],
    queryFn: () => getAgent(agentId)
  });

  useEffect(() => {
    if (query.data) {
      setDraft(query.data);
    }
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: (next: AgentProfile) =>
      updateAgent(agentId, {
        ...next,
        skills_allowlist: next.skills_allowlist,
        tool_allowlist: next.tool_allowlist
      }),
    onSuccess: async (updated) => {
      setSaved(true);
      if (updated) {
        setDraft(updated);
      }
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents", agentId] });
      setTimeout(() => setSaved(false), 1200);
    }
  });

  if (query.isLoading || !draft) {
    return <p className="text-sm text-slate-500">Loading agent profile...</p>;
  }

  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate(draft);
      }}
    >
      <h2 className="im-title text-xl font-bold">Agent Detail</h2>

      <div className="grid gap-1">
        <Label.Root htmlFor="display-name">Display Name</Label.Root>
        <input
          id="display-name"
          className="im-input"
          value={draft.display_name}
          onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
        />
      </div>

      <div className="grid gap-1">
        <Label.Root htmlFor="description">Description</Label.Root>
        <input
          id="description"
          className="im-input"
          value={draft.description ?? ""}
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
            value={draft.skills_allowlist.join(", ")}
            onChange={(event) => setDraft({ ...draft, skills_allowlist: splitList(event.target.value) })}
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
            onChange={(event) =>
              setDraft({ ...draft, group_reply_policy: event.target.value as AgentProfile["group_reply_policy"] })
            }
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
            onChange={(event) => setDraft({ ...draft, default_model: event.target.value })}
          />
        </div>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">Profile Version: {draft.profile_version}</p>
        {saved && <p className="text-xs font-bold text-emerald-700">Saved</p>}
      </div>

      <button className="im-btn im-btn-primary w-fit" type="submit" disabled={mutation.isPending}>
        Save Agent
      </button>
    </form>
  );
}
