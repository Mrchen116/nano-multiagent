import "./company-members-page.css";

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
  active: "company-status--active",
  pending: "company-status--pending",
  suspended: "company-status--suspended"
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
    <section className="company-page" aria-label={t("company.title")}>
      {isMobile && (
        <div className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b border-im-border bg-[oklch(0.97_0.004_240)] px-1">
          <Link to="/me" aria-label={t("common.back")} className="flex h-10 w-10 items-center justify-center rounded-[10px] text-[22px] hover:bg-im-surface-2">‹</Link>
          <h1 className="m-0 text-[16px] font-bold tracking-tight">{t("company.title")}</h1>
        </div>
      )}
      <div className="company-content">
        <header className="company-heading">
          <div>
            {!isMobile && <h1 className="company-title">{t("company.title")}</h1>}
            <p className="company-description">{t("company.subtitle")}</p>
          </div>
          <button type="button" className="company-refresh" aria-label={t("company.refreshList")} title={t("company.refreshList")} disabled={query.isFetching} onClick={() => void query.refetch()}>
            <svg className={query.isFetching ? "animate-spin" : ""} aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M20 7v5h-5" /><path d="M19.2 12a7.5 7.5 0 1 0-2 5.3M20 12l-3.4-4" /></svg>
          </button>
        </header>
        {feedback && <p role="status" className="m-0 rounded-[10px] bg-[var(--im-success-soft)] px-4 py-3 text-[13px] text-[var(--im-success-text)]">{feedback}</p>}
        {change.isError && !target && <p role="alert" className="m-0 text-[13px] text-im-danger">{mutationError}</p>}
        <div className="company-directory">
          <div className="company-columns company-column-headings" aria-hidden="true">
            <span className="company-member-heading">{t("company.member")}</span><span>{t("company.role")}</span><span>{t("company.status")}</span><span className="company-actions-heading">{t("company.actions")}</span>
          </div>
          {query.isLoading && <p role="status" className="m-0 px-5 py-8 text-[13px] text-im-text-muted">{t("common.loading")}</p>}
          {query.isError && <div className="px-5 py-6"><p role="alert" className="text-[13px] text-im-danger">{t("company.loadFailed")}</p><button className="im-btn im-btn-muted" onClick={() => void query.refetch()}>{t("common.retry")}</button></div>}
          {!query.isLoading && !query.isError && members.length === 0 && <p className="m-0 px-5 py-8 text-[13px] text-im-text-muted">{t("company.empty")}</p>}
          <ul className="company-member-list">
            {members.map(member => {
              const name = member.display_name || member.username;
              return (
                <li key={member.id} className="company-columns company-member-row">
                  <div className="company-identity">
                    <span aria-hidden="true" className="company-avatar">{name.trim().slice(0, 2).toUpperCase()}</span>
                    <div className="min-w-0">
                      <p className="company-member-name">{name}{member.id === currentUser.id && <span className="ml-2 text-[11px] font-normal text-im-text-muted">{t("company.you")}</span>}</p>
                      <p className="company-username">@{member.username}</p>
                    </div>
                  </div>
                  <span className="company-role">{t(member.is_company_admin ? "company.admin" : "company.member")}</span>
                  <div className="company-member-status">
                    <span className={`company-status ${statusStyles[member.membership_status]}`}>{t(`company.statusLabel.${member.membership_status}`)}</span>
                    <span className="company-mobile-role">{t(member.is_company_admin ? "company.admin" : "company.member")}</span>
                  </div>
                  <div className="company-member-actions">
                    {member.membership_status === "pending" && <button className="company-action company-action--approve" disabled={change.isPending} onClick={() => { setFeedback(null); change.mutate({ id: member.id, action: "approve", name }); }}>{t("company.approve")}</button>}
                    {member.membership_status === "active" && <button aria-label={t("company.suspend")} className="company-action company-action--suspend" disabled={change.isPending} onClick={() => { change.reset(); setFeedback(null); setTarget(member); }}>{t("company.suspendAction")}</button>}
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
