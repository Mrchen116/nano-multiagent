import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { PillSelector } from "./pill-selector";
import {
  AgentFeature,
  AgentSummary,
  createNodeAgent,
  getNodeCreateState,
  listNodes,
  NodeAgentCreateRequest,
  nodePromptPreview
} from "./im-agent-config-api";

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
    // feat-379-M5 (ISSUE-1): system_prompt no longer exposed in create form;
    // keep blank in payload for API compat — sections assembler owns the content.
    system_prompt: "",
    custom_prompt: (draft.custom_prompt ?? "").trim(),
    features: draft.features ?? {},
    skills: normalizeAllowlist(draft.skills),
    tool_allowlist: normalizeAllowlist(draft.tool_allowlist),
    default_model: normalizeText(draft.default_model ?? "") || null,
    workspace_root: null
  };
}

function validateDraft(draft: CreateAgentFormState) {
  const errors: Partial<Record<"agent_id" | "display_name", string>> = {};
  if (!draft.agent_id) {
    errors.agent_id = "Agent ID is required.";
  } else if (!/^[a-z0-9_-]+$/.test(draft.agent_id)) {
    errors.agent_id = "Lowercase letters, numbers, _ and - only.";
  }
  if (!draft.display_name) errors.display_name = "Display name is required.";
  return errors;
}

// Draft features take precedence; fall back to capability default_on when key absent.
function resolveEffectiveFeatures(
  draftFeatures: Record<string, boolean> | undefined,
  capabilityFeatures: AgentFeature[]
): Record<string, boolean> {
  const result: Record<string, boolean> = {};
  for (const feat of capabilityFeatures) {
    result[feat.key] = draftFeatures?.[feat.key] ?? feat.default_on;
  }
  return result;
}

const EMPTY_DRAFT: CreateAgentFormState = {
  agent_id: "",
  owner_id: "",
  display_name: "",
  description: "",
  system_prompt: "",
  custom_prompt: "",
  features: {},
  skills: [],
  tool_allowlist: [],
  group_reply_policy: "MENTION",
  default_model: null,
  workspace_root: null
};

// feat-379-M5 (ISSUE-1): Behavior card for agent creation — same design as agent-detail-page.tsx
// BehaviorCard component. Custom Instructions (custom_prompt) + Features toggles + Group Reply
// Policy + collapsible Preview panel.
interface CreateBehaviorCardProps {
  draft: CreateAgentFormState;
  capabilityFeatures: AgentFeature[];
  selectedNodeId: string;
  onCustomPromptChange: (value: string) => void;
  onFeatureToggle: (key: string, value: boolean) => void;
  onPolicyChange: (value: string) => void;
}

function CreateBehaviorCard({
  draft,
  capabilityFeatures,
  selectedNodeId,
  onCustomPromptChange,
  onFeatureToggle,
  onPolicyChange
}: CreateBehaviorCardProps) {
  const { t } = useTranslation();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const effectiveFeatures = useMemo(
    () => resolveEffectiveFeatures(draft.features, capabilityFeatures),
    [draft.features, capabilityFeatures]
  );

  // feat-379-M9 (決策 11): use node-level preview endpoint — no agent needed yet.
  // feat-379-M9 (決策 14): tool_ids comes directly from draft.tool_allowlist; the old
  // effectiveToolIds hack that injected capability-inferred tools is removed because
  // _build_tool_names() now correctly includes all tools (R1 fix).
  const fetchPreview = useCallback(async () => {
    if (!selectedNodeId) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const text = await nodePromptPreview(selectedNodeId, {
        features: effectiveFeatures,
        custom_prompt: draft.custom_prompt ?? "",
        tool_ids: draft.tool_allowlist ?? [],
        skill_ids: draft.skills ?? [],
        agent_id_hint: draft.agent_id || undefined
      });
      setPreviewText(text);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  }, [selectedNodeId, effectiveFeatures, draft.custom_prompt, draft.tool_allowlist, draft.skills, draft.agent_id]);

  useEffect(() => {
    if (!previewOpen) return;
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => { void fetchPreview(); }, 600);
    return () => { if (previewTimer.current) clearTimeout(previewTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewOpen, draft.custom_prompt, draft.features, draft.tool_allowlist, draft.skills, draft.agent_id]);

  function handlePreviewToggle() {
    if (!previewOpen) {
      setPreviewOpen(true);
      void fetchPreview();
    } else {
      setPreviewOpen(false);
    }
  }

  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">{t("agents.form.behavior.title")}</h3>
        <p className="im-agent-card-sub">{t("agents.form.behavior.sub")}</p>
      </div>

      {/* Custom Instructions — optional textarea; empty is valid */}
      <div className="im-agent-field">
        <Label.Root htmlFor="custom-instructions">{t("agents.form.behavior.customInstructions")}</Label.Root>
        <textarea
          id="custom-instructions"
          className="im-agent-textarea"
          value={draft.custom_prompt ?? ""}
          placeholder={t("agents.form.behavior.customInstructionsPlaceholder")}
          aria-describedby="custom-instructions-help"
          rows={4}
          onChange={(e) => onCustomPromptChange(e.target.value)}
        />
        <p id="custom-instructions-help" className="im-agent-field-help">
          {t("agents.form.behavior.customInstructionsHelp")}
        </p>
      </div>

      {/* Features section — rendered only when capabilities list is non-empty */}
      {capabilityFeatures.length > 0 && (
        <div data-testid="features-section" className="im-agent-field">
          <span className="text-[13px] font-semibold text-slate-900">{t("agents.form.behavior.features")}</span>
          <p className="im-agent-field-help" style={{ marginTop: 2 }}>{t("agents.form.behavior.featuresHelp")}</p>
          <div className="grid gap-[6px] mt-2">
            {capabilityFeatures.map((feat) => {
              // feat-379-M9 (決策 12): features are always enabled — disabled state removed.
              // All tools are available at node level (R1 fix); user can freely toggle features
              // and the corresponding tool auto-joins the allowlist via linkage logic.
              const checked = effectiveFeatures[feat.key] ?? feat.default_on;
              return (
                <label
                  key={feat.key}
                  className={`flex items-start gap-3 rounded-xl border px-3 py-[10px] transition-colors ${
                    checked
                      ? "border-teal-300 bg-teal-50/60 cursor-pointer"
                      : "border-[var(--im-border)] bg-white/90 cursor-pointer hover:border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    data-feature-key={feat.key}
                    checked={checked}
                    className="im-feature-checkbox mt-[2px] shrink-0"
                    onChange={(e) => onFeatureToggle(feat.key, e.target.checked)}
                  />
                  <div className="min-w-0">
                    <p className="m-0 text-[13px] font-semibold text-slate-900 leading-5">{t(feat.label_i18n)}</p>
                    <p className="m-0 text-[11px] text-slate-500 leading-[1.4]">{t(feat.help_i18n)}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* Group reply policy */}
      <div className="im-agent-field">
        <Label.Root htmlFor="group-reply-policy">{t("agents.form.behavior.policy")}</Label.Root>
        <select
          id="group-reply-policy"
          className="im-input"
          aria-describedby="group-policy-help"
          value={draft.group_reply_policy}
          onChange={(e) => onPolicyChange(e.target.value)}
        >
          <option value="MENTION">{t("agents.form.behavior.policyOptionMention")}</option>
          <option value="ALWAYS">{t("agents.form.behavior.policyOptionAlways")}</option>
          <option value="NO_REPLY">{t("agents.form.behavior.policyOptionNoReply")}</option>
        </select>
        <p id="group-policy-help" className="im-agent-field-help">
          {t("agents.form.behavior.policyHelp")}
        </p>
      </div>

      {/* Collapsible preview — mirrors tool-calls-panel aria-expanded + ▸/▾ pattern */}
      <div>
        <button
          type="button"
          className={`im-behavior-preview-toggle ${previewOpen ? "im-behavior-preview-toggle--open" : ""}`}
          onClick={handlePreviewToggle}
          aria-expanded={previewOpen}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "none",
            border: "none",
            padding: "6px 0",
            cursor: "pointer",
            fontSize: "0.8rem",
            fontWeight: 600,
            color: "var(--im-accent, oklch(0.55 0.18 180))"
          }}
        >
          <span aria-hidden="true">{previewOpen ? "▾" : "▸"}</span>
          <span>{t("agents.form.behavior.previewToggle")}</span>
        </button>

        {previewOpen && (
          <div className="im-behavior-preview-panel im-behavior-preview-panel--open" style={{ marginTop: 8 }}>
            {previewLoading && (
              <p className="text-[11px] text-slate-500">{t("agents.form.behavior.previewLoading")}</p>
            )}
            {previewError && (
              <p className="text-[11px] text-rose-600">{t("agents.form.behavior.previewError")}</p>
            )}
            {!previewLoading && !previewError && previewText !== null && (
              <pre
                style={{
                  fontSize: "0.72rem",
                  lineHeight: 1.5,
                  color: "var(--im-muted, oklch(0.50 0.01 240))",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  background: "oklch(0.96 0.004 240)",
                  border: "1px solid var(--im-border)",
                  borderRadius: 8,
                  padding: "10px 12px",
                  maxHeight: 360,
                  overflowY: "auto",
                  margin: 0
                }}
              >
                {previewText}
              </pre>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

export function AgentCreatePage() {
  const { nodeId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const [draft, setDraft] = useState<CreateAgentFormState>(EMPTY_DRAFT);
  const [selectedNodeId, setSelectedNodeId] = useState(nodeId);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const nodesQuery = useQuery({
    queryKey: ["settings", "agents", "create", "nodes"],
    queryFn: listNodes,
    staleTime: 30_000
  });

  useEffect(() => {
    if (selectedNodeId || !nodesQuery.data || nodesQuery.data.length === 0) return;
    const defaultNode = nodesQuery.data.find((node) => node.status !== "offline") ?? nodesQuery.data[0];
    setSelectedNodeId(defaultNode?.node_id ?? "");
  }, [nodesQuery.data, selectedNodeId]);

  const createStateQuery = useQuery({
    queryKey: ["settings", "nodes", selectedNodeId, "create-state"],
    queryFn: () => getNodeCreateState(selectedNodeId),
    enabled: selectedNodeId.length > 0,
    staleTime: 30_000
  });

  const normalizedDraft = useMemo(() => normalizeDraft(draft), [draft]);
  const validationErrors = useMemo(() => validateDraft(normalizedDraft), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const capabilities = createStateQuery.data?.capabilities;
  const node = createStateQuery.data?.node ?? null;
  const availableModels = capabilities?.model_options ?? [];
  const nodes = nodesQuery.data ?? [];
  const selectedNode = nodes.find((item) => item.node_id === selectedNodeId) ?? node;
  const nodeLabel = selectedNode?.alias ?? capabilities?.node_name ?? node?.node_name ?? selectedNodeId;
  const nodeStatus = (capabilities?.node_status ?? node?.status ?? "unknown").toLowerCase();
  const isNodeOnline = nodeStatus === "online";
  const queryErrorDetail =
    createStateQuery.error instanceof Error
      ? createStateQuery.error.message.split(" failed: ").at(-1) ?? createStateQuery.error.message
      : "Unable to load this node.";

  const mutation = useMutation({
    mutationFn: (next: CreateAgentFormState) => createNodeAgent(selectedNodeId, next),
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

  function markTouched(field: "agent_id" | "display_name") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "agent_id" | "display_name") {
    return (hasSubmitted || touched[field]) && validationErrors[field];
  }

  if ((nodesQuery.isLoading || createStateQuery.isLoading) && !capabilities) {
    return <p className="text-sm text-slate-500">{t("common.loading")}</p>;
  }

  if ((nodesQuery.isError || createStateQuery.isError) && !capabilities) {
    return (
      <section className="grid gap-3 rounded-2xl border border-rose-200 bg-rose-50/80 p-5">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">{t("agents.loadError")}</p>
          <p className="text-sm text-rose-600">
            {nodesQuery.error instanceof Error ? nodesQuery.error.message : queryErrorDetail}
          </p>
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

  const border = "oklch(0.87 0.006 240)";

  return (
    <form
      data-testid="agent-create"
      className="im-agent-panel"
      onSubmit={(event) => {
        event.preventDefault();
        setHasSubmitted(true);
        setErrorMessage(null);
        if (hasValidationErrors || !isNodeOnline || !selectedNodeId) return;
        mutation.mutate(normalizedDraft);
      }}
    >
      <header
        className="im-agent-panel-header"
        style={{
          background: "#fff",
          padding: isMobile ? "14px 16px" : "18px 28px 14px",
          paddingTop: isMobile ? "calc(14px + env(safe-area-inset-top, 0px))" : "18px"
        }}
      >
        <div className="im-agent-panel-header-row">
          {isMobile && (
            <button
              type="button"
              onClick={() => navigate("/settings/agents")}
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                border: "none",
                background: "oklch(0.91 0.006 240)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
                color: "oklch(0.40 0.01 240)",
                flexShrink: 0
              }}
            >
              ‹
            </button>
          )}
          <div style={{ flex: 1 }}>
            <h2
              className="im-agent-panel-title"
              style={{ fontSize: isMobile ? 18 : 18, fontWeight: 800, letterSpacing: "-0.02em" }}
            >
              {t("agents.create.title")}
            </h2>
            <p className="im-agent-panel-subtitle">
              {t("agents.create.subtitle")}
            </p>
          </div>
          {!isMobile && (
            <div style={{ display: "flex", gap: 8 }}>
              <Link
                className="im-btn im-btn-muted"
                to="/settings/agents"
                style={{ textDecoration: "none" }}
              >
                {t("agents.create.cancel")}
              </Link>
              <button className="im-btn im-btn-primary" type="submit" disabled={mutation.isPending || !isNodeOnline}>
                {t("agents.create.submit")}
              </button>
            </div>
          )}
        </div>
      </header>

      <div
        className="im-agent-panel-body"
        style={{ padding: isMobile ? "14px 14px" : "20px 28px", gap: 14 }}
      >
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
                  setDraft({ ...draft, agent_id: event.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") });
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
            <select
              id="owning-node"
              className="im-input"
              value={selectedNodeId}
              onChange={(event) => {
                setSelectedNodeId(event.target.value);
                setErrorMessage(null);
              }}
            >
              <option value="">{t("settings.account.defaults.selectNode")}</option>
              {nodes.filter((item) => item.status !== "offline").map((item) => (
                <option key={item.node_id} value={item.node_id}>
                  {item.alias || item.node_name} ({item.status})
                </option>
              ))}
            </select>
            <p className="im-agent-field-help">{t("agents.form.identity.owningNodeHelp")}</p>
          </div>
        </section>

        {/* feat-379-M5 (ISSUE-1): Behavior card — Custom Instructions + Features + Preview */}
        <CreateBehaviorCard
          draft={draft}
          capabilityFeatures={capabilities.features ?? []}
          selectedNodeId={selectedNodeId}
          onCustomPromptChange={(value) => {
            setErrorMessage(null);
            setDraft({ ...draft, custom_prompt: value });
          }}
          onFeatureToggle={(key, value) => {
            setErrorMessage(null);
            // feat-379-M9 (決策 12): tick → add requires_tool to allowlist; untick → keep tool.
            const capFeats = capabilities?.features ?? [];
            const requiresTool = capFeats.find((f) => f.key === key)?.requires_tool ?? null;
            const nextAllowlist =
              value && requiresTool && !draft.tool_allowlist.includes(requiresTool)
                ? [...draft.tool_allowlist, requiresTool]
                : draft.tool_allowlist;
            setDraft({ ...draft, features: { ...(draft.features ?? {}), [key]: value }, tool_allowlist: nextAllowlist });
          }}
          onPolicyChange={(value) => {
            setErrorMessage(null);
            setDraft({ ...draft, group_reply_policy: value });
          }}
        />

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.access.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.access.sub")}</p>
          </div>
          <div className="im-agent-card-grid-2">
            <PillSelector
              testId="pill-selector-skills"
              label={t("agents.form.access.skills")}
              selected={draft.skills}
              options={capabilities.skills}
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              onChange={(skills) => {
                setErrorMessage(null);
                setDraft({ ...draft, skills });
              }}
            />
            <PillSelector
              testId="pill-selector-tools"
              label={t("agents.form.access.tools")}
              selected={draft.tool_allowlist}
              options={capabilities.tools}
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              onChange={(toolAllowlist) => {
                setErrorMessage(null);
                // feat-379-M9 (決策 12): removed tool → uncheck any feature that requires it.
                const capFeats = capabilities?.features ?? [];
                const removed = draft.tool_allowlist.filter((t) => !toolAllowlist.includes(t));
                const nextFeatures = { ...(draft.features ?? {}) };
                for (const tool of removed) {
                  for (const feat of capFeats) {
                    if (feat.requires_tool === tool) nextFeatures[feat.key] = false;
                  }
                }
                setDraft({ ...draft, tool_allowlist: toolAllowlist, features: nextFeatures });
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

        {/* Error / status banner */}
        {(errorMessage || (hasSubmitted && hasValidationErrors) || (hasSubmitted && !isNodeOnline)) && (
          <div
            className={footerStatusClass}
            style={{
              background: "#fff",
              borderRadius: 12,
              border: `1px solid ${border}`,
              padding: "10px 16px",
              fontSize: "0.78rem",
              fontWeight: 600
            }}
          >
            {footerStatusText}
          </div>
        )}

        {/* Bottom action bar */}
        <div
          style={{
            background: "#fff",
            borderRadius: 12,
            border: `1px solid ${border}`,
            padding: "14px 16px",
            display: "flex",
            gap: 8,
            justifyContent: isMobile ? "stretch" : "flex-end",
            paddingBottom: isMobile ? "calc(14px + env(safe-area-inset-bottom, 0px))" : "14px"
          }}
        >
          {!isMobile && (
            <Link
              className="im-btn im-btn-muted"
              to="/settings/agents"
              style={{ textDecoration: "none" }}
            >
              {t("agents.create.cancel")}
            </Link>
          )}
          <button
            className="im-btn im-btn-primary"
            type="submit"
            disabled={mutation.isPending || !isNodeOnline}
            style={{ flex: isMobile ? 1 : undefined }}
          >
            {mutation.isPending ? t("agents.detail.saving") : t("agents.create.submitArrow")}
          </button>
        </div>
      </div>
    </form>
  );
}
