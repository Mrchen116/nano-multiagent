import { Avatar } from "./components/avatar";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "../auth/auth-store";
import { authFetch } from "../auth/auth-fetch";

import { ArrowRight, Check, LoaderCircle, Monitor, ShieldCheck } from "lucide-react";
import { NanoBrand } from "../../app/shell/nano-brand";
import { ProductHeader } from "../home/product-header";
import "./bind-confirm.css";
import { useTranslation } from "../../i18n";
import { bindingTargetKey } from "../onboarding/binding-target";

type Binding = { node_id: string; node_name: string; agents: string[]; state: string; is_transfer?: boolean; history_transferred?: boolean };

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
  useEffect(() => {
    if (!committed) return;
    if (user?.personal_space_enabled && binding.node_id) localStorage.setItem(bindingTargetKey(user.id), binding.node_id);
    void queryClient.invalidateQueries();
  }, [committed, binding?.node_id, user?.id, user?.personal_space_enabled, queryClient]);
  const accountName = user?.display_name || user?.username || "";
  const failure = preview.error || accept.error || cancel.error;
  const phase = committed ? "connected" : accepted ? "connecting" : "confirm";
  return (
    <div className="bind-screen product-entry">
      <ProductHeader page="setup" accountName={accountName} />
      <main className={`bind-layout is-${phase}`}>
        <aside className="bind-scene">
          <div className="bind-scene-copy"><h2>{t("onboarding.bindWorkspace")}</h2><p>{t("onboarding.bindSceneDetail")}</p></div>
          <div className="bind-computer" aria-hidden="true">
            <div className="bind-computer-display"><i className="bind-computer-camera" /><div className="bind-computer-desktop">
              <div className="bind-desktop-sidebar"><span /><i /><i /><i /></div>
              <div className="bind-desktop-window"><NanoBrand /><div className="bind-window-message"><i /><span /><span /></div><div className="bind-window-reply"><Check /><span /></div></div>
            </div></div>
            <div className="bind-computer-base"><i /></div>
            <span className="bind-computer-badge">{committed ? <Check /> : <Monitor />}</span>
          </div>
          <div className="bind-machine"><span>{t("onboarding.bindComputer")}</span><strong>{binding?.node_name || t("onboarding.bindLoading")}</strong></div>
          <div className="bind-scene-foot"><ShieldCheck aria-hidden="true" /><span>{t("onboarding.bindSceneFoot")}</span></div>
        </aside>
        <section className="bind-panel" aria-labelledby="bind-title">
          <div className="bind-phase-label"><span />{t(committed ? "onboarding.bindConnectedLabel" : accepted ? "onboarding.bindConnectingLabel" : "onboarding.bindConfirmLabel")}</div>
          <h1 id="bind-title">{t(committed ? "onboarding.bindConnectedTitle" : accepted ? "onboarding.bindConnectingTitle" : binding?.is_transfer ? "company.bind.title" : "onboarding.bindTitle")}</h1>
          <p className="bind-description">{binding?.is_transfer ? t("onboarding.transferHistory") : t(committed ? "onboarding.bindConnectedNote" : accepted ? "onboarding.bindWaitingNote" : "onboarding.bindDescription")}</p>
          <div className="bind-account"><Avatar id={user?.id ?? ""} size={40} /><div><small>{t(binding?.is_transfer ? "company.bind.account" : "onboarding.bindAccount")}</small><strong>{accountName}</strong></div>
            {!accepted && !committed && <Link to="/login" state={{ signOut: true, from: location.pathname + location.hash }}>{t("company.bind.switch")}</Link>}
          </div>
          {binding?.agents && binding.agents.length > 0 && <p className="bind-agents">{t("shell.tabs.agents")}: {binding.agents.join(", ")}</p>}
          <ol className="bind-progress" aria-label={t("onboarding.bindProgress")}>
            <li className={accepted || committed ? "is-done" : "is-current"}><span aria-hidden="true">{accepted || committed ? <Check /> : "1"}</span><div><strong>{t("onboarding.bindAccountCheck")}</strong><small>{t(accepted || committed ? "onboarding.bindAccountDone" : "onboarding.bindAccountHint")}</small></div></li>
            <li className={committed ? "is-done" : accepted ? "is-current" : ""}><span aria-hidden="true">{committed ? <Check /> : accepted ? <LoaderCircle className="bind-spinner" /> : "2"}</span><div><strong>{t("onboarding.bindComputerCheck")}</strong><small role={accepted && !committed ? "status" : undefined}>{t(committed ? "onboarding.bindComputerDone" : accepted ? binding?.is_transfer ? "company.bind.localConfirm" : "onboarding.bindWaiting" : "onboarding.bindComputerHint")}</small></div></li>
          </ol>
          {!token && <p className="bind-error" role="alert">{t("company.bind.missing")}</p>}
          {failure && <p className="bind-error" role="alert">{failure.message}</p>}
          <div className="bind-actions">
            {!accepted && !committed && <button type="button" className="bind-primary" disabled={!binding || accept.isPending} onClick={() => accept.mutate()}>{accept.isPending ? <LoaderCircle className="bind-spinner" aria-hidden="true" /> : null}{accept.isPending ? t("company.bind.accepting") : t(binding?.is_transfer ? "company.bind.accept" : "onboarding.bindAccept")}<ArrowRight aria-hidden="true" /></button>}
            {committed ? <><p className="bind-complete" role="status"><Check aria-hidden="true" />{t(binding?.is_transfer ? "company.bind.complete" : "onboarding.bindComplete")}</p><Link to={user?.personal_space_enabled ? "/onboarding" : "/chat"} className="bind-primary">{user?.personal_space_enabled ? t("onboarding.bindNext") : t("company.bind.chat")}<ArrowRight aria-hidden="true" /></Link></> : <button type="button" className="bind-cancel" disabled={!binding || cancel.isPending} onClick={() => cancel.mutate()}>{t("company.cancel")}</button>}
          </div>
        </section>
      </main>
    </div>
  );
}
