import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { AccountProfile, getAccount, listNodes, updateAccount } from "../im-settings-api";

export function AccountPage() {
  const queryClient = useQueryClient();
  const accountQuery = useQuery({
    queryKey: ["settings", "account"],
    queryFn: getAccount
  });
  const nodesQuery = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes
  });

  const [draft, setDraft] = useState<AccountProfile | null>(null);

  useEffect(() => {
    if (accountQuery.data) {
      setDraft(accountQuery.data);
    }
  }, [accountQuery.data]);

  const mutation = useMutation({
    mutationFn: (next: AccountProfile) =>
      updateAccount({
        display_name: next.display_name,
        default_entry_node_id: next.default_entry_node_id
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "account"] });
    }
  });

  if (!draft) {
    return <p className="text-sm text-slate-500">Loading account...</p>;
  }

  return (
    <form
      className="flex h-full flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate(draft);
      }}
    >
      <h2 className="im-title text-xl font-bold">Account</h2>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        User ID
        <input className="im-input" value={draft.user_id || draft.id} disabled />
      </label>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Display Name
        <input
          className="im-input"
          value={draft.display_name}
          onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
        />
      </label>

      <label className="grid gap-1 text-xs font-semibold text-slate-600">
        Default Entry Node
        <select
          className="im-input"
          value={draft.default_entry_node_id ?? ""}
          onChange={(event) =>
            setDraft({ ...draft, default_entry_node_id: event.target.value.length > 0 ? event.target.value : null })
          }
        >
          <option value="">Select one node</option>
          {(nodesQuery.data ?? [])
            .filter((node) => draft.owned_node_ids.includes(node.node_id))
            .map((node) => (
              <option key={node.node_id} value={node.node_id}>
                {node.alias || node.node_name} ({node.status})
              </option>
            ))}
        </select>
      </label>

      <p className="text-xs text-slate-500">Owned Nodes: {draft.owned_node_ids.join(", ") || "none"}</p>
      <p className="text-xs text-slate-500">Created At: {draft.created_at || "-"}</p>

      <button className="im-btn im-btn-primary w-fit" type="submit" disabled={mutation.isPending}>
        Save Account
      </button>
    </form>
  );
}
