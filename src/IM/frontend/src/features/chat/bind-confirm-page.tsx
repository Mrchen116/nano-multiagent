import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "../auth/auth-store";
import { authFetch } from "../auth/auth-fetch";

import { useTranslation } from "../../i18n";

type Binding = { node_id: string; node_name: string; agents: string[]; state: string };

export function BindConfirmPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [token] = useState(() => new URLSearchParams(location.hash.slice(1)).get("token") ?? "");
  const user = useAuthStore((state) => state.user);
  async function request(action: string): Promise<Binding> {
    const response = await authFetch(`/im/v1/device-binding/${action}`, {
      method: "POST", body: JSON.stringify({ browser_token: token })
    });
    if (!response.ok) throw new Error(t("company.bind.error"));
    return response.json();
  }
  const preview = useQuery({queryKey:["device-binding",token],queryFn:()=>request("inspect"),enabled:!!token,retry:false,refetchInterval:(query)=>query.state.data?.state === "awaiting_local_confirmation" ? 2000 : false});
  const accept = useMutation({mutationFn:()=>request("accept"),onSuccess:()=>{void preview.refetch();}});
  const cancel = useMutation({mutationFn:()=>request("decline"),onSuccess:()=>navigate("/chat")});
  const binding = preview.data;
  const accepted = binding?.state === "awaiting_local_confirmation" || accept.isSuccess;
  const committed = binding?.state === "committed";
  useEffect(()=>{if(committed) void queryClient.invalidateQueries();},[committed,queryClient]);
  return (
    <section className="im-card mx-auto flex w-full max-w-xl flex-col gap-4 px-6 py-8">
      <h1 className="im-title text-2xl font-bold">{t("company.bind.title")}</h1>
      <p className="text-sm text-slate-500">{t("company.bind.description")}</p>
      <p>{t("company.bind.account")}: {user?.display_name || user?.username}</p>
      {!accepted && !committed && <Link to="/login" state={{ signOut: true, from: location.pathname + location.hash }}>{t("company.bind.switch")}</Link>}
      {!token && <p role="alert">{t("company.bind.missing")}</p>}
      {(preview.error || accept.error || cancel.error) && <p role="alert">{(preview.error || accept.error || cancel.error)?.message}</p>}
      {binding && <div>
        <p>{binding.node_name}</p>
        <p>{t("shell.tabs.agents")}: {binding.agents.join(", ") || "—"}</p>
        {(accepted || committed) && <p role="status">{committed ? t("company.bind.complete") : t("company.bind.localConfirm")}</p>}
      </div>}
      {!accepted && !committed && <button type="button" className="im-btn im-btn-primary w-full" disabled={!binding || accept.isPending} onClick={() => accept.mutate()}>{accept.isPending ? t("company.bind.accepting") : t("company.bind.accept")}</button>}
      {committed ? <Link to="/chat" className="im-btn im-btn-muted">{t("company.bind.chat")}</Link> : <button type="button" className="im-btn im-btn-muted" disabled={!binding || cancel.isPending} onClick={()=>cancel.mutate()}>{t("company.cancel")}</button>}
    </section>
  );
}
