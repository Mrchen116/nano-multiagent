import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { setLanguage, useTranslation, type Locale } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { useNotificationPreference } from "../../notifications/notification-preference";
import {
  AccountProfile,
  UpdateAccountInput,
  getAccount,
  listNodes,
  updateAccount
} from "../im-settings-api";

interface DraftState {
  display_name: string;
  default_entry_node_id: string | null;
  locale: Locale;
}

function toDraft(profile: AccountProfile): DraftState {
  const locale: Locale = profile.locale === "zh" ? "zh" : "en";
  return {
    display_name: profile.display_name,
    default_entry_node_id: profile.default_entry_node_id,
    locale
  };
}

function isDirty(draft: DraftState, profile: AccountProfile, notificationsDirty: boolean): boolean {
  return (
    draft.display_name !== profile.display_name ||
    draft.default_entry_node_id !== profile.default_entry_node_id ||
    draft.locale !== (profile.locale === "zh" ? "zh" : "en") ||
    notificationsDirty
  );
}

export function AccountPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const accountQuery = useQuery({ queryKey: ["settings", "account"], queryFn: getAccount });
  const nodesQuery = useQuery({ queryKey: ["settings", "nodes"], queryFn: listNodes });

  const profile = accountQuery.data;
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [notificationsPref, setNotificationsPref] = useNotificationPreference();
  const [initialNotifications, setInitialNotifications] = useState<boolean | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    if (profile) {
      setDraft(toDraft(profile));
    }
  }, [profile]);

  useEffect(() => {
    if (initialNotifications === null) {
      setInitialNotifications(notificationsPref);
    }
  }, [initialNotifications, notificationsPref]);

  const ownedNodeOptions = useMemo(() => {
    if (!profile) return [];
    return (nodesQuery.data ?? []).filter((node) => profile.owned_node_ids.includes(node.node_id));
  }, [profile, nodesQuery.data]);

  const mutation = useMutation({
    mutationFn: async (input: UpdateAccountInput) => updateAccount(input),
    onSuccess: async (updated) => {
      // Sync auth-store user so display_name + locale stay consistent across the shell.
      const auth = useAuthStore.getState();
      if (auth.user) {
        auth.setSession({
          access_token: auth.accessToken ?? "",
          refresh_token: auth.refreshToken ?? "",
          user: { ...auth.user, display_name: updated.display_name, locale: updated.locale }
        });
      }
      setLanguage(updated.locale === "zh" ? "zh" : "en");
      setInitialNotifications(notificationsPref);
      setErrorDetail(null);
      await queryClient.invalidateQueries({ queryKey: ["settings", "account"] });
    },
    onError: (err: Error) => {
      setErrorDetail(err.message);
    }
  });

  if (!draft || !profile) {
    return <p className="text-sm text-slate-500">{t("common.loading")}</p>;
  }

  const notificationsDirty = initialNotifications !== null && initialNotifications !== notificationsPref;
  const dirty = isDirty(draft, profile, notificationsDirty);

  const onDiscard = () => {
    setDraft(toDraft(profile));
    if (initialNotifications !== null && initialNotifications !== notificationsPref) {
      setNotificationsPref(initialNotifications);
    }
    setErrorDetail(null);
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!dirty || mutation.isPending) return;
    mutation.mutate({
      display_name: draft.display_name.trim(),
      default_entry_node_id: draft.default_entry_node_id,
      locale: draft.locale
    });
    // Trigger notification permission prompt the first time the user opts in.
    if (notificationsPref && typeof window !== "undefined" && "Notification" in window) {
      const w = window as Window & {
        Notification: { permission: NotificationPermission; requestPermission: () => Promise<NotificationPermission> };
      };
      if (w.Notification.permission === "default") {
        void w.Notification.requestPermission();
      }
    }
  };

  return (
    <form className="im-account-page grid gap-4" onSubmit={onSubmit} aria-label="account-form">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h2 className="im-title text-xl font-bold">{t("settings.account.title")}</h2>
          <p className="im-section-copy">{profile.username}</p>
        </div>
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
            {mutation.isPending ? t("settings.account.actions.saving") : t("settings.account.actions.save")}
          </button>
        </div>
      </header>

      {errorDetail && (
        <div role="alert" className="im-section-card text-sm" style={{ borderColor: "var(--im-danger, #c33)" }}>
          {t("settings.account.actions.saveFailed", { detail: errorDetail })}
        </div>
      )}

      <section className="im-section-card">
        <header>
          <h3 className="im-section-heading">{t("settings.account.identity.heading")}</h3>
          <p className="im-section-copy">{t("settings.account.identity.subtitle")}</p>
        </header>
        <label className="grid gap-1 text-xs font-semibold text-slate-600">
          {t("settings.account.identity.displayName")}
          <input
            className="im-input"
            value={draft.display_name}
            onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
            required
            minLength={1}
          />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-slate-600">
          {t("settings.account.identity.username")}
          <input className="im-input" value={profile.username} disabled />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-slate-600">
          {t("settings.account.identity.userId")}
          <input className="im-input" value={profile.user_id || profile.id} disabled />
        </label>
        <p className="im-section-copy">
          {t("settings.account.identity.createdAt")}: {profile.created_at || "-"}
        </p>
      </section>

      <section className="im-section-card">
        <header>
          <h3 className="im-section-heading">{t("settings.account.defaults.heading")}</h3>
          <p className="im-section-copy">{t("settings.account.defaults.subtitle")}</p>
        </header>
        <label className="grid gap-1 text-xs font-semibold text-slate-600">
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
            {ownedNodeOptions.map((node) => (
              <option key={node.node_id} value={node.node_id}>
                {node.alias || node.node_name} ({node.status})
              </option>
            ))}
          </select>
          <span className="im-section-copy">{t("settings.account.defaults.defaultEntryNodeHint")}</span>
        </label>
        <p className="im-section-copy">
          {t("settings.account.defaults.ownedNodes")}:{" "}
          {profile.owned_node_ids.length > 0
            ? profile.owned_node_ids.join(", ")
            : t("settings.account.defaults.ownedNodesEmpty")}
        </p>
      </section>

      <section className="im-section-card">
        <header>
          <h3 className="im-section-heading">{t("settings.account.preferences.heading")}</h3>
          <p className="im-section-copy">{t("settings.account.preferences.subtitle")}</p>
        </header>
        <fieldset className="grid gap-1 text-xs font-semibold text-slate-600">
          <legend>{t("settings.account.preferences.language")}</legend>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="account-locale"
              value="en"
              checked={draft.locale === "en"}
              onChange={() => setDraft({ ...draft, locale: "en" })}
            />
            {t("me.language.en")}
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="account-locale"
              value="zh"
              checked={draft.locale === "zh"}
              onChange={() => setDraft({ ...draft, locale: "zh" })}
            />
            {t("me.language.zh")}
          </label>
        </fieldset>
        <label className="flex items-start gap-2 text-xs font-semibold text-slate-600">
          <input
            type="checkbox"
            checked={notificationsPref}
            onChange={(event) => setNotificationsPref(event.target.checked)}
          />
          <span>
            {t("settings.account.preferences.notifications")}
            <span className="block font-normal im-section-copy">
              {t("settings.account.preferences.notificationsHint")}
            </span>
          </span>
        </label>
      </section>
    </form>
  );
}
