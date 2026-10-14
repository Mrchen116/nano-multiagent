import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import {
  getPolicies,
  updatePolicies,
  type PolicyProfile,
} from "../im-settings-api";
import { AttachmentCapacityPanel } from "./attachment-capacity-panel";
import "../settings-surfaces.css";

type Draft = Record<keyof PolicyProfile, string>;
const groups = [
  { key: "runtime", fields: ["default_model", "max_turn_per_run"] },
  { key: "safety", fields: ["audit_level", "rate_limit_per_min"] },
  { key: "storage", fields: ["max_attachment_size_mb", "retention_days"] },
] as const;
const labels: Record<keyof PolicyProfile, string> = {
  default_model: "defaultModel",
  max_turn_per_run: "maxTurnPerRun",
  audit_level: "auditLevel",
  rate_limit_per_min: "rateLimitPerMin",
  max_attachment_size_mb: "maxAttachmentSizeMb",
  retention_days: "retentionDays",
};
function toDraft(profile: PolicyProfile): Draft {
  return Object.fromEntries(
    Object.entries(profile).map(([key, value]) => [key, String(value)]),
  ) as Draft;
}
function validField(key: keyof PolicyProfile, value: string) {
  return key === "default_model"
    ? Boolean(value.trim())
    : key === "audit_level"
      ? ["off", "basic", "strict"].includes(value)
      : value.trim() !== "" &&
        Number.isInteger(Number(value)) &&
        Number(value) >= 1;
}

/** Render readable team presets while separating them from actual administrator storage data. */
export function PoliciesPage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const companyMember = user?.membership_status === "active";
  const admin = companyMember && Boolean(user?.is_company_admin);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["settings", "policies"],
    queryFn: getPolicies,
    enabled: companyMember,
    retry: false,
  });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saved, setSaved] = useState(false);
  const mutation = useMutation({
    mutationFn: updatePolicies,
    async onSuccess(updated) {
      // A pre-save read must not overwrite the response accepted by this save.
      await client.cancelQueries({
        queryKey: ["settings", "policies"],
        exact: true,
      });
      client.setQueryData(["settings", "policies"], updated);
      setDraft(null);
      setSaved(true);
    },
  });
  if (!companyMember) return <Navigate to="/membership" replace />;
  const baseline = query.data ? toDraft(query.data) : null;
  // Keep incomplete numeric input as text; a refetch never owns the user's draft.
  const values = draft ?? baseline;
  const dirty =
    values !== null &&
    baseline !== null &&
    (Object.keys(values) as Array<keyof Draft>).some(
      (key) => values[key].trim() !== baseline[key],
    );
  const valid =
    values !== null &&
    (Object.keys(values) as Array<keyof Draft>).every((key) =>
      validField(key, values[key]),
    );

  return (
    <section className="settings-surface im-policies-page">
      <div className="settings-frame">
        <Link
          className="settings-back"
          data-testid="policies-page-back"
          to="/me"
        >
          ‹ {t("computers.account")}
        </Link>
        <header className="settings-heading">
          <h1>{t("settings.policies.title")}</h1>
          <p>{t("settings.policies.subtitle")}</p>
        </header>
        {admin ? (
          <AttachmentCapacityPanel />
        ) : (
          <p className="settings-notice">{t("company.readOnly")}</p>
        )}
        <header className="settings-subheading">
          <h2>{t("settings.policies.presetsTitle")}</h2>
          <p>{t("settings.policies.presetsSubtitle")}</p>
        </header>
        <div className="settings-notice">
          <strong>{t("settings.policies.notAppliedTitle")}</strong>
          <p>{t("settings.policies.notAppliedHint")}</p>
          <Link className="settings-link" to="/settings/models">
            {t("settings.policies.manageModels")} →
          </Link>
        </div>
        {values ? (
          <form
            aria-label="policies-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!admin || !dirty || !valid || mutation.isPending) return;
              setSaved(false);
              mutation.mutate({
                default_model: values.default_model.trim(),
                audit_level: values.audit_level as PolicyProfile["audit_level"],
                max_turn_per_run: Number(values.max_turn_per_run),
                rate_limit_per_min: Number(values.rate_limit_per_min),
                max_attachment_size_mb: Number(values.max_attachment_size_mb),
                retention_days: Number(values.retention_days),
              });
            }}
          >
            {groups.map((group) => (
              <section
                className="settings-card settings-section"
                key={group.key}
              >
                <header>
                  <h2>{t(`settings.policies.groups.${group.key}.title`)}</h2>
                  <p>{t(`settings.policies.groups.${group.key}.hint`)}</p>
                </header>
                <div className="settings-section-content">
                  {group.fields.map((key) => {
                    const label = labels[key];
                    const fieldValid = validField(key, values[key]);
                    const id = `policy-${key}`;
                    return (
                      <div className="settings-policy-field" key={key}>
                        {admin ? (
                          <>
                            <label className="settings-field" htmlFor={id}>
                              {t(`settings.policies.fields.${label}`)}
                            </label>
                            {key === "audit_level" ? (
                              <select
                                className="im-input"
                                id={id}
                                value={values[key]}
                                disabled={mutation.isPending}
                                aria-describedby={`${id}-hint`}
                                onChange={(event) => {
                                  setDraft({
                                    ...values,
                                    [key]: event.target.value,
                                  });
                                  setSaved(false);
                                  mutation.reset();
                                }}
                              >
                                {["off", "basic", "strict"].map((level) => (
                                  <option key={level} value={level}>
                                    {t(`settings.policies.audit.${level}`)}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <input
                                className="im-input"
                                id={id}
                                type={
                                  key === "default_model" ? "text" : "number"
                                }
                                required
                                min={key === "default_model" ? undefined : 1}
                                step={key === "default_model" ? undefined : 1}
                                value={values[key]}
                                disabled={mutation.isPending}
                                aria-invalid={!fieldValid}
                                aria-describedby={`${id}-hint`}
                                onChange={(event) => {
                                  setDraft({
                                    ...values,
                                    [key]: event.target.value,
                                  });
                                  setSaved(false);
                                  mutation.reset();
                                }}
                              />
                            )}
                          </>
                        ) : (
                          <>
                            <h3 className="settings-field">
                              {t(`settings.policies.fields.${label}`)}
                            </h3>
                            <p className="settings-readonly">
                              {key === "audit_level"
                                ? t(`settings.policies.audit.${values[key]}`)
                                : values[key]}
                            </p>
                          </>
                        )}
                        <p
                          id={`${id}-hint`}
                          className={`settings-field-hint ${!fieldValid ? "settings-error-text" : ""}`}
                        >
                          {t(
                            fieldValid
                              ? `settings.policies.hints.${key}`
                              : key === "default_model"
                                ? "settings.surface.modelRequired"
                                : "settings.surface.positiveInteger",
                          )}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
            {admin && (
              <footer className="settings-save">
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
                    {t("settings.policies.actions.discard")}
                  </button>
                  <button
                    className="im-btn im-btn-primary"
                    type="submit"
                    disabled={!dirty || !valid || mutation.isPending}
                  >
                    {t(
                      mutation.isPending
                        ? "settings.policies.actions.saving"
                        : "settings.policies.actions.save",
                    )}
                  </button>
                </div>
              </footer>
            )}
          </form>
        ) : (
          <div className="settings-card settings-state">
            {query.isError ? (
              <>
                <p role="alert">{t("settings.surface.loadFailed")}</p>
                <button
                  className="im-btn im-btn-muted"
                  onClick={() => void query.refetch()}
                >
                  {t("common.retry")}
                </button>
              </>
            ) : (
              <p role="status">{t("settings.policies.loading")}</p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
