import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { PolicyProfile, getPolicies, updatePolicies } from "../im-settings-api";

export function PoliciesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["settings", "policies"],
    queryFn: getPolicies
  });

  const [draft, setDraft] = useState<PolicyProfile | null>(null);

  useEffect(() => {
    if (query.data) {
      setDraft(query.data);
    }
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: (next: PolicyProfile) => updatePolicies(next),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "policies"] });
    }
  });

  if (!draft) {
    return <p className="text-sm text-slate-500">Loading policies...</p>;
  }

  return (
    <form
      className="grid h-full flex-1 gap-3 md:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate(draft);
      }}
    >
      <h2 className="im-title col-span-full text-xl font-bold">Policies</h2>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Default Model
        <input
          className="im-input"
          value={draft.default_model}
          onChange={(event) => setDraft({ ...draft, default_model: event.target.value })}
        />
      </label>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Audit Level
        <select
          className="im-input"
          value={draft.audit_level}
          onChange={(event) => setDraft({ ...draft, audit_level: event.target.value as PolicyProfile["audit_level"] })}
        >
          <option value="off">off</option>
          <option value="basic">basic</option>
          <option value="strict">strict</option>
        </select>
      </label>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Max Turn Per Run
        <input
          className="im-input"
          type="number"
          value={draft.max_turn_per_run}
          onChange={(event) => setDraft({ ...draft, max_turn_per_run: Number(event.target.value) })}
        />
      </label>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Rate Limit / Min
        <input
          className="im-input"
          type="number"
          value={draft.rate_limit_per_min}
          onChange={(event) => setDraft({ ...draft, rate_limit_per_min: Number(event.target.value) })}
        />
      </label>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Max Attachment Size (MB)
        <input
          className="im-input"
          type="number"
          value={draft.max_attachment_size_mb}
          onChange={(event) => setDraft({ ...draft, max_attachment_size_mb: Number(event.target.value) })}
        />
      </label>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Retention Days
        <input
          className="im-input"
          type="number"
          value={draft.retention_days}
          onChange={(event) => setDraft({ ...draft, retention_days: Number(event.target.value) })}
        />
      </label>

      <button className="im-btn im-btn-primary col-span-full w-fit" type="submit" disabled={mutation.isPending}>
        Save Policies
      </button>
    </form>
  );
}
