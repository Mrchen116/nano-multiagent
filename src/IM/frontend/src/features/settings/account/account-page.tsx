import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { useTranslation, type Locale } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import {
  AccountProfile,
  UpdateAccountInput,
  getAccount,
  listNodes,
  updateAccount
} from "../im-settings-api";

// M19/R11-6: prototype `im-extra-pages.jsx::AccountPage` 是 2 张窄居中卡 (Profile +
// Gateway, maxWidth 620px),Profile 头部带 54×54 圆 avatar + initials + mono user_id。
// Preferences 卡 (Language radio + Notifications checkbox) 不在 prototype —
// Language 入口在 Me 页 / UserMenu (R2 已落),Notifications toggle 在 Me 页 (R2 已落)。

interface DraftState {
  display_name: string;
  default_entry_node_id: string | null;
}

function toDraft(profile: AccountProfile): DraftState {
  return {
    display_name: profile.display_name,
    default_entry_node_id: profile.default_entry_node_id
  };
}

function isDirty(draft: DraftState, profile: AccountProfile): boolean {
  return (
    draft.display_name !== profile.display_name ||
    draft.default_entry_node_id !== profile.default_entry_node_id
  );
}

function initialsOf(name: string): string {
  return (name || "U").trim().slice(0, 2).toUpperCase();
}

export function AccountPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const accountQuery = useQuery({ queryKey: ["settings", "account"], queryFn: getAccount });
  const nodesQuery = useQuery({ queryKey: ["settings", "nodes"], queryFn: listNodes });

  const profile = accountQuery.data;
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    if (profile) {
      setDraft(toDraft(profile));
    }
  }, [profile]);

  const mutation = useMutation({
    mutationFn: async (input: UpdateAccountInput) => updateAccount(input),
    onSuccess: async (updated) => {
      const auth = useAuthStore.getState();
      if (auth.user) {
        auth.setSession({
          access_token: auth.accessToken ?? "",
          refresh_token: auth.refreshToken ?? "",
          user: { ...auth.user, display_name: updated.display_name, locale: updated.locale }
        });
      }
      setErrorDetail(null);
      await queryClient.invalidateQueries({ queryKey: ["settings", "account"] });
    },
    onError: (err: Error) => {
      setErrorDetail(err.message);
    }
  });

  const ownedNodeRows = useMemo(() => {
    if (!profile) return [];
    return (nodesQuery.data ?? []).filter((node) => profile.owned_node_ids.includes(node.node_id));
  }, [profile, nodesQuery.data]);

  if (!draft || !profile) {
    return <p className="text-sm text-slate-500">{t("common.loading")}</p>;
  }

  const dirty = isDirty(draft, profile);
  const currentLocale: Locale = profile.locale === "zh" ? "zh" : "en";

  const onDiscard = () => {
    setDraft(toDraft(profile));
    setErrorDetail(null);
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!dirty || mutation.isPending) return;
    mutation.mutate({
      display_name: draft.display_name.trim(),
      default_entry_node_id: draft.default_entry_node_id,
      locale: currentLocale
    });
  };

  return (
    <form
      className="im-account-page grid gap-4 mx-auto w-full max-w-[620px] p-[24px_28px]"
      onSubmit={onSubmit}
      aria-label="account-form"
    >
      <header>
        <h2 className="m-0 text-[22px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">
          {t("settings.account.title")}
        </h2>
        <p className="mt-1 text-[13px] text-[oklch(0.55_0.01_240)]">{profile.username}</p>
      </header>

      {errorDetail && (
        <div
          role="alert"
          className="rounded-[12px] border border-[oklch(0.78_0.15_25)] bg-[oklch(0.97_0.03_25)] px-4 py-3 text-sm text-[oklch(0.45_0.14_25)]"
        >
          {t("settings.account.actions.saveFailed", { detail: errorDetail })}
        </div>
      )}

      <section className="rounded-[14px] border border-[oklch(0.87_0.006_240)] bg-white p-[18px] grid gap-3">
        <header>
          <h3 className="m-0 text-[15px] font-extrabold text-[oklch(0.14_0.01_240)]">
            {t("settings.account.identity.heading")}
          </h3>
          <p className="mt-1 text-[12.5px] text-[oklch(0.55_0.01_240)]">
            {t("settings.account.identity.subtitle")}
          </p>
        </header>
        <div className="flex items-center gap-4 pb-1">
          <span
            data-testid="account-avatar"
            className="flex w-[54px] h-[54px] shrink-0 items-center justify-center rounded-full bg-[oklch(0.52_0.14_270)] text-white text-[20px] font-extrabold"
            aria-hidden="true"
          >
            {initialsOf(profile.display_name)}
          </span>
          <div className="min-w-0">
            <p className="m-0 text-[16px] font-extrabold text-[oklch(0.14_0.01_240)] truncate">
              {profile.display_name}
            </p>
            <p
              data-testid="account-user-id"
              className="m-0 mt-[3px] font-mono text-[12px] text-[oklch(0.55_0.01_240)] truncate"
            >
              {profile.user_id || profile.id}
            </p>
          </div>
        </div>
        <div className="grid gap-[14px] md:grid-cols-2">
          <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
            {t("settings.account.identity.userId")}
            <input className="im-input im-agent-input-mono" value={profile.user_id || profile.id} disabled />
          </label>
          <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
            {t("settings.account.identity.displayName")}
            <input
              className="im-input"
              value={draft.display_name}
              onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
              required
              minLength={1}
            />
          </label>
        </div>
      </section>

      <section className="rounded-[14px] border border-[oklch(0.87_0.006_240)] bg-white p-[18px] grid gap-3">
        <header>
          <h3 className="m-0 text-[15px] font-extrabold text-[oklch(0.14_0.01_240)]">
            {t("settings.account.defaults.heading")}
          </h3>
          <p className="mt-1 text-[12.5px] text-[oklch(0.55_0.01_240)]">
            {t("settings.account.defaults.subtitle")}
          </p>
        </header>
        <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
          {t("settings.account.defaults.defaultEntryNode")}
          <select
            className="im-input"
            value={draft.default_entry_node_id ?? ""}
            onChange={(event) =>
              setDraft({
                ...draft,
                default_entry_node_id: event.target.value.length > 0 ? event.target.value : null
              })
            }
          >
            <option value="">{t("settings.account.defaults.selectNode")}</option>
            {ownedNodeRows.map((node) => (
              <option key={node.node_id} value={node.node_id}>
                {node.alias || node.node_name} ({node.status})
              </option>
            ))}
          </select>
          <span className="text-[12px] text-[oklch(0.55_0.01_240)]">
            {t("settings.account.defaults.defaultEntryNodeHint")}
          </span>
        </label>
        <div className="grid gap-2">
          {ownedNodeRows.map((node) => {
            const isOnline = node.status === "online";
            const isDefault = node.node_id === draft.default_entry_node_id;
            return (
              <div
                key={node.node_id}
                data-testid={`account-owned-node-${node.node_id}`}
                className="flex items-center gap-3 rounded-[10px] border border-[oklch(0.87_0.006_240)] bg-[oklch(0.96_0.005_240)] px-3 py-[10px]"
              >
                <span
                  className={
                    "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11.5px] font-bold " +
                    (isOnline
                      ? "bg-[oklch(0.93_0.07_145)] text-[oklch(0.32_0.14_145)] border-[oklch(0.80_0.12_145)]"
                      : "bg-[oklch(0.92_0.005_240)] text-[oklch(0.50_0.01_240)] border-[oklch(0.85_0.005_240)]")
                  }
                >
                  <span
                    className={
                      "inline-block h-1.5 w-1.5 rounded-full " +
                      (isOnline ? "bg-[oklch(0.55_0.18_145)]" : "bg-[oklch(0.60_0.01_240)]")
                    }
                  />
                  {isOnline ? "online" : "offline"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="m-0 text-[13px] font-bold text-[oklch(0.18_0.01_240)] truncate">{node.alias || node.node_name}</p>
                  <p className="m-0 font-mono text-[11px] text-[oklch(0.55_0.01_240)] truncate">{node.node_id}</p>
                </div>
                <div className="text-right text-[12px] text-[oklch(0.55_0.01_240)]">
                  <p className="m-0">
                    {node.agent_count} {t("settings.account.defaults.agentsShort")}
                  </p>
                  <p className="m-0">v{node.version}</p>
                </div>
                {isDefault ? (
                  <span
                    data-testid={`account-owned-node-default-chip-${node.node_id}`}
                    className="rounded-full border border-[oklch(0.78_0.12_180)] bg-[oklch(0.93_0.06_180)] px-2 py-0.5 text-[11px] font-bold text-[oklch(0.35_0.12_180)]"
                  >
                    {t("settings.account.defaults.defaultChip")}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
        <div className="rounded-[8px] border border-[oklch(0.87_0.006_240)] bg-[oklch(0.96_0.005_240)] px-3 py-2 text-[12px] grid gap-1">
          <div className="flex justify-between text-[oklch(0.55_0.01_240)]">
            <span>{t("settings.account.defaults.ownedNodes")}</span>
            <span className="text-[oklch(0.30_0.01_240)] font-semibold">
              {profile.owned_node_ids.length > 0
                ? profile.owned_node_ids.join(", ")
                : t("settings.account.defaults.ownedNodesEmpty")}
            </span>
          </div>
          {profile.created_at ? (
            <div className="flex justify-between text-[oklch(0.55_0.01_240)]">
              <span>{t("settings.account.identity.createdAt")}</span>
              <span className="text-[oklch(0.30_0.01_240)] font-semibold">
                {new Date(profile.created_at).toLocaleDateString()}
              </span>
            </div>
          ) : null}
        </div>
      </section>

      <div
        data-testid="account-save-footer"
        className="flex items-center justify-between gap-3 rounded-[12px] border border-[oklch(0.87_0.006_240)] bg-white px-4 py-[14px]"
      >
        <span className="text-[12.5px] text-[oklch(0.60_0.01_240)]">
          {dirty ? (
            <span className="font-bold text-[oklch(0.50_0.15_60)]">● {t("settings.account.actions.savedJustNow") === "Saved." ? "Unsaved changes" : "有未保存改动"}</span>
          ) : null}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            className="im-btn im-btn-muted"
            disabled={!dirty || mutation.isPending}
            onClick={onDiscard}
          >
            {t("settings.account.actions.discard")}
          </button>
          <button
            type="submit"
            className="im-btn im-btn-primary"
            disabled={!dirty || mutation.isPending}
          >
            {mutation.isPending ? t("settings.account.actions.saving") : t("settings.account.actions.saveAccount")}
          </button>
        </div>
      </div>
    </form>
  );
}
