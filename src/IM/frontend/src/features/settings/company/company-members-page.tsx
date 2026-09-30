import { useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { authFetchJson } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";

type Member = { id: string; username: string; display_name: string; membership_status: "pending" | "active" | "suspended"; is_company_admin: boolean; node_count: number; agent_count: number };
type MemberPage = { members: Member[]; next_cursor: string | null };
export function CompanyMembersPage() {
  const { t } = useTranslation();
  const admin = useAuthStore(s => s.user?.is_company_admin);
  const client = useQueryClient();
  const [target, setTarget] = useState<Member | null>(null);
  const query = useInfiniteQuery({ queryKey: ["company", "members"], initialPageParam: "", enabled: Boolean(admin), queryFn: ({ pageParam }) => authFetchJson<MemberPage>(`/im/v1/company/members?cursor=${encodeURIComponent(pageParam)}`), getNextPageParam: last => last.next_cursor ?? undefined });
  const change = useMutation({ mutationFn: ({ id, action }: { id: string; action: "approve" | "suspend" }) => authFetchJson(`/im/v1/company/members/${encodeURIComponent(id)}/${action}`, { method: "POST" }), onSuccess: async () => { setTarget(null); await client.invalidateQueries({ queryKey: ["company", "members"] }); } });
  if (!admin) return <Navigate to="/chat" replace />;
  return <section className="flex-1 overflow-y-auto p-4 md:p-6" aria-label={t("company.title")}>
    <div className="mx-auto max-w-[780px] grid gap-4">
      <h1 className="text-[22px] font-extrabold">{t("company.title")}</h1>
      {(query.isError || change.isError) && <p role="alert">{t("auth.feedback.serviceUnavailable")}</p>}
      {query.data?.pages.flatMap(page => page.members).map(member => <article key={member.id} className="rounded-[14px] border bg-white p-4 flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-0"><strong className="break-words">{member.display_name || member.username}</strong><p className="text-sm text-slate-500 break-words">{member.username} · {t(`company.${member.membership_status}`)} {member.is_company_admin && `· ${t("company.admin")}`}</p></div>
        {member.membership_status === "pending" && <button className="im-btn im-btn-primary" disabled={change.isPending} onClick={() => change.mutate({ id: member.id, action: "approve" })}>{t("company.approve")}</button>}
        {member.membership_status === "active" && <button className="im-btn im-btn-muted" disabled={change.isPending} onClick={() => setTarget(member)}>{t("company.suspend")}</button>}
      </article>)}
      {query.hasNextPage && <button className="im-btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{t("company.more")}</button>}
    </div>
    {target && <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4" role="presentation"><section role="dialog" aria-modal="true" aria-labelledby="suspend-title" className="bg-white rounded-[14px] p-6 max-w-md grid gap-4"><h2 id="suspend-title">{t("company.suspend")} · {target.display_name}</h2><p>{t("company.impact", { nodes: target.node_count, agents: target.agent_count })}</p>{change.isError && <p role="alert">{t("auth.feedback.serviceUnavailable")}</p>}<div className="flex gap-2"><button className="im-btn" disabled={change.isPending} onClick={() => setTarget(null)}>{t("company.cancel")}</button><button className="im-btn im-btn-primary" disabled={change.isPending} onClick={() => change.mutate({ id: target.id, action: "suspend" })}>{t("company.confirm")}</button></div></section></div>}
  </section>;
}
