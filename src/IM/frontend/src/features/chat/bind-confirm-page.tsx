import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuthStore, type AuthUser } from "../auth/auth-store";
import {
  confirmBindToken,
  getAccount,
  type AccountProfile
} from "../settings/im-settings-api";

const OWNER_DERIVED_QUERY_KEYS = [
  ["chat", "conversations"],
  ["chat", "agents"],
  ["chat", "nodes"],
  ["settings", "account"],
  ["settings", "nodes"],
  ["settings", "agents"]
] as const;

function toAuthUser(account: AccountProfile): AuthUser {
  return {
    id: account.user_id || account.id,
    username: account.username,
    display_name: account.display_name,
    owner_id: account.owner_id,
    locale: account.locale,
    default_entry_node_id: account.default_entry_node_id,
    owned_node_ids: account.owned_node_ids,
    created_at: account.created_at
  };
}

export function BindConfirmPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const bindToken = useMemo(() => searchParams.get("token")?.trim() ?? "", [searchParams]);
  const confirmedBind = useRef<{ token: string; result: { node_id: string } } | null>(null);
  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (confirmedBind.current?.token !== bindToken) {
        confirmedBind.current = { token: bindToken, result: await confirmBindToken(bindToken) };
      }

      const account = await getAccount();
      if (!useAuthStore.getState().replaceUser(toAuthUser(account))) {
        throw new Error(
          "Binding succeeded, but the signed-in account changed. Sign in again to finish syncing."
        );
      }

      const results = await Promise.allSettled(
        OWNER_DERIVED_QUERY_KEYS.map((queryKey) =>
          queryClient.invalidateQueries({ queryKey, refetchType: "all" }, { throwOnError: true })
        )
      );
      const failure = results.find((result) => result.status === "rejected");
      if (failure?.status === "rejected") {
        throw failure.reason instanceof Error
          ? failure.reason
          : new Error("Binding succeeded, but refreshing owner data failed.");
      }
      return confirmedBind.current.result;
    },
    onSuccess: () => {
      navigate("/chat", { replace: true });
    }
  });

  return (
    <section className="im-card mx-auto flex w-full max-w-xl flex-col gap-4 px-6 py-8">
      <div className="space-y-2">
        <p className="im-title text-2xl font-bold">Bind this Gateway</p>
        <p className="text-sm text-slate-500">
          Finish the local device bind, then go straight into Web IM chat.
        </p>
      </div>
      {!bindToken ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Missing bind token. Restart the Gateway so it can open a fresh bind link.
        </div>
      ) : (
        <div className="rounded-2xl border border-[var(--im-border)] bg-slate-50 px-4 py-3 text-sm text-slate-600">
          You will continue as the default local IM user and bind this browser session to the current Gateway node.
        </div>
      )}
      {confirmMutation.isError && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
        >
          {(confirmMutation.error as Error).message}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="im-btn im-btn-primary"
          disabled={!bindToken || confirmMutation.isPending}
          onClick={() => confirmMutation.mutate()}
        >
          {confirmMutation.isPending ? "Binding..." : "Continue to chat"}
        </button>
        <Link to="/chat" className="im-btn im-btn-muted">
          Back to chat
        </Link>
      </div>
    </section>
  );
}
