import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { useTranslation } from "../../../i18n";
import {
  AgentChannel,
  CreateAgentChannelInput,
  createAgentChannel,
  listAgentChannels,
  updateAgentChannel,
} from "./im-agent-config-api";

const FEISHU_OPEN_PLATFORM_URL = "https://open.feishu.cn/page/launcher?from=backend_oneclick";

export const CHANNEL_PROVIDERS = [{
  id: "feishu",
  icon: "飞",
  labelKey: "agents.channels.feishu.label",
  descriptionKey: "agents.channels.feishu.description",
}] as const;

type CredentialMode = "keep" | "replace";

interface ChannelFormState {
  appId: string;
  appSecret: string;
  credentialMode: CredentialMode;
}

function appIdOf(channel: AgentChannel): string {
  return typeof channel.config.app_id === "string" ? channel.config.app_id : "";
}

function maskAppId(value: string): string {
  if (value.length <= 8) return value;
  return `${value.slice(0, 6)}••••${value.slice(-4)}`;
}

function formatTime(value: string | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function errorDetail(error: unknown): string {
  if (!(error instanceof Error)) return "Unknown error";
  return error.message.split(" failed: ").at(-1) ?? error.message;
}

function ConnectionCard({ channel, onEdit }: { channel: AgentChannel; onEdit(): void }) {
  const { t } = useTranslation();
  const observed = channel.observed;
  const state = observed?.connection_state ?? "pending";
  const connected = channel.sync_state === "applied" && state === "connected";
  const failed = state === "failed";
  const statusLabel = connected
    ? t("agents.channels.status.connected")
    : failed
      ? t("agents.channels.status.failed")
      : t("agents.channels.status.connecting");
  const statusClass = connected
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : failed
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : "border-amber-200 bg-amber-50 text-amber-700";

  return (
    <article className="im-agent-card" data-channel-state={connected ? "connected" : failed ? "failed" : "connecting"}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-blue-700">
          飞
        </span>
        <div className="min-w-[180px] flex-1">
          <div className="flex items-center gap-2">
            <h3 className="m-0 text-[15px] font-bold text-slate-900">{t("agents.channels.feishu.label")}</h3>
            <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClass}`}>{statusLabel}</span>
          </div>
          <p className="m-0 mt-1 text-xs text-slate-500">App ID · {maskAppId(appIdOf(channel))}</p>
        </div>
        <button type="button" className="im-btn im-btn-muted" onClick={onEdit}>
          {t("agents.channels.actions.edit")}
        </button>
      </div>
      <div className="flex flex-wrap justify-between gap-2 border-t border-[var(--im-border)] pt-3 text-xs text-slate-500">
        {connected ? (
          <span><strong className="text-slate-800">{t("agents.channels.status.synced")}</strong> · <span>{t("agents.channels.status.applied")}</span></span>
        ) : failed ? (
          <span role="alert"><strong className="text-rose-700">{t("agents.channels.status.failed")}</strong> · <span>{observed?.status_message || observed?.status_code || t("agents.channels.status.unknownFailure")}</span></span>
        ) : (
          <span><strong className="text-slate-800">{t("agents.channels.status.savedSecurely")}</strong> · {t("agents.channels.status.connectingDetail")}</span>
        )}
        <span>
          {observed?.status_updated_at
            ? t("agents.channels.status.updatedAt", { time: formatTime(observed.status_updated_at) })
            : t("agents.channels.status.savedAt", { time: formatTime(channel.updated_at) })}
        </span>
      </div>
    </article>
  );
}

interface ChannelDialogProps {
  existing: AgentChannel | null;
  editing: AgentChannel | null;
  initialStep: "provider" | "credentials";
  pending: boolean;
  requestError: string | null;
  onClose(): void;
  onSave(input: ChannelFormState): void;
}

function ChannelDialog({ existing, editing, initialStep, pending, requestError, onClose, onSave }: ChannelDialogProps) {
  const { t } = useTranslation();
  const titleId = useId();
  const appIdInputId = useId();
  const secretInputId = useId();
  const [step, setStep] = useState(initialStep);
  const originalAppId = editing ? appIdOf(editing) : "";
  const [form, setForm] = useState<ChannelFormState>({
    appId: originalAppId,
    appSecret: "",
    credentialMode: editing ? "keep" : "replace",
  });
  const [attempted, setAttempted] = useState(false);
  const appIdMissing = attempted && !form.appId.trim();
  const secretRequired = !editing || form.credentialMode === "replace";
  const secretMissing = attempted && secretRequired && !form.appSecret.trim();

  function setAppId(appId: string) {
    setForm((current) => ({
      ...current,
      appId,
      credentialMode: editing && appId.trim() !== originalAppId ? "replace" : current.credentialMode,
    }));
  }

  function submit() {
    setAttempted(true);
    if (!form.appId.trim() || (secretRequired && !form.appSecret.trim())) return;
    onSave({ ...form, appId: form.appId.trim(), appSecret: form.appSecret.trim() });
  }

  return (
    <div className="chat-modal-backdrop" role="presentation">
      <section className="chat-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="chat-modal-header flex items-start justify-between gap-3 bg-white">
          <div>
            <h2 id={titleId}>{editing ? t("agents.channels.dialog.editTitle") : t("agents.channels.dialog.addTitle")}</h2>
            <p>{step === "provider" ? t("agents.channels.dialog.chooseProvider") : t("agents.channels.dialog.credentialsSubtitle")}</p>
          </div>
          <button type="button" className="chat-modal-btn-ghost" aria-label={t("agents.channels.actions.close")} onClick={onClose}>×</button>
        </header>

        {step === "provider" ? (
          <div className="chat-modal-body">
            {CHANNEL_PROVIDERS.map((provider) => {
              const alreadyAdded = existing?.provider === provider.id;
              return (
                <button
                  key={provider.id}
                  type="button"
                  disabled={alreadyAdded}
                  className="flex items-center gap-3 rounded-xl border border-[var(--im-border)] bg-white p-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => setStep("credentials")}
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 font-bold text-blue-700">{provider.icon}</span>
                  <span className="flex flex-1 flex-col">
                    <strong className="text-sm">{t(provider.labelKey)}</strong>
                    <span className="text-xs text-slate-500">{t(provider.descriptionKey)}</span>
                  </span>
                  {alreadyAdded ? <span className="text-xs font-semibold text-slate-500">{t("agents.channels.provider.added")}</span> : null}
                </button>
              );
            })}
          </div>
        ) : (
          <div className="chat-modal-body gap-3">
            <div className="rounded-lg bg-blue-50 p-3 text-xs leading-5 text-blue-900">
              {t("agents.channels.feishu.guide")} {" "}
              <a className="font-semibold underline" href={FEISHU_OPEN_PLATFORM_URL} target="_blank" rel="noreferrer">
                {t("agents.channels.feishu.openPlatform")} ↗
              </a>
            </div>
            <div className="im-agent-field">
              <label className="text-xs font-semibold" htmlFor={appIdInputId}>App ID</label>
              <input id={appIdInputId} className="im-input" autoComplete="off" value={form.appId} onChange={(event) => setAppId(event.target.value)} />
              {appIdMissing ? <span className="im-agent-field-error">{t("agents.channels.validation.appId")}</span> : null}
            </div>
            {editing ? (
              <fieldset className="grid gap-2 border-0 p-0">
                <legend className="mb-1 text-xs font-semibold">App Secret</legend>
                {(["keep", "replace"] as CredentialMode[]).map((mode) => (
                  <label key={mode} className="flex cursor-pointer items-start gap-2 rounded-lg border border-[var(--im-border)] p-2 text-xs">
                    <input
                      type="radio"
                      name="credential-mode"
                      checked={form.credentialMode === mode}
                      onChange={() => setForm((current) => ({ ...current, credentialMode: mode, appSecret: mode === "keep" ? "" : current.appSecret }))}
                    />
                    <span><strong>{t(`agents.channels.credentials.${mode}`)}</strong><br /><span className="text-slate-500">{t(`agents.channels.credentials.${mode}Help`)}</span></span>
                  </label>
                ))}
              </fieldset>
            ) : null}
            {secretRequired ? (
              <div className="im-agent-field">
                <label className="text-xs font-semibold" htmlFor={secretInputId}>App Secret</label>
                <input
                  id={secretInputId}
                  className="im-input"
                  type="password"
                  autoComplete="new-password"
                  value={form.appSecret}
                  onChange={(event) => setForm((current) => ({ ...current, appSecret: event.target.value }))}
                />
                <span className="im-agent-field-help">{t("agents.channels.credentials.secretHelp")}</span>
                {secretMissing ? <span className="im-agent-field-error">{t("agents.channels.validation.appSecret")}</span> : null}
              </div>
            ) : null}
            {requestError ? <p className="m-0 text-xs font-semibold text-rose-700" role="alert">{requestError}</p> : null}
          </div>
        )}

        <footer className="chat-modal-footer bg-white">
          <button type="button" className="chat-modal-btn-ghost" onClick={onClose}>{t("agents.channels.actions.cancel")}</button>
          {step === "credentials" ? (
            <button type="button" className="chat-modal-btn-primary" disabled={pending} onClick={submit}>
              {pending ? t("agents.channels.actions.saving") : t("agents.channels.actions.saveConnect")}
            </button>
          ) : null}
        </footer>
      </section>
    </div>
  );
}

export function AgentChannelsPanel({ agentId }: { agentId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const queryKey = ["settings", "agents", agentId, "channels"];
  const [dialog, setDialog] = useState<{ step: "provider" | "credentials"; editing: AgentChannel | null } | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const channelsQuery = useQuery({
    queryKey,
    queryFn: () => listAgentChannels(agentId),
    refetchInterval: (query) => {
      const channels = query.state.data as AgentChannel[] | undefined;
      return channels?.some((channel) => {
        const state = channel.observed?.connection_state;
        return channel.sync_state !== "applied" || !state || state === "connecting" || state === "reconnecting";
      }) ? 1_000 : false;
    },
  });

  const saveMutation = useMutation({
    mutationFn: ({ form, editing }: { form: ChannelFormState; editing: AgentChannel | null }) => {
      const credentials = form.credentialMode === "replace"
        ? { mode: "replace" as const, app_secret: form.appSecret }
        : { mode: "keep" as const };
      if (editing) {
        return updateAgentChannel(agentId, editing.channel_id, {
          channel_revision: editing.channel_revision,
          enabled: true,
          config: { app_id: form.appId },
          credentials,
        });
      }
      const payload: CreateAgentChannelInput = {
        provider: "feishu",
        enabled: true,
        config: { app_id: form.appId },
        credentials,
      };
      return createAgentChannel(agentId, payload);
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<AgentChannel[]>(queryKey, (current = []) => {
        const exists = current.some((item) => item.channel_id === saved.channel_id);
        return exists ? current.map((item) => item.channel_id === saved.channel_id ? saved : item) : [...current, saved];
      });
      setRequestError(null);
      setDialog(null);
    },
    onError: (error) => setRequestError(errorDetail(error)),
  });

  const channels = channelsQuery.data ?? [];
  const feishu = channels.find((channel) => channel.provider === "feishu") ?? null;

  if (channelsQuery.isLoading) return <p className="text-sm text-slate-500">{t("agents.channels.loading")}</p>;
  if (channelsQuery.isError) {
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
          <p className="m-0 mt-1 text-xs text-slate-500">{t("agents.channels.subtitle")}</p>
        </div>
        <button type="button" className="im-btn im-btn-primary" aria-label={t("agents.channels.actions.add")} onClick={() => { setRequestError(null); setDialog({ step: "provider", editing: null }); }}>
          + {t("agents.channels.actions.add")}
        </button>
      </header>

      {channels.length === 0 ? (
        <section className="im-agent-card place-items-center py-10 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-xl text-slate-500">+</span>
          <div>
            <h3 className="im-agent-card-title">{t("agents.channels.empty.title")}</h3>
            <p className="im-agent-card-sub mt-1">{t("agents.channels.empty.description")}</p>
          </div>
          <button type="button" className="im-btn im-btn-primary" onClick={() => { setRequestError(null); setDialog({ step: "provider", editing: null }); }}>
            {t("agents.channels.actions.add")}
          </button>
        </section>
      ) : channels.map((channel) => (
        <ConnectionCard
          key={channel.channel_id}
          channel={channel}
          onEdit={() => { setRequestError(null); setDialog({ step: "credentials", editing: channel }); }}
        />
      ))}

      {dialog ? (
        <ChannelDialog
          key={`${dialog.step}:${dialog.editing?.channel_id ?? "new"}`}
          existing={feishu}
          editing={dialog.editing}
          initialStep={dialog.step}
          pending={saveMutation.isPending}
          requestError={requestError}
          onClose={() => setDialog(null)}
          onSave={(form) => saveMutation.mutate({ form, editing: dialog.editing })}
        />
      ) : null}
    </div>
  );
}
