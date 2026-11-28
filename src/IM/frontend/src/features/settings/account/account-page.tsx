import { Avatar, AvatarIdentities } from "../../chat/components/avatar";
import { evictUserAvatarBlobs } from "../../chat/components/avatar-blob-store";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { getCurrentLanguage, useTranslation } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import {
  SettingsRequestError,
  deleteAccountAvatar,
  getAccount,
  updateAccount,
  uploadAccountAvatar,
  type AccountProfile,
} from "../im-settings-api";
import {
  AvatarCropDialog,
  loadAvatarImageSource,
  type PreparedAvatarSource,
} from "./avatar-crop-dialog";
import "../settings-surfaces.css";

const MAX_AVATAR_FILE_BYTES = 5 * 1024 * 1024;
const ALLOWED_AVATAR_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

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
  const [avatarFeedback, setAvatarFeedback] = useState<{
    kind: "ok" | "error";
    message: string;
  } | null>(null);
  const [cropState, setCropState] = useState<{
    file: File;
    prepared: PreparedAvatarSource;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadButtonRef = useRef<HTMLButtonElement | null>(null);
  const pendingCleanupRef = useRef<(() => void) | null>(null);

  const releasePendingCropUrl = useCallback(() => {
    if (pendingCleanupRef.current) {
      pendingCleanupRef.current();
      pendingCleanupRef.current = null;
    }
  }, []);

  useEffect(() => () => releasePendingCropUrl(), [releasePendingCropUrl]);

  const profile = query.data;
  useEffect(() => {
    if (!profile || profile.avatar_version === undefined) return;
    const current = useAuthStore.getState().user;
    const uid = profile.user_id || profile.id;
    if (current && current.id === uid && current.avatar_version !== profile.avatar_version) {
      useAuthStore.getState().replaceUser({
        ...current,
        avatar_version: profile.avatar_version,
      });
    }
  }, [profile]);

  const applyAvatarProfileUpdate = useCallback(
    async (updated: AccountProfile) => {
      await client.cancelQueries({ queryKey: ["settings", "account"], exact: true });
      client.setQueryData(["settings", "account"], updated);
      const uid = updated.user_id || updated.id;
      const nextVersion = updated.avatar_version ?? null;
      evictUserAvatarBlobs(uid, nextVersion);
      const current = useAuthStore.getState().user;
      if (current && current.id === uid) {
        useAuthStore.getState().replaceUser({
          ...current,
          avatar_version: nextVersion,
        });
      }
      void client.invalidateQueries({ queryKey: ["contacts"] });
      void client.invalidateQueries({ queryKey: ["company", "members"] });
    },
    [client],
  );

  const formatAvatarMutationError = useCallback(
    (error: unknown) => {
      if (error instanceof SettingsRequestError) {
        if (error.status === 413 || error.status === 415 || error.status === 422) {
          return t("settings.account.avatar.invalidFileError");
        }
        if (error.status === 429) {
          return t("settings.account.avatar.rateLimitedError");
        }
      }
      return t("settings.account.avatar.saveError");
    },
    [t],
  );

  const uploadAvatarMutation = useMutation({
    mutationFn: uploadAccountAvatar,
    async onSuccess(updated) {
      releasePendingCropUrl();
      setCropState(null);
      await applyAvatarProfileUpdate(updated);
      setAvatarFeedback({
        kind: "ok",
        message: t("settings.account.avatar.updatedStatus"),
      });
    },
    onError(error) {
      releasePendingCropUrl();
      setCropState(null);
      setAvatarFeedback({
        kind: "error",
        message: formatAvatarMutationError(error),
      });
    },
  });

  const removeAvatarMutation = useMutation({
    mutationFn: deleteAccountAvatar,
    async onSuccess(updated) {
      await applyAvatarProfileUpdate(updated);
      setAvatarFeedback({
        kind: "ok",
        message: t("settings.account.avatar.removedStatus"),
      });
    },
    onError(error) {
      setAvatarFeedback({
        kind: "error",
        message: formatAvatarMutationError(error),
      });
    },
  });

  const avatarBusy = uploadAvatarMutation.isPending || removeAvatarMutation.isPending;

  const openFilePicker = () => {
    if (avatarBusy) return;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size === 0) {
      setAvatarFeedback({
        kind: "error",
        message: t("settings.account.avatar.emptyError"),
      });
      return;
    }
    if (!ALLOWED_AVATAR_TYPES.has(file.type) || file.size > MAX_AVATAR_FILE_BYTES) {
      setAvatarFeedback({
        kind: "error",
        message: t("settings.account.avatar.invalidFileError"),
      });
      return;
    }
    releasePendingCropUrl();
    try {
      const { prepared, cleanup } = await loadAvatarImageSource(file);
      pendingCleanupRef.current = cleanup;
      setAvatarFeedback(null);
      setCropState({ file, prepared });
    } catch {
      releasePendingCropUrl();
      setAvatarFeedback({
        kind: "error",
        message: t("settings.account.avatar.decodeError"),
      });
    }
  };

  const name = draft ?? profile?.display_name ?? "";
  const dirty = profile !== undefined && name.trim() !== profile.display_name;
  const valid = name.trim().length > 0;
  const mutation = useMutation({
    mutationFn: updateAccount,
    async onSuccess(updated) {
      // A pre-save read must not overwrite the response accepted by this save.
      await client.cancelQueries({
        queryKey: ["settings", "account"],
        exact: true,
      });
      client.setQueryData(["settings", "account"], updated);
      const current = useAuthStore.getState().user;
      if (current)
        useAuthStore.getState().replaceUser({
          ...current,
          display_name: updated.display_name,
          locale: updated.locale,
          ...(updated.avatar_version !== undefined
            ? { avatar_version: updated.avatar_version }
            : {}),
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
  const profileUserId = profile?.user_id || profile?.id || authUser?.id || "";
  const effectiveAvatarVersion =
    profile?.avatar_version !== undefined
      ? profile.avatar_version
      : authUser?.avatar_version ?? null;
  const hasCustomAvatar = Boolean(effectiveAvatarVersion);

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
                <AvatarIdentities
                  source="names"
                  actors={[
                    {
                      type: "user",
                      id: profileUserId,
                      user_id: profileUserId,
                      display_name: displayName || profile.username,
                      avatar_version: effectiveAvatarVersion,
                    },
                  ]}
                >
                  <div className="settings-identity account-identity-editor">
                    <button
                      type="button"
                      className="account-avatar-trigger"
                      data-testid="account-avatar-trigger"
                      aria-label={t("settings.account.avatar.changeTrigger")}
                      title={t("settings.account.avatar.changeTrigger")}
                      disabled={avatarBusy}
                      onClick={openFilePicker}
                    >
                      <span data-testid="account-avatar">
                        <Avatar id={profileUserId} size={56} />
                      </span>
                    </button>
                    <div className="account-identity-meta">
                      <strong>{displayName}</strong>
                      <span>@{profile.username}</span>
                    </div>
                    <div className="account-avatar-actions">
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        hidden
                        data-testid="account-avatar-file-input"
                        onChange={(event) => void handleFileChange(event)}
                      />
                      <button
                        ref={uploadButtonRef}
                        type="button"
                        className="im-btn im-btn-muted"
                        data-testid="account-avatar-upload-btn"
                        disabled={avatarBusy}
                        onClick={openFilePicker}
                      >
                        {t(
                          hasCustomAvatar
                            ? "settings.account.avatar.change"
                            : "settings.account.avatar.upload",
                        )}
                      </button>
                      {hasCustomAvatar && (
                        <button
                          type="button"
                          className="im-btn im-btn-danger-ghost"
                          data-testid="account-avatar-remove-btn"
                          disabled={avatarBusy}
                          onClick={() => {
                            setAvatarFeedback(null);
                            removeAvatarMutation.mutate();
                          }}
                        >
                          {t("settings.account.avatar.remove")}
                        </button>
                      )}
                    </div>
                  </div>
                </AvatarIdentities>
                {avatarFeedback && (
                  <p
                    role={avatarFeedback.kind === "error" ? "alert" : "status"}
                    data-testid="account-avatar-feedback"
                    className={`avatar-inline-feedback avatar-inline-feedback--${avatarFeedback.kind}`}
                  >
                    {avatarFeedback.message}
                  </p>
                )}
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
        <AvatarCropDialog
          open={Boolean(cropState)}
          prepared={cropState?.prepared ?? null}
          sourceFile={cropState?.file ?? null}
          saving={uploadAvatarMutation.isPending}
          returnFocusRef={uploadButtonRef}
          onReselect={openFilePicker}
          onCancel={() => {
            releasePendingCropUrl();
            setCropState(null);
          }}
          onConfirm={(blob) => {
            uploadAvatarMutation.mutate(blob);
          }}
        />
      </div>
    </section>
  );
}
