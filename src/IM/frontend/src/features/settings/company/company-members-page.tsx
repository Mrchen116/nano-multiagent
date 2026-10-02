import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { authFetchJson } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";

type Member = {
  id: string;
  username: string;
  display_name: string;
  membership_status: "pending" | "active" | "suspended";
  is_company_admin: boolean;
  node_count: number;
  agent_count: number;
};
type MemberPage = { members: Member[]; next_cursor: string | null };

const statusStyles = {
  active: "bg-[var(--im-success-soft)] text-[var(--im-success-text)]",
  pending: "bg-amber-50 text-amber-800",
  suspended: "bg-im-surface-2 text-im-text-muted"
};

export function CompanyMembersPage() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const currentUser = useAuthStore(s => s.user);
  const client = useQueryClient();
  const [target, setTarget] = useState<Member | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const query = useInfiniteQuery({
    queryKey: ["company", "members"],
    initialPageParam: "",
    enabled: Boolean(currentUser?.is_company_admin),
    queryFn: ({ pageParam }) => authFetchJson<MemberPage>(`/im/v1/company/members?cursor=${encodeURIComponent(pageParam)}`),
    getNextPageParam: last => last.next_cursor ?? undefined
  });
  const change = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "suspend"; name: string }) =>
      authFetchJson(`/im/v1/company/members/${encodeURIComponent(id)}/${action}`, { method: "POST" }),
    onSuccess: async (_, variables) => {
      setTarget(null);
      setFeedback(t(variables.action === "approve" ? "company.approvedFeedback" : "company.suspendedFeedback", { name: variables.name }));
      await client.invalidateQueries({ queryKey: ["company", "members"] });
    }
  });
  if (!currentUser?.is_company_admin) return <Navigate to="/chat" replace />;

  const members = query.data?.pages.flatMap(page => page.members) ?? [];
  const mutationError = change.error?.message.includes("cannot suspend the last active administrator")
    ? t("company.lastAdminError")
    : t("company.updateFailed");
  const closeDialog = () => { if (!change.isPending) { setTarget(null); change.reset(); } };

  return (
    <section className="flex flex-1 flex-col overflow-y-auto bg-[oklch(0.95_0.005_240)]" aria-label={t("company.title")}>
      {isMobile && (
        <div className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b border-im-border bg-[oklch(0.97_0.004_240)] px-1">
          <Link to="/me" aria-label={t("common.back")} className="flex h-10 w-10 items-center justify-center rounded-[10px] text-[22px] hover:bg-im-surface-2">‹</Link>
          <h1 className="m-0 text-[16px] font-bold tracking-tight">{t("company.title")}</h1>
        </div>
      )}
      <div className="mx-auto grid w-full max-w-[880px] gap-4" style={{ padding: isMobile ? "16px 14px" : "24px 28px" }}>
        <header className="flex items-start justify-between gap-4">
          <div>
            {!isMobile && <h1 className="m-0 text-[22px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">{t("company.title")}</h1>}
            <p className="m-0 mt-1 text-[13px] leading-5 text-im-text-muted">{t("company.subtitle")}</p>
          </div>
          <button type="button" className="im-btn im-btn-muted shrink-0" disabled={query.isFetching} onClick={() => void query.refetch()}>{t("company.refreshList")}</button>
        </header>
        {feedback && <p role="status" className="m-0 rounded-[10px] bg-[var(--im-success-soft)] px-4 py-3 text-[13px] text-[var(--im-success-text)]">{feedback}</p>}
        {change.isError && !target && <p role="alert" className="m-0 text-[13px] text-im-danger">{mutationError}</p>}
        <div className="overflow-hidden rounded-[14px] border border-[oklch(0.87_0.006_240)] bg-white">
          <div className="hidden grid-cols-[minmax(0,1fr)_100px_130px_108px] gap-4 border-b border-im-border bg-im-surface-2 px-5 py-3 text-[12px] font-medium text-im-text-muted md:grid" aria-hidden="true">
            <span>{t("company.member")}</span><span>{t("company.role")}</span><span>{t("company.status")}</span><span className="text-right">{t("company.actions")}</span>
          </div>
          {query.isLoading && <p role="status" className="m-0 px-5 py-8 text-[13px] text-im-text-muted">{t("common.loading")}</p>}
          {query.isError && <div className="px-5 py-6"><p role="alert" className="text-[13px] text-im-danger">{t("company.loadFailed")}</p><button className="im-btn im-btn-muted" onClick={() => void query.refetch()}>{t("common.retry")}</button></div>}
          {!query.isLoading && !query.isError && members.length === 0 && <p className="m-0 px-5 py-8 text-[13px] text-im-text-muted">{t("company.empty")}</p>}
          <ul className="m-0 list-none divide-y divide-im-border p-0">
            {members.map(member => {
              const name = member.display_name || member.username;
              return (
                <li key={member.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 px-4 py-4 md:grid-cols-[minmax(0,1fr)_100px_130px_108px] md:gap-4 md:px-5">
                  <div className="flex min-w-0 items-center gap-3">
                    <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--im-user-avatar)] text-[14px] font-semibold text-[var(--im-user-avatar-text)]">{name.trim().slice(0, 2).toUpperCase()}</span>
                    <div className="min-w-0">
                      <p className="m-0 break-words text-[14px] font-semibold leading-5">{name}{member.id === currentUser.id && <span className="ml-2 text-[11px] font-normal text-im-text-muted">{t("company.you")}</span>}</p>
                      <p className="m-0 mt-0.5 break-all text-[12px] leading-4 text-im-text-muted">@{member.username}</p>
                    </div>
                  </div>
                  <span className="hidden text-[12px] text-im-text-muted md:block">{t(member.is_company_admin ? "company.admin" : "company.member")}</span>
                  <div className="col-start-1 row-start-2 flex flex-wrap items-center gap-2 pl-[52px] md:col-auto md:row-auto md:pl-0">
                    <span className={`inline-flex rounded-md px-2 py-1 text-[11px] font-medium leading-4 ${statusStyles[member.membership_status]}`}>{t(`company.statusLabel.${member.membership_status}`)}</span>
                    <span className="text-[11px] text-im-text-muted md:hidden">{t(member.is_company_admin ? "company.admin" : "company.member")}</span>
                  </div>
                  <div className="col-start-2 row-span-2 row-start-1 justify-self-end md:col-auto md:row-span-1 md:row-auto">
                    {member.membership_status === "pending" && <button className="im-btn im-btn-primary" disabled={change.isPending} onClick={() => { setFeedback(null); change.mutate({ id: member.id, action: "approve", name }); }}>{t("company.approve")}</button>}
                    {member.membership_status === "active" && <button className="rounded-lg px-3 py-2 text-[12px] font-medium text-im-danger hover:bg-red-50 disabled:opacity-50" disabled={change.isPending} onClick={() => { change.reset(); setFeedback(null); setTarget(member); }}>{t("company.suspend")}</button>}
                  </div>
                </li>
              );
            })}
          </ul>
          {query.hasNextPage && <div className="border-t border-im-border px-5 py-3 text-center"><button className="im-btn im-btn-muted" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{t("company.more")}</button></div>}
        </div>
      </div>
      <Dialog.Root open={Boolean(target)} onOpenChange={open => { if (!open) closeDialog(); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--im-overlay)]" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 grid w-[calc(100%-32px)] max-w-[440px] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-[14px] border border-im-border bg-white p-6 shadow-[var(--im-shadow-strong)]" onEscapeKeyDown={event => { if (change.isPending) event.preventDefault(); }} onPointerDownOutside={event => { if (change.isPending) event.preventDefault(); }}>
            <Dialog.Title className="m-0 text-[18px] font-bold">{t("company.suspendTitle", { name: target?.display_name || target?.username || "" })}</Dialog.Title>
            <Dialog.Description className="m-0 text-[13px] leading-6 text-im-text-muted">{t("company.impact", { nodes: target?.node_count ?? 0, agents: target?.agent_count ?? 0 })}</Dialog.Description>
            {change.isError && <p role="alert" className="m-0 text-[13px] text-im-danger">{mutationError}</p>}
            <div className="flex justify-end gap-2 border-t border-im-border pt-4">
              <button className="im-btn im-btn-muted" disabled={change.isPending} onClick={closeDialog}>{t("company.cancel")}</button>
              <button className="im-btn !border-transparent !bg-[var(--im-danger)] !text-white" disabled={change.isPending} onClick={() => { if (target) change.mutate({ id: target.id, action: "suspend", name: target.display_name || target.username }); }}>{t("company.confirm")}</button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
