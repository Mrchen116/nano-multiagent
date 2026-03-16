import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { confirmBindToken } from "./im-chat-api";

export function BindConfirmPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const bindToken = useMemo(() => searchParams.get("token")?.trim() ?? "", [searchParams]);
  const confirmMutation = useMutation({
    mutationFn: () => confirmBindToken(bindToken),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["chat", "bootstrap"] });
      await queryClient.invalidateQueries({ queryKey: ["chat", "starter"] });
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      navigate("/chat", {
        replace: true,
        state: {
          boundSelfUserId: result.self_user_id
        }
      });
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
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
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
