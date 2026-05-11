import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { createDirectConversation } from "../../chat/chat-api";
import { AllowlistSelector } from "./allowlist-selector";
import { useAgentStatusBroadcastConsumer } from "./agent-status-ws-consumer";
import { AgentConfig, getAgentDetailState, updateAgentConfig } from "./im-agent-config-api";

type AgentConfigFormState = AgentConfig;

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function normalizeText(value: string) {
  return value.trim();
}

function normalizeAgentConfig(config: AgentConfigFormState): AgentConfigFormState {
  return {
    ...config,
    display_name: normalizeText(config.display_name),
    description: normalizeText(config.description),
    system_prompt: config.system_prompt.trim(),
    skills: normalizeAllowlist(config.skills),
    tool_allowlist: normalizeAllowlist(config.tool_allowlist),
    default_model: normalizeText(config.default_model ?? "") || null
  };
}

function validateDraft(draft: AgentConfigFormState) {
  const errors: Partial<Record<"display_name" | "system_prompt", string>> = {};
  if (!draft.display_name) errors.display_name = "Display name is required.";
  if (!draft.system_prompt) errors.system_prompt = "System prompt is required.";
  return errors;
}

function initialsOf(displayName: string): string {
  const trimmed = displayName.trim();
  if (!trimmed) return "AG";
  return trimmed.slice(0, 2).toUpperCase();
}

function resolveModelOptions(modelOptions: string[] | undefined, currentModel: string | null) {
  const resolved = Array.from(new Set((modelOptions ?? []).map((value) => value.trim()).filter(Boolean)));
  if (currentModel && !resolved.includes(currentModel)) {
    resolved.unshift(currentModel);
  }
  return resolved;
}

function formatUpdatedAt(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export function AgentDetailPage() {
  const { agentId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  useAgentStatusBroadcastConsumer();
  const [draft, setDraft] = useState<AgentConfigFormState | null>(null);
  const [saved, setSaved] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasAttemptedSave, setHasAttemptedSave] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const detailQuery = useQuery({
    queryKey: ["settings", "agents", agentId, "detail-state"],
    queryFn: () => getAgentDetailState(agentId),
    staleTime: 30_000
  });

  useEffect(() => {
    if (detailQuery.data?.config) {
      setDraft(detailQuery.data.config);
      setErrorMessage(null);
    }
  }, [detailQuery.data]);

  const capabilities = detailQuery.data?.capabilities;
  const owningNode = detailQuery.data?.owningNode ?? null;
  const normalizedDraft = useMemo(() => (draft ? normalizeAgentConfig(draft) : null), [draft]);
  const normalizedServerState = useMemo(
    () => (detailQuery.data?.config ? normalizeAgentConfig(detailQuery.data.config) : null),
    [detailQuery.data]
  );
  const availableModels = useMemo(
    () => resolveModelOptions(capabilities?.model_options, draft?.default_model ?? null),
    [capabilities?.model_options, draft?.default_model]
  );
  const platformDefaultModel = capabilities?.platform_default_model ?? null;
  const validationErrors = useMemo(() => (normalizedDraft ? validateDraft(normalizedDraft) : {}), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const isDirty =
    normalizedDraft && normalizedServerState ? JSON.stringify(normalizedDraft) !== JSON.stringify(normalizedServerState) : false;
  const queryErrorDetail =
    detailQuery.error instanceof Error
      ? detailQuery.error.message.split(" failed: ").at(-1) ?? detailQuery.error.message
      : "Unable to load this agent.";

  const mutation = useMutation({
    mutationFn: (next: AgentConfigFormState) => {
      const {
        updated_at: _updatedAt,
        owner_id: _ownerId,
        agent_id: _agentId,
        workspace_root: _workspaceRoot,
        workspace_is_default: _workspaceIsDefault,
        node_id: _nodeId,
        node_name: _nodeName,
        node_status: _nodeStatus,
        ...payload
      } = next;
      return updateAgentConfig(agentId, payload);
    },
    onSuccess: async (updated) => {
      setErrorMessage(null);
      setSaved(true);
      setHasAttemptedSave(false);
      if (updated && capabilities) {
        setDraft(updated);
        queryClient.setQueryData(["settings", "agents", agentId, "detail-state"], {
          config: updated,
          capabilities,
          owningNode
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents", agentId, "detail-state"] });
      setTimeout(() => setSaved(false), 1800);
    },
    onError: (error) => {
      setSaved(false);
      setErrorMessage(
        error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Save failed"
      );
    }
  });

  const openDirectChatMutation = useMutation({
    mutationFn: () => createDirectConversation({ agentId }),
    onSuccess: async ({ conversation_id }) => {
      setErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      navigate(`/chat/${conversation_id}`);
    },
    onError: (error) => {
      setErrorMessage(
        error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Open direct chat failed"
      );
    }
  });

  function markTouched(field: "display_name" | "system_prompt") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "display_name" | "system_prompt") {
    return (hasAttemptedSave || touched[field]) && validationErrors[field];
  }

  function handleDiscard() {
    if (detailQuery.data?.config) {
      setDraft(detailQuery.data.config);
      setErrorMessage(null);
      setHasAttemptedSave(false);
      setTouched({});
    }
  }

  if (detailQuery.isLoading && !draft) {
    return <p className="text-sm text-slate-500">{t("agents.detail.loading")}</p>;
  }

  if (detailQuery.isError && !draft) {
    return (
      <section className="grid gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">{t("agents.loadError")}</p>
          <p className="text-sm text-rose-600">{queryErrorDetail}</p>
        </div>
        <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void detailQuery.refetch()}>
          {t("agents.retry")}
        </button>
      </section>
    );
  }

  if (!draft || !normalizedDraft || !capabilities) {
    return <p className="text-sm text-slate-500">{t("agents.detail.loading")}</p>;
  }

  const displayedNodeName =
    draft.node_name ?? capabilities.node_name ?? owningNode?.node_name ?? draft.node_id ?? capabilities.node_id ?? "—";
  const displayedNodeId = draft.node_id ?? capabilities.node_id ?? "—";
  const displayedNodeStatusRaw = draft.node_status ?? capabilities.node_status ?? owningNode?.status ?? "unknown";
  const displayedNodeStatus = displayedNodeStatusRaw.toLowerCase();
  const statusChipClass =
    displayedNodeStatus === "online" ? "im-agent-panel-status-chip online" : "im-agent-panel-status-chip";

  let footerStatusClass = "im-agent-footer-status";
  let footerStatusText = t("agents.detail.noChanges");
  if (errorMessage) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = errorMessage;
  } else if (hasAttemptedSave && hasValidationErrors) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = t("agents.form.errors.required");
  } else if (mutation.isPending) {
    footerStatusClass = "im-agent-footer-status";
    footerStatusText = t("agents.detail.saving");
  } else if (saved) {
    footerStatusClass = "im-agent-footer-status saved";
    footerStatusText = t("agents.detail.saved");
  } else if (isDirty) {
    footerStatusClass = "im-agent-footer-status dirty";
    footerStatusText = t("agents.detail.unsavedChanges");
  }

  return (
    <form
      data-testid="agent-detail"
      className="im-agent-panel"
      onSubmit={(event) => {
        event.preventDefault();
        setHasAttemptedSave(true);
        setErrorMessage(null);
        if (hasValidationErrors || !isDirty || !normalizedDraft) return;
        mutation.mutate(normalizedDraft);
      }}
    >
      <header className="im-agent-panel-header">
        <div className="im-agent-panel-header-row">
          <span className="im-agent-row-avatar" aria-hidden="true">
            {initialsOf(draft.display_name)}
          </span>
          <div style={{ flex: 1 }}>
            <h2 className="im-agent-panel-title">{draft.display_name || draft.agent_id}</h2>
            <p className="im-agent-panel-subtitle">
              {draft.agent_id} · {displayedNodeName}
            </p>
          </div>
          <span
            data-testid="agent-detail-status-pill"
            className={statusChipClass}
            aria-label={`${draft.agent_id} ${displayedNodeStatus}`}
          >
            <span className="dot" /> {displayedNodeStatus}
          </span>
          <button
            type="button"
            className="im-btn im-btn-muted"
            disabled={openDirectChatMutation.isPending}
            onClick={() => openDirectChatMutation.mutate()}
          >
            {openDirectChatMutation.isPending ? t("agents.detail.openChatPending") : t("agents.detail.openChat")}
          </button>
        </div>
      </header>

      <div className="im-agent-panel-body">
        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.identity.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.identity.subEdit")}</p>
          </div>
          <div className="im-agent-card-grid-2">
            <div className="im-agent-field">
              <Label.Root htmlFor="agent-id">{t("agents.form.identity.agentId")}</Label.Root>
              <input id="agent-id" className="im-input im-agent-input-mono" value={draft.agent_id} disabled />
            </div>
            <div className="im-agent-field">
              <Label.Root htmlFor="owner-id">{t("agents.form.identity.owner")}</Label.Root>
              <input id="owner-id" className="im-input" value={draft.owner_id || "—"} disabled />
            </div>
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="display-name">{t("agents.form.identity.displayName")}</Label.Root>
            <input
              id="display-name"
              className="im-input"
              value={draft.display_name}
              aria-invalid={Boolean(shouldShowError("display_name"))}
              aria-describedby="display-name-help"
              onBlur={() => markTouched("display_name")}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, display_name: event.target.value });
              }}
            />
            <p id="display-name-help" className="im-agent-field-help">
              {t("agents.form.identity.displayNamePlaceholder")}
            </p>
            {shouldShowError("display_name") ? (
              <p className="im-agent-field-error">{validationErrors.display_name}</p>
            ) : null}
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="description">{t("agents.form.identity.description")}</Label.Root>
            <input
              id="description"
              className="im-input"
              value={draft.description ?? ""}
              aria-describedby="description-help"
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, description: event.target.value });
              }}
            />
            <p id="description-help" className="im-agent-field-help">
              {t("agents.form.identity.descriptionHelp")}
            </p>
          </div>
        </section>

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.behavior.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.behavior.sub")}</p>
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="system-prompt">{t("agents.form.behavior.systemPrompt")}</Label.Root>
            <textarea
              id="system-prompt"
              className="im-agent-textarea"
              value={draft.system_prompt}
              aria-invalid={Boolean(shouldShowError("system_prompt"))}
              aria-describedby="system-prompt-help"
              onBlur={() => markTouched("system_prompt")}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, system_prompt: event.target.value });
              }}
            />
            <p id="system-prompt-help" className="im-agent-field-help">
              {t("agents.form.behavior.systemPromptHelp")}
            </p>
            {shouldShowError("system_prompt") ? (
              <p className="im-agent-field-error">{validationErrors.system_prompt}</p>
            ) : null}
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="group-reply-policy">{t("agents.form.behavior.policy")}</Label.Root>
            <select
              id="group-reply-policy"
              className="im-input"
              aria-describedby="group-policy-help"
              value={draft.group_reply_policy}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, group_reply_policy: event.target.value as AgentConfig["group_reply_policy"] });
              }}
            >
              <option value="MENTION">{t("agents.form.behavior.policyOptionMention")}</option>
              <option value="ALWAYS">{t("agents.form.behavior.policyOptionAlways")}</option>
              <option value="NO_REPLY">{t("agents.form.behavior.policyOptionNoReply")}</option>
            </select>
            <p id="group-policy-help" className="im-agent-field-help">
              {t("agents.form.behavior.policyHelp")}
            </p>
          </div>
        </section>

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.access.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.access.sub")}</p>
          </div>
          <div className="im-agent-card-grid-2">
            <AllowlistSelector
              id="skills-allowlist"
              label={t("agents.form.access.skills")}
              selected={draft.skills}
              options={capabilities.skills}
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
              helpText=""
              emptySelectionText=""
              onChange={(skills) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, skills });
              }}
            />
            <AllowlistSelector
              id="tool-allowlist"
              label={t("agents.form.access.tools")}
              selected={draft.tool_allowlist}
              options={capabilities.tools}
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
              showDescriptions={false}
              helpText=""
              emptySelectionText=""
              onChange={(toolAllowlist) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, tool_allowlist: toolAllowlist });
              }}
            />
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="default-model">{t("agents.form.access.model")}</Label.Root>
            <select
              id="default-model"
              className="im-input"
              value={draft.default_model ?? ""}
              aria-describedby="default-model-help"
              disabled={detailQuery.isLoading && availableModels.length === 0}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, default_model: event.target.value || null });
              }}
            >
              <option value="">
                {platformDefaultModel
                  ? t("agents.form.access.modelPlatformDefault", { model: platformDefaultModel })
                  : t("agents.form.access.modelPlatformDefaultPlain")}
              </option>
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {model === platformDefaultModel
                    ? `${model} ${t("agents.form.access.modelDefaultSuffix")}`
                    : model}
                </option>
              ))}
            </select>
          </div>
        </section>

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.workspace.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.workspace.sub")}</p>
          </div>
          <div className="im-agent-card-grid-2">
            <div className="im-agent-field">
              <Label.Root htmlFor="workspace-root">{t("agents.form.workspace.workspaceRoot")}</Label.Root>
              <input
                id="workspace-root"
                className="im-input im-agent-input-mono"
                value={draft.workspace_root}
                disabled
              />
            </div>
            <div className="im-agent-field">
              <Label.Root htmlFor="profile-version">{t("agents.form.workspace.profileVersion")}</Label.Root>
              <input
                id="profile-version"
                className="im-input"
                value={t("agents.detail.version", { version: draft.profile_version })}
                disabled
              />
            </div>
          </div>
          <div className="im-agent-card-grid-2">
            <div className="im-agent-field">
              <Label.Root htmlFor="owning-node">{t("agents.form.workspace.owningNode")}</Label.Root>
              <input id="owning-node" className="im-input" value={`${displayedNodeName} (${displayedNodeId})`} disabled />
            </div>
            <div className="im-agent-field">
              <Label.Root htmlFor="last-updated">{t("agents.form.workspace.lastUpdated")}</Label.Root>
              <input id="last-updated" className="im-input" value={formatUpdatedAt(draft.updated_at)} disabled />
            </div>
          </div>
        </section>
      </div>

      <footer className="im-agent-footer" aria-live="polite">
        <p className={footerStatusClass}>{footerStatusText}</p>
        <div className="im-agent-footer-actions">
          <button
            className="im-btn im-btn-muted"
            type="button"
            disabled={!isDirty || mutation.isPending}
            onClick={handleDiscard}
          >
            {t("agents.detail.discard")}
          </button>
          <button className="im-btn im-btn-primary" type="submit" disabled={mutation.isPending || !isDirty}>
            {mutation.isPending ? t("agents.detail.saving") : t("agents.detail.save")}
          </button>
        </div>
      </footer>
    </form>
  );
}
