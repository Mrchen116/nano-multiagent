import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { AllowlistSelector } from "./allowlist-selector";
import { AgentSummary, createNodeAgent, getNodeCreateState, NodeAgentCreateRequest } from "./im-agent-config-api";

type CreateAgentFormState = NodeAgentCreateRequest;

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function normalizeText(value: string) {
  return value.trim();
}

function normalizeDraft(draft: CreateAgentFormState): CreateAgentFormState {
  return {
    ...draft,
    agent_id: normalizeText(draft.agent_id),
    display_name: normalizeText(draft.display_name),
    description: normalizeText(draft.description),
    system_prompt: draft.system_prompt.trim(),
    skills: normalizeAllowlist(draft.skills),
    tool_allowlist: normalizeAllowlist(draft.tool_allowlist),
    default_model: normalizeText(draft.default_model ?? "") || null,
    workspace_root: null
  };
}

function validateDraft(draft: CreateAgentFormState) {
  const errors: Partial<Record<"agent_id" | "display_name" | "system_prompt", string>> = {};
  if (!draft.agent_id) {
    errors.agent_id = "Agent ID is required.";
  } else if (/\s/.test(draft.agent_id)) {
    errors.agent_id = "Agent ID cannot contain spaces.";
  }
  if (!draft.display_name) errors.display_name = "Display name is required.";
  if (!draft.system_prompt) errors.system_prompt = "System prompt is required.";
  return errors;
}

const EMPTY_DRAFT: CreateAgentFormState = {
  agent_id: "",
  owner_id: "",
  display_name: "",
  description: "",
  system_prompt: "",
  skills: [],
  tool_allowlist: [],
  group_reply_policy: "MENTION",
  default_model: null,
  workspace_root: null
};

export function AgentCreatePage() {
  const { nodeId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [draft, setDraft] = useState<CreateAgentFormState>(EMPTY_DRAFT);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const createStateQuery = useQuery({
    queryKey: ["settings", "nodes", nodeId, "create-state"],
    queryFn: () => getNodeCreateState(nodeId),
    staleTime: 30_000
  });

  useEffect(() => {
    const defaultSystemPrompt = createStateQuery.data?.capabilities.default_system_prompt?.trim() ?? "";
    if (!defaultSystemPrompt) return;
    setDraft((current) => {
      if (current.system_prompt.trim().length > 0) return current;
      return { ...current, system_prompt: defaultSystemPrompt };
    });
  }, [createStateQuery.data?.capabilities.default_system_prompt]);

  const normalizedDraft = useMemo(() => normalizeDraft(draft), [draft]);
  const validationErrors = useMemo(() => validateDraft(normalizedDraft), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const capabilities = createStateQuery.data?.capabilities;
  const node = createStateQuery.data?.node ?? null;
  const availableModels = capabilities?.model_options ?? [];
  const nodeLabel = capabilities?.node_name ?? node?.node_name ?? nodeId;
  const nodeStatus = (capabilities?.node_status ?? node?.status ?? "unknown").toLowerCase();
  const isNodeOnline = nodeStatus === "online";
  const queryErrorDetail =
    createStateQuery.error instanceof Error
      ? createStateQuery.error.message.split(" failed: ").at(-1) ?? createStateQuery.error.message
      : "Unable to load this node.";

  const mutation = useMutation({
    mutationFn: (next: CreateAgentFormState) => createNodeAgent(nodeId, next),
    onSuccess: async (created) => {
      setErrorMessage(null);
      queryClient.setQueryData(["settings", "agents", created.agent_id], created);
      queryClient.setQueryData(["settings", "agents"], (current: AgentSummary[] | undefined) => {
        if (!current) return [created];
        const next = current.filter((agent) => agent.agent_id !== created.agent_id);
        return [created, ...next];
      });
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "nodes"] });
      navigate(`/settings/agents/${created.agent_id}`);
    },
    onError: (error) => {
      setErrorMessage(
        error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Create failed"
      );
    }
  });

  function markTouched(field: "agent_id" | "display_name" | "system_prompt") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "agent_id" | "display_name" | "system_prompt") {
    return (hasSubmitted || touched[field]) && validationErrors[field];
  }

  if (createStateQuery.isLoading && !capabilities) {
    return <p className="text-sm text-slate-500">{t("common.loading")}</p>;
  }

  if (createStateQuery.isError && !capabilities) {
    return (
      <section className="grid gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">{t("agents.loadError")}</p>
          <p className="text-sm text-rose-600">{queryErrorDetail}</p>
        </div>
        <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void createStateQuery.refetch()}>
          {t("agents.retry")}
        </button>
      </section>
    );
  }

  if (!capabilities) {
    return <p className="text-sm text-slate-500">{t("common.loading")}</p>;
  }

  const statusChipClass = isNodeOnline ? "im-agent-panel-status-chip online" : "im-agent-panel-status-chip";

  let footerStatusClass = "im-agent-footer-status";
  let footerStatusText = t("agents.create.subtitle");
  if (errorMessage) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = errorMessage;
  } else if (hasSubmitted && hasValidationErrors) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = t("agents.form.errors.required");
  } else if (hasSubmitted && !isNodeOnline) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = `${nodeLabel}: ${nodeStatus}`;
  } else if (mutation.isPending) {
    footerStatusText = t("agents.detail.saving");
  }

  return (
    <form
      data-testid="agent-create"
      className="im-agent-panel"
      onSubmit={(event) => {
        event.preventDefault();
        setHasSubmitted(true);
        setErrorMessage(null);
        if (hasValidationErrors || !isNodeOnline) return;
        mutation.mutate(normalizedDraft);
      }}
    >
      <header className="im-agent-panel-header">
        <div className="im-agent-panel-header-row">
          <div style={{ flex: 1 }}>
            <h2 className="im-agent-panel-title">{t("agents.create.title")}</h2>
            <p className="im-agent-panel-subtitle">
              {nodeLabel} · {nodeId}
            </p>
          </div>
          <span className={statusChipClass} aria-label={`${nodeId} ${nodeStatus}`}>
            <span className="dot" /> {nodeStatus}
          </span>
        </div>
      </header>

      <div className="im-agent-panel-body">
        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.identity.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.identity.subNew")}</p>
          </div>
          <div className="im-agent-card-grid-2">
            <div className="im-agent-field">
              <Label.Root htmlFor="agent-id">{t("agents.form.identity.agentIdRequired")}</Label.Root>
              <input
                id="agent-id"
                className="im-input im-agent-input-mono"
                value={draft.agent_id}
                aria-invalid={Boolean(shouldShowError("agent_id"))}
                aria-describedby="agent-id-help"
                placeholder={t("agents.form.identity.agentIdPlaceholder")}
                onBlur={() => markTouched("agent_id")}
                onChange={(event) => {
                  setErrorMessage(null);
                  setDraft({ ...draft, agent_id: event.target.value });
                }}
              />
              <p id="agent-id-help" className="im-agent-field-help">
                {t("agents.form.identity.agentIdHelp")}
              </p>
              {shouldShowError("agent_id") ? (
                <p className="im-agent-field-error">{validationErrors.agent_id}</p>
              ) : null}
            </div>
            <div className="im-agent-field">
              <Label.Root htmlFor="display-name">{t("agents.form.identity.displayNameRequired")}</Label.Root>
              <input
                id="display-name"
                className="im-input"
                value={draft.display_name}
                aria-invalid={Boolean(shouldShowError("display_name"))}
                aria-describedby="display-name-help"
                placeholder={t("agents.form.identity.displayNamePlaceholder")}
                onBlur={() => markTouched("display_name")}
                onChange={(event) => {
                  setErrorMessage(null);
                  setDraft({ ...draft, display_name: event.target.value });
                }}
              />
              {shouldShowError("display_name") ? (
                <p className="im-agent-field-error">{validationErrors.display_name}</p>
              ) : null}
            </div>
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="description">{t("agents.form.identity.description")}</Label.Root>
            <input
              id="description"
              className="im-input"
              value={draft.description}
              aria-describedby="description-help"
              placeholder={t("agents.form.identity.descriptionPlaceholder")}
              onChange={(event) => {
                setErrorMessage(null);
                setDraft({ ...draft, description: event.target.value });
              }}
            />
            <p id="description-help" className="im-agent-field-help">
              {t("agents.form.identity.descriptionHelp")}
            </p>
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="owning-node">{t("agents.form.identity.owningNodeRequired")}</Label.Root>
            <input id="owning-node" className="im-input" value={`${nodeLabel} (${nodeId})`} disabled />
            <p className="im-agent-field-help">{t("agents.form.identity.owningNodeHelp")}</p>
          </div>
        </section>

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.behavior.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.behavior.sub")}</p>
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="system-prompt">{t("agents.form.behavior.systemPromptRequired")}</Label.Root>
            <textarea
              id="system-prompt"
              className="im-agent-textarea"
              value={draft.system_prompt}
              aria-invalid={Boolean(shouldShowError("system_prompt"))}
              aria-describedby="system-prompt-help"
              placeholder={t("agents.form.behavior.systemPromptPlaceholder")}
              onBlur={() => markTouched("system_prompt")}
              onChange={(event) => {
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
              aria-describedby="group-reply-policy-help"
              value={draft.group_reply_policy}
              onChange={(event) => {
                setErrorMessage(null);
                setDraft({ ...draft, group_reply_policy: event.target.value });
              }}
            >
              <option value="MENTION">{t("agents.form.behavior.policyOptionMention")}</option>
              <option value="ALWAYS">{t("agents.form.behavior.policyOptionAlways")}</option>
              <option value="NO_REPLY">{t("agents.form.behavior.policyOptionNoReply")}</option>
            </select>
            <p id="group-reply-policy-help" className="im-agent-field-help">
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
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              helpText=""
              emptySelectionText=""
              onChange={(skills) => {
                setErrorMessage(null);
                setDraft({ ...draft, skills });
              }}
            />
            <AllowlistSelector
              id="tool-allowlist"
              label={t("agents.form.access.tools")}
              selected={draft.tool_allowlist}
              options={capabilities.tools}
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              showDescriptions={false}
              helpText=""
              emptySelectionText=""
              onChange={(toolAllowlist) => {
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
              onChange={(event) => {
                setErrorMessage(null);
                setDraft({ ...draft, default_model: event.target.value || null });
              }}
            >
              <option value="">
                {capabilities.platform_default_model
                  ? t("agents.form.access.modelPlatformDefault", { model: capabilities.platform_default_model })
                  : t("agents.form.access.modelPlatformDefaultPlain")}
              </option>
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {model === capabilities.platform_default_model
                    ? `${model} ${t("agents.form.access.modelDefaultSuffix")}`
                    : model}
                </option>
              ))}
            </select>
          </div>
        </section>
      </div>

      <footer className="im-agent-footer" aria-live="polite">
        <p className={footerStatusClass}>{footerStatusText}</p>
        <div className="im-agent-footer-actions">
          <Link className="im-btn im-btn-muted" to="/settings/agents">
            {t("agents.create.cancel")}
          </Link>
          <button className="im-btn im-btn-primary" type="submit" disabled={mutation.isPending || !isNodeOnline}>
            {mutation.isPending ? t("agents.detail.saving") : t("agents.create.submit")}
          </button>
        </div>
      </footer>
    </form>
  );
}
