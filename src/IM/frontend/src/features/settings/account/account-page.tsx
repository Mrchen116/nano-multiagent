import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getCurrentLanguage, useTranslation } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { getAccount, updateAccount } from "../im-settings-api";
import "../settings-surfaces.css";

/** Render personal identity editing and the account's space and management destinations. */
export function AccountPage() {
  const { t } = useTranslation();
  const authUser = useAuthStore((s) => s.user);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["settings", "account"],
    queryFn: getAccount,
    retry: false,
  });
  // A draft belongs to the editor, so background query refreshes cannot replace it.
  const [draft, setDraft] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const profile = query.data;
  const name = draft ?? profile?.display_name ?? "";
  const dirty = profile !== undefined && name.trim() !== profile.display_name;
  const valid = name.trim().length > 0;
  const mutation = useMutation({
    mutationFn: updateAccount,
    onSuccess(updated) {
      client.setQueryData(["settings", "account"], updated);
      const current = useAuthStore.getState().user;
      if (current)
        useAuthStore
          .getState()
          .replaceUser({
            ...current,
            display_name: updated.display_name,
            locale: updated.locale,
          });
      setDraft(null);
      setSaved(true);
    },
  });
  const member = authUser?.membership_status ?? "none";
  const teamState =
    member === "active"
      ? authUser?.is_company_admin
        ? "admin"
        : "member"
      : member;
  const personal = Boolean(authUser?.personal_space_enabled);
  const computerCount = (
    profile?.owned_node_ids ??
    authUser?.owned_node_ids ??
    []
  ).length;
  const displayName = profile?.display_name ?? authUser?.display_name ?? "";

  return (
    <section className="settings-surface im-account-page">
      <div className="settings-frame">
        <Link
          className="settings-back"
          data-testid="account-page-back"
          to="/me"
        >
          ‹ {t("computers.account")}
        </Link>
        <header className="settings-heading">
          <h1>{t("settings.account.title")}</h1>
          <p>{t("settings.account.subtitle")}</p>
        </header>
        {profile ? (
          <form
            aria-label="account-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!dirty || !valid || mutation.isPending) return;
              setSaved(false);
              mutation.mutate({
                display_name: name.trim(),
                default_entry_node_id: profile.default_entry_node_id,
                locale: profile.locale,
              });
            }}
          >
            <section className="settings-card settings-section">
              <header>
                <h2>{t("settings.account.identity.heading")}</h2>
                <p>{t("settings.account.identity.subtitle")}</p>
              </header>
              <div className="settings-section-content">
                <div className="settings-identity">
                  <span
                    className="settings-avatar"
                    aria-hidden="true"
                    data-testid="account-avatar"
                  >
                    {(displayName || "U").trim().slice(0, 2).toUpperCase()}
                  </span>
                  <div>
                    <strong>{displayName}</strong>
                    <span>@{profile.username}</span>
                  </div>
                </div>
                <label
                  className="settings-field"
                  htmlFor="account-display-name"
                >
                  {t("settings.account.identity.displayName")}
                </label>
                <input
                  id="account-display-name"
                  className="im-input"
                  value={name}
                  disabled={mutation.isPending}
                  required
                  maxLength={128}
                  aria-invalid={!valid}
                  aria-describedby="account-name-hint"
                  onChange={(event) => {
                    setDraft(event.target.value);
                    setSaved(false);
                    mutation.reset();
                  }}
                />
                <p
                  id="account-name-hint"
                  className={`settings-field-hint ${!valid ? "settings-error-text" : ""}`}
                >
                  {t(
                    valid
                      ? "settings.account.identity.displayNameHint"
                      : "settings.surface.nameRequired",
                  )}
                </p>
                <details className="settings-details">
                  <summary>{t("settings.account.identity.details")}</summary>
                  <dl className="settings-metadata">
                    <dt>{t("settings.account.identity.userId")}</dt>
                    <dd data-testid="account-user-id">
                      {profile.user_id || profile.id}
                    </dd>
                    {profile.created_at && (
                      <>
                        <dt>{t("settings.account.identity.createdAt")}</dt>
                        <dd>
                          {new Date(profile.created_at).toLocaleDateString(
                            getCurrentLanguage(),
                          )}
                        </dd>
                      </>
                    )}
                  </dl>
                </details>
              </div>
            </section>
            <footer className="settings-save" data-testid="account-save-footer">
              <p
                role={mutation.isError ? "alert" : "status"}
                className={
                  mutation.isError
                    ? "settings-error-text"
                    : saved
                      ? "settings-success-text"
                      : ""
                }
              >
                {t(
                  mutation.isError
                    ? "settings.surface.saveFailed"
                    : saved
                      ? "settings.surface.saved"
                      : dirty
                        ? "settings.surface.unsaved"
                        : "settings.surface.unchanged",
                )}
              </p>
              <div>
                <button
                  className="im-btn im-btn-muted"
                  type="button"
                  disabled={!dirty || mutation.isPending}
                  onClick={() => {
                    setDraft(null);
                    setSaved(false);
                    mutation.reset();
                  }}
                >
                  {t("settings.account.actions.discard")}
                </button>
                <button
                  className="im-btn im-btn-primary"
                  type="submit"
                  disabled={!dirty || !valid || mutation.isPending}
                >
                  {t(
                    mutation.isPending
                      ? "settings.account.actions.saving"
                      : "settings.account.actions.saveAccount",
                  )}
                </button>
              </div>
            </footer>
          </form>
        ) : (
          <div className="settings-card settings-state">
            {query.isError ? (
              <>
                <p role="alert">{t("settings.surface.loadFailed")}</p>
                <button
                  type="button"
                  className="im-btn im-btn-muted"
                  onClick={() => void query.refetch()}
                >
                  {t("common.retry")}
                </button>
              </>
            ) : (
              <p role="status">{t("common.loading")}</p>
            )}
          </div>
        )}

        <section className="settings-card settings-section">
          <header>
            <h2>{t("settings.account.spaces.heading")}</h2>
            <p>{t("settings.account.spaces.subtitle")}</p>
          </header>
          <div className="settings-section-content">
            <div className="settings-row">
              <div>
                <h3>
                  {t("settings.account.spaces.personal")}{" "}
                  <span
                    className={`settings-badge ${personal ? "" : "neutral"}`}
                  >
                    {t(
                      personal
                        ? "settings.account.spaces.available"
                        : "settings.account.spaces.unavailable",
                    )}
                  </span>
                </h3>
                <p>
                  {t(
                    personal
                      ? "settings.account.spaces.personalHint"
                      : "settings.account.spaces.companyOnly",
                  )}
                </p>
              </div>
            </div>
            <div className="settings-row">
              <div>
                <h3>
                  {t("settings.account.spaces.team")}{" "}
                  <span
                    className={`settings-badge ${member === "active" ? "" : "neutral"}`}
                  >
                    {t(`settings.account.spaces.states.${teamState}`)}
                  </span>
                </h3>
                <p>{t(`settings.account.spaces.hints.${member}`)}</p>
              </div>
              {member !== "active" ? (
                <Link
                  className="settings-link"
                  to="/membership"
                  state={{ from: "/settings/account" }}
                >
                  {t(
                    member === "none"
                      ? "settings.account.spaces.join"
                      : member === "pending"
                        ? "settings.account.spaces.application"
                        : "settings.account.spaces.membership",
                  )}{" "}
                  →
                </Link>
              ) : authUser?.is_company_admin ? (
                <Link className="settings-link" to="/settings/company">
                  {t("settings.account.spaces.manageMembers")} →
                </Link>
              ) : null}
            </div>
          </div>
        </section>
        <section className="settings-card settings-section">
          <header>
            <h2>{t("settings.account.linked.heading")}</h2>
            <p>{t("settings.account.linked.subtitle")}</p>
          </header>
          <div className="settings-section-content">
            <div className="settings-row">
              <div>
                <h3>{t("settings.account.linked.computers")}</h3>
                <p>
                  {t(
                    computerCount
                      ? "settings.account.linked.summary"
                      : "settings.account.linked.empty",
                    { count: computerCount },
                  )}
                </p>
              </div>
              <Link className="settings-link" to="/settings/nodes">
                {t("settings.account.linked.manage")} →
              </Link>
            </div>
            {computerCount === 0 && (
              <Link
                className="settings-link settings-setup-link"
                to="/onboarding"
              >
                {t("onboarding.continue")} →
              </Link>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
