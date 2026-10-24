import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import {
  CHANNEL_PROVIDERS,
  ChannelProviderDescriptor,
  ChannelProviderFormState,
  ChannelText,
  initialProviderForm,
  providerById,
  providerDiagnosticsHref,
  providerRemovalSummary,
  providerSummary,
  serializeProviderForm,
  textKey,
  validateProviderForm,
} from "./channel-provider-registry";
import {
  AgentChannel,
  AgentChannelRemoval,
  AgentChannelResource,
  ChannelDiagnosticCheck,
  CreateAgentChannelInput,
  createAgentChannel,
  deleteAgentChannel,
  listAgentChannels,
  reconnectAgentChannel,
  retryAgentChannelRemoval,
  updateAgentChannel,
} from "./im-agent-config-api";

export { CHANNEL_PROVIDERS } from "./channel-provider-registry";
export type { ChannelProviderDescriptor } from "./channel-provider-registry";

function formatTime(value: string | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function errorDetail(error: unknown): string {
  if (!(error instanceof Error)) return "Unknown error";
  return error.message.split(" failed: ").at(-1) ?? error.message;
}

function isRemoval(resource: AgentChannelResource): resource is AgentChannelRemoval {
  return "resource_type" in resource && resource.resource_type === "removal";
}

interface RequestErrorState {
  message: string;
  removalId: string | null;
}

function diagnosticScopes(check: ChannelDiagnosticCheck): string[] {
  if (check.required.recommended_scopes.length > 0) {
    return check.required.recommended_scopes;
  }
  return [...new Set(check.required.accepted_scope_sets.flat())];
}

function DiagnosticsPanel({
  channel,
  provider,
}: {
  channel: AgentChannel;
  provider: ChannelProviderDescriptor;
}) {
  const { t } = useTranslation();
  const state = channel.observed?.diagnostics_state;
  if (state !== "limited" && state !== "unknown") return null;
  const limited = state === "limited";
  const checks = (channel.observed?.checks ?? []).filter(
    (check) => check.state !== "satisfied",
  );
  const diagnostics = provider.diagnostics;
  const diagnosticsHref = providerDiagnosticsHref(provider, channel);
  return (
    <section
      className={`im-channel-diagnostics ${limited ? "im-channel-diagnostics--limited" : "im-channel-diagnostics--unknown"}`}
      data-diagnostics-state={state}
      role="status"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <strong className="text-sm text-slate-900">
            {t(`agents.channels.diagnostics.${state}.title`)}
          </strong>
          <p className="m-0 mt-1 text-xs leading-5 text-slate-600">
            {t(`agents.channels.diagnostics.${state}.detail`)}
          </p>
        </div>
        {diagnostics && diagnosticsHref ? (
          <a
            className="text-xs font-semibold text-blue-700 underline"
            href={diagnosticsHref}
            target="_blank"
            rel="noreferrer"
          >
            {t(textKey(diagnostics.linkLabel))} ↗
          </a>
        ) : null}
      </div>
      {checks.length > 0 ? (
        <div className="grid gap-2">
          {checks.map((check) => {
            const missing = check.state === "missing";
            const effectOverride = diagnostics?.effectOverrides[check.check_id];
            const effect = effectOverride ? t(textKey(effectOverride)) : check.effect;
            return (
              <article
                className="grid gap-2 rounded-lg border border-slate-200 bg-white/80 p-3"
                data-diagnostic-check={check.check_id}
                key={check.check_id}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <code className="text-[11px] font-semibold text-slate-700">{check.check_id}</code>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${missing ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600"}`}>
                    {t(`agents.channels.diagnostics.checkState.${check.state}`)}
                  </span>
                </div>
                <div
                  className="flex flex-wrap gap-1.5"
                  aria-label={diagnostics
                    ? t(textKey(diagnostics.scopeLabel))
                    : t("agents.channels.diagnostics.rawScopes")}
                >
                  {diagnosticScopes(check).map((scope) => (
                    <code className="im-channel-scope" key={scope}>{scope}</code>
                  ))}
                </div>
                {check.state === "unknown" ? (
                  <p className="m-0 text-xs font-semibold text-slate-600">
                    {t("agents.channels.diagnostics.checkUnknown")}
                  </p>
                ) : null}
                <dl className="m-0 grid gap-1 text-xs leading-5 text-slate-600">
                  <div><dt className="inline font-semibold text-slate-800">{t("agents.channels.diagnostics.effect")}</dt><dd className="m-0 inline"> · {effect}</dd></div>
                  <div><dt className="inline font-semibold text-slate-800">{t("agents.channels.diagnostics.remediation")}</dt><dd className="m-0 inline"> · {check.remediation}</dd></div>
                </dl>
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

interface ConnectionCardProps {
  channel: AgentChannel;
  provider: ChannelProviderDescriptor;
  manualReconnecting: boolean;
  offline: boolean;
  connectionUnknown: boolean;
  pending: boolean;
  onEdit(): void;
  onReconnect(): void;
  onToggle(): void;
  onDelete(): void;
}

function ConnectionCard({
  channel,
  provider,
  manualReconnecting,
  offline,
  connectionUnknown,
  pending,
  onEdit,
  onReconnect,
  onToggle,
  onDelete,
}: ConnectionCardProps) {
  const { t, i18n } = useTranslation();
  const unknownLabel = i18n.language.startsWith("zh") ? "连接未确认" : "Connection unconfirmed";
  const observed = channel.observed;
  const observedState = observed?.connection_state ?? "pending";
  const applyFailed = channel.sync_state === "failed" && channel.apply_error !== null;
  const waiting = channel.sync_state === "pending";
  // The agent list can learn that a node went offline before the cached channel
  // query is invalidated.  The live node state is therefore authoritative for
  // whether any observed connection may still be presented as current.
  const stale = observed !== null && (offline || observed.status_stale === true);
  const state = manualReconnecting
    ? "reconnecting"
    : applyFailed
      ? "failed"
    : waiting
    ? channel.enabled
      ? offline ? "pending" : "connecting"
      : "disabling"
    : stale
      ? "offline"
    : observedState === "failed"
      ? "failed"
    : !channel.enabled || observedState === "disabled"
      ? "disabled"
      : observedState;
  const connected = state === "connected";
  const failed = state === "failed";
  const disabled = state === "disabled";
  const lastKnownState = observedState === "connected" && observed?.diagnostics_state === "limited"
    ? t("agents.channels.diagnostics.limited.title")
    : t(`agents.channels.status.${observedState}`);
  const statusLabel = connectionUnknown && state === "offline" ? unknownLabel : t(`agents.channels.status.${state}`);
  const statusClass = connected
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : failed
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : disabled
        ? "border-slate-200 bg-slate-100 text-slate-700"
        : "border-amber-200 bg-amber-50 text-amber-700";

  const detail = state === "pending"
    ? { strong: t("agents.channels.status.saved"), copy: t("agents.channels.status.autoApply") }
    : state === "offline"
      ? {
        strong: t("agents.channels.status.lastKnown"),
        copy: t("agents.channels.status.lastKnownDetail", { status: lastKnownState }),
      }
    : state === "disabling"
      ? { strong: t("agents.channels.status.disableSaved"), copy: t("agents.channels.status.disableWaiting") }
      : state === "disabled"
        ? { strong: t("agents.channels.status.disabledApplied"), copy: t("agents.channels.status.disabledDetail") }
        : state === "reconnecting"
          ? { strong: t("agents.channels.status.connectionInterrupted"), copy: t("agents.channels.status.autoRecover") }
          : failed
            ? {
              strong: t("agents.channels.status.failed"),
              copy: channel.apply_error?.message || observed?.status_message || observed?.status_code || t("agents.channels.status.unknownFailure"),
            }
            : connected
              ? { strong: t("agents.channels.status.synced"), copy: t("agents.channels.status.applied") }
              : {
                strong: t("agents.channels.status.savedSecurely"),
                copy: t(textKey(provider.connectingDetail)),
              };

  return (
    <article className="im-agent-card im-channel-card" data-channel-state={state}>
      <div className="im-channel-card-head">
        <span className="im-channel-provider-logo">
          {provider.icon}
        </span>
        <div className="im-channel-card-copy min-w-[180px] flex-1">
          <div className="flex items-center gap-2">
            <h3 className="m-0 text-[14px] font-bold text-slate-900">
              {t(textKey(provider.label))}
            </h3>
            <span className={`im-channel-status-pill ${statusClass}`}>{statusLabel}</span>
          </div>
          <p className="im-channel-card-meta">
            {provider.summary.label} · {providerSummary(provider, channel)}
            {disabled ? ` · ${t("agents.channels.status.credentialsRetained")}` : null}
          </p>
        </div>
        <div className="im-channel-actions flex flex-wrap gap-2" data-testid="channel-actions">
          {state !== "disabling" ? <button type="button" className="im-btn im-btn-muted" disabled={pending} onClick={onEdit}>{t("agents.channels.actions.edit")}</button> : null}
          {channel.enabled && offline ? (
            <button type="button" className="im-btn im-btn-muted" disabled>{connectionUnknown ? unknownLabel : t("agents.channels.actions.nodeOffline")}</button>
          ) : channel.enabled && ["connected", "reconnecting", "failed"].includes(state) ? (
            <button type="button" className="im-btn im-btn-muted" disabled={pending} onClick={onReconnect}>{t("agents.channels.actions.reconnect")}</button>
          ) : null}
          {state !== "disabling" ? <button type="button" className="im-btn im-btn-muted" disabled={pending} onClick={onToggle}>{channel.enabled ? t("agents.channels.actions.disable") : t("agents.channels.actions.enable")}</button> : null}
          <button type="button" className="im-btn im-btn-muted text-rose-700" disabled={pending} onClick={onDelete}>{t("agents.channels.actions.delete")}</button>
        </div>
      </div>
      <DiagnosticsPanel channel={channel} provider={provider} />
      <div className="im-channel-card-footer">
        <span role={failed ? "alert" : undefined}>
          <strong className={failed ? "text-rose-700" : "text-slate-800"}>{detail.strong}</strong> · <span>{detail.copy}</span>
        </span>
        <span>
          {observed?.status_updated_at
            ? t(stale ? "agents.channels.status.lastKnownUpdatedAt" : "agents.channels.status.updatedAt", { time: formatTime(observed.status_updated_at) })
            : t("agents.channels.status.savedAt", { time: formatTime(channel.updated_at) })}
        </span>
      </div>
    </article>
  );
}

function RemovalCard({
  removal,
  provider,
  pending,
  onRetry,
}: {
  removal: AgentChannelRemoval;
  provider: ChannelProviderDescriptor;
  pending: boolean;
  onRetry(): void;
}) {
  const { t } = useTranslation();
  const failed = removal.apply_state === "failed";
  const suffix = providerRemovalSummary(provider, removal);
  return (
    <article className="im-agent-card" data-channel-state="deleting">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-blue-700">{provider.icon}</span>
        <div className="min-w-[180px] flex-1">
          <div className="flex items-center gap-2">
            <h3 className="m-0 text-[15px] font-bold text-slate-900">{t(textKey(provider.label))}</h3>
            <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${failed ? "border-rose-200 bg-rose-50 text-rose-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
              {failed ? t("agents.channels.status.deleteFailed") : t("agents.channels.status.deletePending")}
            </span>
          </div>
          <p className="m-0 mt-1 text-xs text-slate-500">{provider.removalSummary.label} · ••••{suffix} · {t("agents.channels.status.credentialsDeleted")}</p>
        </div>
        <button type="button" className="im-btn im-btn-muted" disabled={pending} onClick={onRetry}>{t("agents.channels.actions.retryApply")}</button>
      </div>
      <div className="flex flex-wrap justify-between gap-2 border-t border-[var(--im-border)] pt-3 text-xs text-slate-500">
        <span role={failed ? "alert" : undefined}>
          <strong className={failed ? "text-rose-700" : "text-slate-800"}>
            {failed ? removal.apply_error?.message || t("agents.channels.status.deleteUnknownFailure") : t("agents.channels.status.deleteSaved")}
          </strong> · {t("agents.channels.status.deleteReload")}
        </span>
        <span>{t("agents.channels.status.savedAt", { time: formatTime(removal.created_at) })}</span>
      </div>
    </article>
  );
}

function ConfirmationDialog({
  kind,
  provider,
  pending,
  notice,
  onCancel,
  onConfirm,
}: {
  kind: "disable" | "delete";
  provider: ChannelProviderDescriptor;
  pending: boolean;
  notice?: string | null;
  onCancel(): void;
  onConfirm(): void;
}) {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const titleId = useId();
  return (
    <div className={isMobile ? "chat-modal-bottom-sheet" : "chat-modal-backdrop"} role="presentation">
      <section className="chat-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="chat-modal-header bg-white">
          {isMobile ? <div className="chat-modal-sheet-handle" aria-hidden="true"><div className="chat-modal-sheet-handle-bar" /></div> : null}
          <h2 id={titleId}>{t(`agents.channels.confirm.${kind}TitleGeneric`, {
            provider: t(textKey(provider.label)),
          })}</h2>
        </header>
        <div className="chat-modal-body"><p className="m-0 text-sm text-slate-600">{t(`agents.channels.confirm.${kind}Body`)}</p>{notice ? <p className="m-0 text-xs text-amber-900" role="status">{notice}</p> : null}</div>
        <footer className="chat-modal-footer bg-white">
          <button type="button" className="chat-modal-btn-ghost" onClick={onCancel}>{t("agents.channels.actions.cancel")}</button>
          <button type="button" className="chat-modal-btn-primary" disabled={pending} onClick={onConfirm}>{t(`agents.channels.confirm.${kind}Action`)}</button>
        </footer>
      </section>
    </div>
  );
}

interface ChannelDialogProps {
  providers: readonly ChannelProviderDescriptor[];
  occupiedProviderIds: ReadonlySet<string>;
  editing: AgentChannel | null;
  initialStep: "provider" | "credentials";
  pending: boolean;
  readOnly: boolean;
  requestError: string | null;
  onClose(): void;
  onSave(
    provider: ChannelProviderDescriptor,
    input: ChannelProviderFormState,
  ): void;
}

function ChannelDialog({
  providers,
  occupiedProviderIds,
  editing,
  initialStep,
  pending,
  readOnly,
  requestError,
  onClose,
  onSave,
}: ChannelDialogProps) {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const titleId = useId();
  const fieldId = useId();
  const [step, setStep] = useState(initialStep);
  const initialProvider = editing
    ? providerById(providers, editing.provider)
    : undefined;
  const [providerId, setProviderId] = useState(initialProvider?.id ?? null);
  const provider = providerId ? providerById(providers, providerId) : undefined;
  const [form, setForm] = useState<ChannelProviderFormState | null>(() => (
    initialProvider ? initialProviderForm(initialProvider, editing) : null
  ));
  const [errors, setErrors] = useState<Record<string, ChannelText>>({});
  const configFields = provider?.fields.filter((field) => field.source === "config") ?? [];
  const secretFields = provider?.fields.filter((field) => field.source === "credentials") ?? [];
  const secretRequired = editing === null || form?.credentialMode === "replace";

  function selectProvider(selected: ChannelProviderDescriptor) {
    setProviderId(selected.id);
    setForm(initialProviderForm(selected, null));
    setErrors({});
    setStep("credentials");
  }

  function setFieldValue(name: string, value: string) {
    if (!provider) return;
    const field = provider.fields.find((candidate) => candidate.name === name);
    setForm((current) => {
      if (!current) return current;
      let credentialMode = current.credentialMode;
      if (editing && field?.resetsCredentials) {
        const original = editing.config[field.wireKey];
        if (value.trim() !== (typeof original === "string" ? original : "")) {
          credentialMode = "replace";
        }
      }
      return {
        ...current,
        credentialMode,
        values: { ...current.values, [name]: value },
      };
    });
  }

  function submit() {
    if (readOnly || pending || !provider || !form) return;
    const validationErrors = validateProviderForm(provider, form, editing);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;
    onSave(provider, form);
  }

  return (
    <div className={isMobile ? "chat-modal-bottom-sheet" : "chat-modal-backdrop"} role="presentation">
      <section className="chat-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="chat-modal-header flex items-start justify-between gap-3 bg-white">
          <div>
            {isMobile ? <div className="chat-modal-sheet-handle" aria-hidden="true"><div className="chat-modal-sheet-handle-bar" /></div> : null}
            <h2 id={titleId}>
              {editing && provider
                ? t("agents.channels.dialog.editTitleGeneric", {
                  provider: t(textKey(provider.label)),
                })
                : t("agents.channels.dialog.addTitle")}
            </h2>
          </div>
          <button type="button" className="chat-modal-btn-ghost" aria-label={t("agents.channels.actions.close")} onClick={onClose}>×</button>
        </header>

        {step === "provider" ? (
          <div className="chat-modal-body">
            {providers.map((candidate) => {
              const alreadyAdded = occupiedProviderIds.has(candidate.id);
              return (
                <button
                  key={candidate.id}
                  type="button"
                  disabled={alreadyAdded || readOnly}
                  className="im-channel-provider flex items-center gap-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => selectProvider(candidate)}
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 font-bold text-blue-700">{candidate.icon}</span>
                  <span className="flex flex-1 flex-col">
                    <strong className="text-sm">{t(textKey(candidate.label))}</strong>
                    <span className="text-xs text-slate-500">{t(textKey(candidate.description))}</span>
                  </span>
                  {alreadyAdded ? <span className="text-xs font-semibold text-slate-500">{t("agents.channels.provider.added")}</span> : null}
                </button>
              );
            })}
          </div>
        ) : provider && form ? (
          <div className="chat-modal-body gap-3">
            {provider.guide ? (
              <div className="rounded-lg bg-blue-50 p-3 text-xs leading-5 text-blue-900">
                {t(textKey(provider.guide.text))} {" "}
                <a className="font-semibold underline" href={provider.guide.href} target="_blank" rel="noreferrer">
                  {t(textKey(provider.guide.linkLabel))} ↗
                </a>
              </div>
            ) : null}
            {configFields.map((field) => (
              <div className="im-agent-field" key={field.name}>
                <label className="text-xs font-semibold" htmlFor={`${fieldId}-${field.name}`}>
                  {t(textKey(field.label))}
                </label>
                <input
                  id={`${fieldId}-${field.name}`}
                  className="im-input"
                  disabled={readOnly || pending}
                  autoComplete="off"
                  value={form.values[field.name] ?? ""}
                  onChange={(event) => setFieldValue(field.name, event.target.value)}
                />
                {errors[field.name] ? (
                  <span className="im-agent-field-error">{t(textKey(errors[field.name]))}</span>
                ) : null}
              </div>
            ))}
            {editing && secretFields.length > 0 ? (
              <fieldset className="grid gap-2 border-0 p-0">
                <legend className="mb-1 text-xs font-semibold">
                  {secretFields.map((field) => t(textKey(field.label))).join(" / ")}
                </legend>
                {(["keep", "replace"] as const).map((mode) => (
                  <label key={mode} className="flex cursor-pointer items-start gap-2 rounded-lg border border-[var(--im-border)] p-2 text-xs">
                    <input
                      disabled={readOnly || pending}
                      type="radio"
                      name="credential-mode"
                      checked={form.credentialMode === mode}
                      onChange={() => setForm((current) => current ? ({
                        ...current,
                        credentialMode: mode,
                        values: mode === "keep"
                          ? Object.fromEntries(Object.entries(current.values).map(([key, value]) => (
                            secretFields.some((field) => field.name === key)
                              ? [key, ""]
                              : [key, value]
                          )))
                          : current.values,
                      }) : current)}
                    />
                    <span><strong>{t(`agents.channels.credentials.${mode}`)}</strong><br /><span className="text-slate-500">{t(`agents.channels.credentials.${mode}Help`)}</span></span>
                  </label>
                ))}
              </fieldset>
            ) : null}
            {secretRequired ? secretFields.map((field) => (
              <div className="im-agent-field" key={field.name}>
                <label className="text-xs font-semibold" htmlFor={`${fieldId}-${field.name}`}>
                  {t(textKey(field.label))}
                </label>
                <input
                  id={`${fieldId}-${field.name}`}
                  className="im-input"
                  type={field.inputType ?? "password"}
                  disabled={readOnly || pending}
                  autoComplete="new-password"
                  value={form.values[field.name] ?? ""}
                  onChange={(event) => setFieldValue(field.name, event.target.value)}
                />
                {field.help ? (
                  <span className="im-agent-field-help">{t(textKey(field.help))}</span>
                ) : null}
                {errors[field.name] ? (
                  <span className="im-agent-field-error">{t(textKey(errors[field.name]))}</span>
                ) : null}
              </div>
            )) : null}
            {requestError ? <p className="m-0 text-xs font-semibold text-rose-700" role="alert">{requestError}</p> : null}
            {!editing && occupiedProviderIds.has(provider.id) ? <p className="m-0 text-xs font-semibold text-rose-700" role="alert">{t("agents.channels.provider.added")}</p> : null}
          </div>
        ) : null}

        <footer className="chat-modal-footer bg-white">
          <button type="button" className="chat-modal-btn-ghost" onClick={onClose}>{t("agents.channels.actions.cancel")}</button>
          {step === "credentials" && provider && form ? (
            <button type="button" className="chat-modal-btn-primary" disabled={pending || readOnly || (!editing && occupiedProviderIds.has(provider.id))} onClick={submit}>
              {pending ? t("agents.channels.actions.saving") : t("agents.channels.actions.saveConnect")}
            </button>
          ) : null}
        </footer>
      </section>
    </div>
  );
}

export function AgentChannelsPanel({
  agentId,
  nodeStatus = "online",
  readOnly = false,
  providers = CHANNEL_PROVIDERS,
}: {
  agentId: string;
  nodeStatus?: string | null;
  readOnly?: boolean;
  providers?: readonly ChannelProviderDescriptor[];
}) {
  const { t, i18n } = useTranslation();
  const tr = (zh: string, en: string) => i18n.language.startsWith("zh") ? zh : en;
  const queryClient = useQueryClient();
  const queryPrefix = ["settings", "agents", agentId, "channels"];
  // Each connection state has its own observer so a pre-disconnect response
  // cannot unlock the newly connected page.
  const queryKey = [...queryPrefix, nodeStatus, readOnly];
  const [dialog, setDialog] = useState<{
    step: "provider" | "credentials";
    editing: AgentChannel | null;
  } | null>(null);
  const [confirmation, setConfirmation] = useState<{ kind: "disable" | "delete"; channel: AgentChannel } | null>(null);
  const [unconfirmed, setUnconfirmed] = useState<{
    kind: "create" | "edit" | "toggle" | "delete" | "retry" | "reconnect";
    provider: string;
    channelId?: string;
    revision?: number;
    observedAt?: string;
    submittedAt: number;
  } | null>(null);
  const [removalRetryNoticeId, setRemovalRetryNoticeId] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<RequestErrorState | null>(null);
  const offline = nodeStatus !== "online" || readOnly;
  const channelsQuery = useQuery({
    queryKey,
    queryFn: ({ signal }) => listAgentChannels(agentId, signal),
    placeholderData: (previous) => previous,
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: (query) => {
      const resources = query.state.data as AgentChannelResource[] | undefined;
      return unconfirmed || resources?.some((resource) => {
        if (isRemoval(resource)) return true;
        const channel = resource;
        const state = channel.observed?.connection_state;
        return channel.sync_state !== "applied" || !state || state === "connecting" || state === "reconnecting";
      }) ? 1_000 : false;
    },
  });

  const resources = channelsQuery.data ?? [];
  const unavailable = offline || channelsQuery.isFetching || channelsQuery.isPlaceholderData
    || !channelsQuery.isFetchedAfterMount || channelsQuery.isError;
  const editingLatest = dialog?.editing
    ? resources.find((resource) => resource.channel_id === dialog.editing?.channel_id)
    : undefined;
  const draftConflict = !!dialog?.editing && (!editingLatest || isRemoval(editingLatest)
    || editingLatest.channel_revision !== dialog.editing.channel_revision);
  const confirmationLatest = confirmation
    ? resources.find((resource) => resource.channel_id === confirmation.channel.channel_id)
    : undefined;
  const confirmationConflict = !!confirmation && (!confirmationLatest || isRemoval(confirmationLatest)
    || confirmationLatest.channel_revision !== confirmation.channel.channel_revision);
  const blocked = unavailable || unconfirmed !== null;
  const connectionNotice = offline
    ? tr("节点连接未确认，当前只读；未保存的输入已保留。", "Node connection is unconfirmed. Settings are read-only; unsaved input is retained.")
    : channelsQuery.isError
      ? tr("通道读取失败，已保留最后取得的信息。", "Channel refresh failed. Previously loaded information is retained.")
      : unavailable
        ? tr("已连接，正在刷新通道信息。", "Connected. Refreshing channel information.")
        : null;
  const conflictNotice = tr("通道已在其他地方更新，草稿已保留。请取消后重新编辑最新配置。", "The channel changed elsewhere. Your draft is retained. Cancel and reopen to edit the latest configuration.");

  function requireWritable(channel?: AgentChannel) {
    if (blocked) throw Object.assign(new Error(connectionNotice ?? tr("操作结果待确认，请先重新读取。", "The operation result is unconfirmed. Refresh first.")), { status: 409 });
    if (channel) {
      const latest = resources.find((resource) => resource.channel_id === channel.channel_id);
      if (!latest || isRemoval(latest) || latest.channel_revision !== channel.channel_revision || latest.sync_state === "pending") {
        throw Object.assign(new Error(conflictNotice), { status: 409 });
      }
    }
  }

  function uncertainFailure(error: unknown, action: NonNullable<typeof unconfirmed>) {
    const detail = errorDetail(error);
    setRequestError({ message: detail, removalId: action.kind === "retry" ? action.channelId ?? null : null });
    // Explicit HTTP rejections are authoritative. Transport failures can have
    // happened after acceptance, so never resend them automatically.
    const status = error && typeof error === "object" && "status" in error ? error.status : null;
    if (![400, 401, 403, 404, 409, 422].includes(Number(status))
      && !/agent_node_offline|channel_node_offline/.test(detail)) {
      setUnconfirmed(action);
    } else {
      setUnconfirmed(null);
    }
    void queryClient.invalidateQueries({ queryKey: queryPrefix });
  }

  function storeResource(saved: AgentChannelResource) {
    queryClient.setQueryData<AgentChannelResource[]>(queryKey, (current = []) => {
      const previous = current.find((item) => item.channel_id === saved.channel_id);
      if (previous && !isRemoval(saved)
        && (isRemoval(previous) || previous.channel_revision > saved.channel_revision)) return current;
      return previous
        ? current.map((item) => item.channel_id === saved.channel_id ? saved : item)
        : [...current, saved];
    });
  }

  const saveMutation = useMutation({
    mutationFn: ({
      provider,
      form,
      editing,
    }: {
      provider: ChannelProviderDescriptor;
      form: ChannelProviderFormState;
      editing: AgentChannel | null;
    }) => {
      requireWritable(editing ?? undefined);
      if (!editing && resources.some((resource) => resource.provider === provider.id)) throw Object.assign(new Error(conflictNotice), { status: 409 });
      const { config, credentials } = serializeProviderForm(provider, form);
      if (editing) {
        return updateAgentChannel(agentId, editing.channel_id, {
          channel_revision: editing.channel_revision,
          enabled: editing.enabled,
          config,
          credentials,
        });
      }
      const payload: CreateAgentChannelInput = {
        provider: provider.id,
        enabled: true,
        config,
        credentials,
      };
      return createAgentChannel(agentId, payload);
    },
    onSuccess: (saved) => {
      storeResource(saved);
      setRequestError(null);
      setDialog(null);
    },
    onError: (error, { provider, editing }) => uncertainFailure(error, {
      kind: editing ? "edit" : "create", provider: provider.id,
      channelId: editing?.channel_id, revision: editing?.channel_revision, submittedAt: Date.now(),
    }),
  });

  const toggleMutation = useMutation({
    mutationFn: (channel: AgentChannel) => {
      requireWritable(channel);
      return updateAgentChannel(agentId, channel.channel_id, {
        channel_revision: channel.channel_revision,
        enabled: !channel.enabled,
        config: channel.config,
        credentials: { mode: "keep" },
      });
    },
    onSuccess: (saved) => {
      storeResource(saved);
      setConfirmation(null);
      setRequestError(null);
    },
    onError: (error, channel) => uncertainFailure(error, {
      kind: "toggle", provider: channel.provider, channelId: channel.channel_id,
      revision: channel.channel_revision, submittedAt: Date.now(),
    }),
  });

  const reconnectMutation = useMutation({
    onMutate: () => Date.now(),
    mutationFn: (channel: AgentChannel) => {
      requireWritable(channel);
      setUnconfirmed({ kind: "reconnect", provider: channel.provider, channelId: channel.channel_id,
        revision: channel.channel_revision, observedAt: channel.observed?.status_updated_at, submittedAt: Date.now() });
      return reconnectAgentChannel(agentId, channel.channel_id);
    },
    onSuccess: () => {
      setRequestError(null);
      void queryClient.invalidateQueries({ queryKey: queryPrefix });
    },
    onError: (error, channel, submittedAt) => uncertainFailure(error, {
      kind: "reconnect", provider: channel.provider, channelId: channel.channel_id,
      revision: channel.channel_revision, observedAt: channel.observed?.status_updated_at, submittedAt: submittedAt ?? Date.now(),
    }),
  });

  const deleteMutation = useMutation({
    mutationFn: (channel: AgentChannel) => {
      requireWritable(channel);
      return deleteAgentChannel(agentId, channel.channel_id, channel.channel_revision);
    },
    onSuccess: (saved) => {
      storeResource(saved);
      setConfirmation(null);
      setRequestError(null);
    },
    onError: (error, channel) => uncertainFailure(error, {
      kind: "delete", provider: channel.provider, channelId: channel.channel_id,
      revision: channel.channel_revision, submittedAt: Date.now(),
    }),
  });

  const retryMutation = useMutation({
    mutationFn: (removal: AgentChannelRemoval) => {
      requireWritable();
      return retryAgentChannelRemoval(agentId, removal.channel_id);
    },
    onSuccess: (saved) => {
      storeResource(saved);
      setRemovalRetryNoticeId(null);
      setRequestError(null);
    },
    onError: (error, removal) => {
      const detail = errorDetail(error);
      if (/channel_node_offline|agent_node_offline/.test(detail)) {
        setRemovalRetryNoticeId(removal.channel_id);
        setRequestError(null);
        return;
      }
      setRemovalRetryNoticeId(null);
      uncertainFailure(error, { kind: "retry", provider: removal.provider,
        channelId: removal.channel_id, submittedAt: Date.now() });
    },
  });

  useEffect(() => {
    if (unavailable || !unconfirmed) return;
    const latest = resources.find((resource) => unconfirmed.kind === "create"
      ? resource.provider === unconfirmed.provider : resource.channel_id === unconfirmed.channelId);
    const confirmed = unconfirmed.kind === "delete" || unconfirmed.kind === "retry"
      ? !latest || (isRemoval(latest) && (unconfirmed.kind === "delete" || latest.apply_state !== "failed"))
      : unconfirmed.kind === "create"
        ? !!latest
        : unconfirmed.kind === "reconnect"
          ? latest && !isRemoval(latest) && latest.observed && !latest.observed.status_stale
            && latest.observed.observed_revision >= (unconfirmed.revision ?? 0)
            && Date.parse(latest.observed.status_updated_at) > Math.max(unconfirmed.submittedAt, Date.parse(unconfirmed.observedAt ?? "") || 0)
          : latest && !isRemoval(latest) && latest.channel_revision > (unconfirmed.revision ?? 0);
    if (confirmed) {
      setUnconfirmed(null);
      setRequestError(null);
    }
  }, [resources, unavailable, unconfirmed]);

  useEffect(() => {
    const hasRemoval = (channelId: string) => resources.some(
      (resource) => isRemoval(resource) && resource.channel_id === channelId,
    );
    if (requestError?.removalId && !hasRemoval(requestError.removalId)) {
      setRequestError(null);
    }
    if (removalRetryNoticeId && !hasRemoval(removalRetryNoticeId)) {
      setRemovalRetryNoticeId(null);
    }
  }, [removalRetryNoticeId, requestError?.removalId, resources]);

  const removalRetryWaiting = removalRetryNoticeId !== null && resources.some(
    (resource) => isRemoval(resource) && resource.channel_id === removalRetryNoticeId,
  );
  const occupiedProviderIds = new Set(resources.map((resource) => resource.provider));
  const lifecyclePending = toggleMutation.isPending || reconnectMutation.isPending || deleteMutation.isPending || retryMutation.isPending;

  if (channelsQuery.isLoading && !dialog && !confirmation) return <p className="text-sm text-slate-500">{t("agents.channels.loading")}</p>;
  if (channelsQuery.isError && !channelsQuery.data && !dialog && !confirmation) {
    return (
      <section className="im-agent-card border-rose-200 bg-rose-50/80">
        <h3 className="im-agent-card-title text-rose-700">{t("agents.channels.loadError")}</h3>
        <p className="im-agent-card-sub">{errorDetail(channelsQuery.error)}</p>
        <button type="button" className="im-btn im-btn-muted w-fit" onClick={() => void channelsQuery.refetch()}>{t("agents.retry")}</button>
      </section>
    );
  }

  return (
    <div className="grid gap-4" data-testid="agent-channels-panel">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="m-0 text-base font-bold text-slate-900">{t("agents.channels.title")}</h3>
        </div>
        <button type="button" className="im-btn im-btn-primary im-channel-primary-action" aria-label={t("agents.channels.actions.add")} disabled={blocked || lifecyclePending || saveMutation.isPending} onClick={() => { if (blocked) return; setRequestError(null); setDialog({ step: "provider", editing: null }); }}>
          + {t("agents.channels.actions.add")}
        </button>
      </header>

      {(!offline && connectionNotice) || unconfirmed ? (
        <section className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--im-border)] py-2 text-xs text-slate-600" role="status">
          <span>{connectionNotice ?? tr("操作结果待确认；请重新读取后核对最新状态，勿重复提交。", "The operation result is unconfirmed. Refresh and check its latest state before submitting again.")}</span>
          <button type="button" className="im-btn im-btn-muted" disabled={channelsQuery.isFetching} onClick={async () => {
            const result = await channelsQuery.refetch();
            if (result.isSuccess && !offline && unconfirmed && requestError) {
              // A deliberate reread permits a new explicit action; it does not
              // prove the lost response succeeded or replay the previous write.
              setUnconfirmed(null);
              setRequestError({ message: tr("此前操作结果无法确认。请核对最新状态后决定是否重新操作。", "The previous result could not be confirmed. Check the latest state before deciding whether to try again."), removalId: null });
            }
          }}>{t("agents.retry")}</button>
        </section>
      ) : null}
      {nodeStatus === "offline" && resources.length > 0 ? (
        <section className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--im-border)] py-2 text-xs text-slate-600" role="status">
          <strong>{t("agents.channels.offline.title")}</strong>
          <span>{t("agents.channels.offline.detail")}</span>
        </section>
      ) : null}

      {requestError && !dialog ? <p className="m-0 text-xs font-semibold text-rose-700" role="alert">{requestError.message}</p> : null}
      {removalRetryWaiting ? (
        <p className="m-0 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900" role="status">
          {t("agents.channels.status.retryWaitingForNode")}
        </p>
      ) : null}

      {resources.length === 0 ? (
        <p className="im-settings-empty">{t("agents.channels.empty.title")}</p>
      ) : resources.map((resource) => {
        const provider = providerById(providers, resource.provider);
        if (!provider) return null;
        return isRemoval(resource) ? (
          <RemovalCard
            key={resource.channel_id}
            removal={resource}
            provider={provider}
            pending={blocked || lifecyclePending || saveMutation.isPending}
            onRetry={() => {
              if (blocked) return;
              setRequestError(null);
              setRemovalRetryNoticeId(null);
              retryMutation.mutate(resource);
            }}
          />
        ) : (
          <ConnectionCard
            key={resource.channel_id}
            channel={resource}
            provider={provider}
            manualReconnecting={unconfirmed?.kind === "reconnect" && unconfirmed.channelId === resource.channel_id}
            offline={offline}
            connectionUnknown={offline && nodeStatus !== "offline"}
            pending={blocked || lifecyclePending || saveMutation.isPending || resource.sync_state === "pending"}
            onEdit={() => {
              if (blocked) return;
              setRequestError(null);
              setDialog({ step: "credentials", editing: resource });
            }}
            onReconnect={() => { if (!blocked) reconnectMutation.mutate(resource); }}
            onToggle={() => {
              if (blocked) return;
              if (resource.enabled) {
                setConfirmation({ kind: "disable", channel: resource });
              } else {
                toggleMutation.mutate(resource);
              }
            }}
            onDelete={() => { if (!blocked) setConfirmation({ kind: "delete", channel: resource }); }}
          />
        );
      })}

      {dialog ? (
        <ChannelDialog
          key={`${dialog.step}:${dialog.editing?.channel_id ?? "new"}`}
          providers={providers}
          occupiedProviderIds={occupiedProviderIds}
          editing={dialog.editing}
          initialStep={dialog.step}
          pending={saveMutation.isPending}
          readOnly={blocked || draftConflict}
          requestError={draftConflict ? conflictNotice : connectionNotice ?? requestError?.message ?? (unconfirmed ? tr("提交结果待确认，草稿已保留。", "Submission result is unconfirmed; your draft is retained.") : null)}
          onClose={() => setDialog(null)}
          onSave={(provider, form) => {
            if (blocked || draftConflict) return;
            saveMutation.mutate({ provider, form, editing: dialog.editing });
          }}
        />
      ) : null}

      {confirmation ? (
        <ConfirmationDialog
          kind={confirmation.kind}
          provider={providerById(providers, confirmation.channel.provider) ?? providers[0]}
          pending={blocked || confirmationConflict || toggleMutation.isPending || deleteMutation.isPending}
          notice={confirmationConflict ? tr("通道已更新，请取消后核对最新状态。", "The channel changed. Cancel and check the latest state.") : connectionNotice}
          onCancel={() => setConfirmation(null)}
          onConfirm={() => {
            if (blocked || confirmationConflict) return;
            if (confirmation.kind === "disable") toggleMutation.mutate(confirmation.channel);
            else deleteMutation.mutate(confirmation.channel);
          }}
        />
      ) : null}
    </div>
  );
}
