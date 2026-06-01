import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { PolicyProfile, getPolicies, updatePolicies } from "../im-settings-api";

// M2 restyle: 以 account-page.tsx 为 house-style 参考重写呈现层。
// 字段集、getPolicies/updatePolicies 调用、保存语义全部不动。

function isDirty(draft: PolicyProfile, saved: PolicyProfile): boolean {
  return (
    draft.default_model !== saved.default_model ||
    draft.audit_level !== saved.audit_level ||
    draft.max_turn_per_run !== saved.max_turn_per_run ||
    draft.rate_limit_per_min !== saved.rate_limit_per_min ||
    draft.max_attachment_size_mb !== saved.max_attachment_size_mb ||
    draft.retention_days !== saved.retention_days
  );
}

export function PoliciesPage() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["settings", "policies"],
    queryFn: getPolicies
  });

  const [draft, setDraft] = useState<PolicyProfile | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    if (query.data) {
      setDraft(query.data);
    }
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: (next: PolicyProfile) => updatePolicies(next),
    onSuccess: async () => {
      setErrorDetail(null);
      await queryClient.invalidateQueries({ queryKey: ["settings", "policies"] });
    },
    onError: (err: Error) => {
      setErrorDetail(err.message);
    }
  });

  if (!draft || !query.data) {
    return (
      <div className="flex flex-1 flex-col overflow-y-auto bg-[oklch(0.95_0.005_240)]">
        <p className="mx-auto mt-8 text-sm text-[oklch(0.55_0.01_240)]">{t("settings.policies.loading")}</p>
      </div>
    );
  }

  const dirty = isDirty(draft, query.data);

  const onDiscard = () => {
    setDraft(query.data!);
    setErrorDetail(null);
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!dirty || mutation.isPending) return;
    mutation.mutate(draft);
  };

  return (
    <div className="flex flex-1 flex-col overflow-y-auto bg-[oklch(0.95_0.005_240)]">
      {isMobile ? (
        <div className="sticky top-0 z-10 flex h-12 items-center gap-2 border-b border-[oklch(0.91_0.005_240)] bg-[oklch(0.97_0.004_240)] px-1">
          <Link
            data-testid="policies-page-back"
            to="/me"
            aria-label="Back"
            className="flex h-10 w-10 items-center justify-center rounded-[10px] text-[22px] text-[oklch(0.30_0.01_240)] hover:bg-[oklch(0.93_0.005_240)]"
          >
            ‹
          </Link>
          <h1 className="m-0 text-[16px] font-bold tracking-tight text-[oklch(0.14_0.01_240)]">{t("settings.policies.title")}</h1>
        </div>
      ) : null}
      <form
        className="im-policies-page grid gap-4 mx-auto w-full max-w-[620px]"
        style={{ padding: isMobile ? "16px 14px" : "24px 28px" }}
        onSubmit={onSubmit}
        aria-label="policies-form"
      >
        {!isMobile && (
          <header>
            <h2 className="m-0 text-[22px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)]">
              {t("settings.policies.title")}
            </h2>
            <p className="mt-1 text-[13px] text-[oklch(0.55_0.01_240)]">{t("settings.policies.subtitle")}</p>
          </header>
        )}

        {errorDetail && (
          <div
            role="alert"
            className="rounded-[12px] border border-[oklch(0.78_0.15_25)] bg-[oklch(0.97_0.03_25)] px-4 py-3 text-sm text-[oklch(0.45_0.14_25)]"
          >
            {t("settings.policies.actions.saveFailed", { detail: errorDetail })}
          </div>
        )}

        {/* 模型与审计卡 */}
        <section className="rounded-[14px] border border-[oklch(0.87_0.006_240)] bg-white p-[18px] grid gap-3">
          <div className="grid gap-[14px]">
            <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
              {t("settings.policies.fields.defaultModel")}
              <input
                className="im-input"
                value={draft.default_model}
                onChange={(event) => setDraft({ ...draft, default_model: event.target.value })}
              />
            </label>
            <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
              {t("settings.policies.fields.auditLevel")}
              <select
                className="im-input"
                value={draft.audit_level}
                onChange={(event) =>
                  setDraft({ ...draft, audit_level: event.target.value as PolicyProfile["audit_level"] })
                }
              >
                <option value="off">{t("settings.policies.fields.auditLevelOff")}</option>
                <option value="basic">{t("settings.policies.fields.auditLevelBasic")}</option>
                <option value="strict">{t("settings.policies.fields.auditLevelStrict")}</option>
              </select>
            </label>
          </div>
        </section>

        {/* 运行时限制卡 */}
        <section className="rounded-[14px] border border-[oklch(0.87_0.006_240)] bg-white p-[18px] grid gap-3 md:grid-cols-2">
          <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
            {t("settings.policies.fields.maxTurnPerRun")}
            <input
              className="im-input"
              type="number"
              value={draft.max_turn_per_run}
              onChange={(event) => setDraft({ ...draft, max_turn_per_run: Number(event.target.value) })}
            />
          </label>
          <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
            {t("settings.policies.fields.rateLimitPerMin")}
            <input
              className="im-input"
              type="number"
              value={draft.rate_limit_per_min}
              onChange={(event) => setDraft({ ...draft, rate_limit_per_min: Number(event.target.value) })}
            />
          </label>
          <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
            {t("settings.policies.fields.maxAttachmentSizeMb")}
            <input
              className="im-input"
              type="number"
              value={draft.max_attachment_size_mb}
              onChange={(event) => setDraft({ ...draft, max_attachment_size_mb: Number(event.target.value) })}
            />
          </label>
          <label className="grid gap-1 text-[13px] font-semibold text-[oklch(0.30_0.01_240)]">
            {t("settings.policies.fields.retentionDays")}
            <input
              className="im-input"
              type="number"
              value={draft.retention_days}
              onChange={(event) => setDraft({ ...draft, retention_days: Number(event.target.value) })}
            />
          </label>
        </section>

        {/* 保存区 */}
        <div
          data-testid="policies-save-footer"
          className="flex items-center justify-between gap-3 rounded-[12px] border border-[oklch(0.87_0.006_240)] bg-white px-4 py-[14px]"
        >
          <span className="text-[12.5px] text-[oklch(0.60_0.01_240)]">
            {dirty ? (
              <span className="font-bold text-[oklch(0.50_0.15_60)]">● {t("settings.policies.actions.unsavedChanges")}</span>
            ) : null}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              className="im-btn im-btn-muted"
              disabled={!dirty || mutation.isPending}
              onClick={onDiscard}
            >
              {t("settings.policies.actions.discard")}
            </button>
            <button
              type="submit"
              className="im-btn im-btn-primary"
              disabled={!dirty || mutation.isPending}
            >
              {mutation.isPending ? t("settings.policies.actions.saving") : t("settings.policies.actions.save")}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
