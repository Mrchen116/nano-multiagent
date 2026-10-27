import { changeCapability } from "@nano/product-contracts/capabilities";
import { capabilityCatalog, useCapabilityEditor } from "./capability-editor";
import { ApprovalModeField, type ApprovalMode } from "./approval-mode-field";
import "./agent-settings.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { AgentsRailDesktop } from "./agents-rail-desktop";
import {
  effectiveReasoningModel,
  isStaleReasoningEffort,
  ModelReasoningField,
  normalizeReasoningEffort,
  reasoningEffortAfterModelChange,
} from "./model-reasoning-field";
import { fallbacksAfterPrimaryChange, ModelFallbackField } from "./model-fallback-field";
import { PillSelector } from "./pill-selector";
import { SkillSourceSelector } from "./skill-source-selector";
import {
  AgentFeature,
  AgentSummary,
  createNodeAgent,
  getNodeCreateState,
  getNodeApprovalRules,
  getAgentConfigRequestDetail,
  getAgentConfigRequestStatus,
  isConfigApplyPendingError,
  listNodes,
  ModelOption,
  NodeAgentCreateRequest,
  nodePromptPreview
} from "./im-agent-config-api";

type CreateAgentFormState = NodeAgentCreateRequest;
type WorkspaceMode = "default" | "custom";

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function sameStringList(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function defaultNames(options: { name: string; default_on?: boolean }[]) {
  return normalizeAllowlist(
    options
      .filter((option) => option.default_on === true)
      .map((option) => option.name)
  );
}

function normalizeText(value: string) {
  return value.trim();
}

function normalizeDraft(draft: CreateAgentFormState, modelOptions: ModelOption[]): CreateAgentFormState {
  const defaultModel = normalizeText(draft.default_model ?? "") || null;
  return {
    ...draft,
    agent_id: normalizeText(draft.agent_id),
    display_name: normalizeText(draft.display_name),
    description: normalizeText(draft.description),
    custom_prompt: (draft.custom_prompt ?? "").trim(),
    features: draft.features ?? {},
    skills: normalizeAllowlist(draft.skills),
    tool_allowlist: normalizeAllowlist(draft.tool_allowlist),
    default_model: defaultModel,
    model_fallbacks: fallbacksAfterPrimaryChange(draft.model_fallbacks ?? [], defaultModel),
    reasoning_effort: normalizeReasoningEffort(modelOptions, defaultModel, draft.reasoning_effort),
    workspace_root: normalizeText(draft.workspace_root ?? "") || null,
    confirm_existing_workspace: draft.confirm_existing_workspace ?? false
  };
}

function validateDraft(draft: CreateAgentFormState, t: (key: string) => string) {
  const errors: Partial<Record<"agent_id" | "display_name", string>> = {};
  if (!draft.agent_id) {
    errors.agent_id = t("agents.form.errors.agentIdRequired");
  } else if (!/^[a-z0-9_-]+$/.test(draft.agent_id)) {
    errors.agent_id = t("agents.form.errors.agentIdInvalid");
  }
  if (!draft.display_name) errors.display_name = t("agents.form.errors.displayNameRequired");
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
  custom_prompt: "",
  features: {},
  skills: [],
  skills_selection_mode: "explicit_denylist",
  tool_allowlist: [],
  work_mode: "single_thread",
  group_reply_policy: "MENTION",
  default_model: null,
  model_fallbacks: [],
  reasoning_effort: null,
  approval_mode: null,
  workspace_root: null,
  confirm_existing_workspace: false
};

// feat-379-M5 (ISSUE-1): Behavior card for agent creation — same design as agent-detail-page.tsx
// BehaviorCard component. Custom Instructions (custom_prompt) + Features toggles + Group Reply
// Policy + collapsible Preview panel.
interface CreateBehaviorCardProps {
  draft: CreateAgentFormState;
  inheritedRules?: "nano" | "codex" | "dsh" | null;
  capabilityFeatures: AgentFeature[];
  selectedNodeId: string;
  workspaceMode: WorkspaceMode;
  workspaceRoot: string | null;
  onApprovalModeChange: (value: ApprovalMode) => void;
  onCustomPromptChange: (value: string) => void;
  onFeatureToggle: (key: string, value: boolean) => void;
  onPolicyChange: (value: string) => void;
}

function CreateBehaviorCard({
  draft,
  capabilityFeatures,
  inheritedRules,
  selectedNodeId,
  workspaceMode,
  workspaceRoot,
  onApprovalModeChange,
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
        ...(draft.work_mode === "global" ? { work_mode: "global" as const } : {}),
        skill_ids: draft.skills ?? [],
        skills_selection_mode: draft.skills_selection_mode,
        agent_id_hint: draft.agent_id || undefined,
        workspace_mode: workspaceMode,
        workspace_root: workspaceMode === "custom" ? workspaceRoot : null
      });
      setPreviewText(text);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  }, [
    selectedNodeId,
    effectiveFeatures,
    draft.custom_prompt,
    draft.tool_allowlist,
    draft.work_mode,
    draft.skills,
    draft.agent_id,
    workspaceMode,
    workspaceRoot
  ]);

  useEffect(() => {
    if (!previewOpen) return;
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => { void fetchPreview(); }, 600);
    return () => { if (previewTimer.current) clearTimeout(previewTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    previewOpen,
    draft.custom_prompt,
    draft.features,
    draft.tool_allowlist,
    draft.work_mode,
    draft.skills,
    draft.agent_id,
    workspaceMode,
    workspaceRoot
  ]);

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
      </div>

      {/* Custom Instructions — optional textarea; empty is valid */}
      <ApprovalModeField inheritedRules={inheritedRules} value={draft.approval_mode} onChange={onApprovalModeChange} />

      <div className="im-agent-field">
        <Label.Root htmlFor="custom-instructions">{t("agents.form.behavior.customInstructions")}</Label.Root>
        <textarea
          id="custom-instructions"
          className="im-agent-textarea"
          value={draft.custom_prompt ?? ""}
          placeholder={t("agents.form.behavior.customInstructionsPlaceholder")}
          rows={4}
          onChange={(e) => onCustomPromptChange(e.target.value)}
        />
      </div>

      {/* Features section — rendered only when capabilities list is non-empty */}
      {capabilityFeatures.length > 0 && (
        <div data-testid="features-section" className="im-agent-field">
          <span className="text-[13px] font-semibold text-slate-900">{t("agents.form.behavior.features")}</span>
          <div className="im-settings-features">
            {capabilityFeatures.map((feat) => {
              const checked = effectiveFeatures[feat.key] ?? feat.default_on;
              return (
                <label
                  key={feat.key}
                  className="im-settings-feature"
                >
                  <input
                    type="checkbox"
                    data-feature-key={feat.key}
                    aria-labelledby={`feature-${feat.key}-label`}
                    aria-describedby={`feature-${feat.key}-help`}
                    checked={checked}
                    className="im-feature-checkbox mt-[2px] shrink-0"
                    onChange={(e) => onFeatureToggle(feat.key, e.target.checked)}
                  />
                  <div className="min-w-0">
                    <p id={`feature-${feat.key}-label`} className="im-settings-feature-name">{t(feat.label_i18n, feat.key)}</p>
                    <p id={`feature-${feat.key}-help`} className="im-settings-feature-help">{t(feat.help_i18n, "")}</p>
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
          value={draft.group_reply_policy}
          onChange={(e) => onPolicyChange(e.target.value)}
        >
          <option value="MENTION">{t("agents.form.behavior.policyOptionMention")}</option>
          <option value="ALWAYS">{t("agents.form.behavior.policyOptionAlways")}</option>
          <option value="NO_REPLY">{t("agents.form.behavior.policyOptionNoReply")}</option>
        </select>
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
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>("default");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [existingConfirmationRequired, setExistingConfirmationRequired] = useState(false);
  const [existingConfirmed, setExistingConfirmed] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [applyPending, setApplyPending] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [isDirty, setIsDirty] = useState(false);
  const allowExitRef = useRef(false);
  const autoDefaultToolsRef = useRef<string[]>([]);
  const toolsEditedRef = useRef(false);
  const blocker = useBlocker(() => isDirty && !allowExitRef.current);

  const nodesQuery = useQuery({
    // Shares the agents list/rail cache for the same /im/v1/nodes payload so
    // the create page never issues a duplicate request or shows divergent nodes.
    queryKey: ["settings", "agents", "nodes-status"],
    queryFn: listNodes,
    staleTime: 30_000
  });

  useEffect(() => {
    if (selectedNodeId || !nodesQuery.data || nodesQuery.data.length === 0) return;
    const defaultNode = nodesQuery.data.find((node) => node.status !== "offline") ?? nodesQuery.data[0];
    setSelectedNodeId(defaultNode?.node_id ?? "");
  }, [nodesQuery.data, selectedNodeId]);

  useEffect(() => {
    toolsEditedRef.current = false;
    autoDefaultToolsRef.current = [];
    setDraft((current) => ({
      ...current,
      skills: [],
      tool_allowlist: [],
      default_model: null,
      model_fallbacks: [],
      reasoning_effort: null,
    }));
    setWorkspaceError(null);
    setExistingConfirmationRequired(false);
    setExistingConfirmed(false);
  }, [selectedNodeId]);

  const createStateQuery = useQuery({
    queryKey: ["settings", "nodes", selectedNodeId, "create-state"],
    queryFn: () => getNodeCreateState(selectedNodeId),
    enabled: selectedNodeId.length > 0,
    staleTime: 30_000
  });

  const capabilities = createStateQuery.data?.capabilities;
  const capabilityEditor = useCapabilityEditor(draft, setDraft, capabilities);
  const modelOptions = capabilities?.model_options ?? [];
  const platformDefaultModel = capabilities?.platform_default_model ?? null;
  const normalizedDraft = useMemo(() => {
    const normalized = normalizeDraft(draft, modelOptions);
    return {
      ...normalized,
      workspace_root: workspaceMode === "custom" ? normalized.workspace_root : null,
      confirm_existing_workspace:
        workspaceMode === "custom" && existingConfirmationRequired && existingConfirmed
    };
  }, [draft, existingConfirmationRequired, existingConfirmed, modelOptions, workspaceMode]);
  const validationErrors = useMemo(() => validateDraft(normalizedDraft, t), [normalizedDraft, t]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const hasStaleReasoning = isStaleReasoningEffort(
    modelOptions,
    effectiveReasoningModel(draft.default_model, platformDefaultModel),
    draft.reasoning_effort,
  );
  const node = createStateQuery.data?.node ?? null;
  const availableModels = capabilities?.model_options ?? [];
  const nodes = nodesQuery.data ?? [];
  const selectedNode = nodes.find((item) => item.node_id === selectedNodeId) ?? node;
  const nodeLabel = selectedNode?.alias ?? capabilities?.node_name ?? node?.node_name ?? selectedNodeId;
  const nodeStatus = (capabilities?.node_status ?? node?.status ?? "unknown").toLowerCase();
  const isNodeOnline = nodeStatus === "online";
  const resolvedDefaultWorkspacePath = capabilities?.default_workspace_template
    ? capabilities.default_workspace_template.replace(
        "{agent_id}",
        draft.agent_id.trim() || t("agents.form.workspaceCreate.agentIdPlaceholder"),
      )
    : null;
  const approvalWorkspace = workspaceMode === "custom" ? (draft.workspace_root ?? "").trim()
    : draft.agent_id.trim() ? resolvedDefaultWorkspacePath ?? "" : "";
  const [settledApprovalWorkspace, setSettledApprovalWorkspace] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setSettledApprovalWorkspace(approvalWorkspace), 300);
    return () => clearTimeout(timer);
  }, [approvalWorkspace]);
  const approvalQuery = useQuery({
    queryKey: ["settings", "nodes", selectedNodeId, "approval", approvalWorkspace],
    queryFn: () => getNodeApprovalRules(selectedNodeId, approvalWorkspace),
    enabled: isNodeOnline && !!approvalWorkspace && approvalWorkspace === settledApprovalWorkspace,
    retry: false,
  });
  const inheritedApprovalRules = workspaceMode === "default" && !draft.agent_id.trim()
    ? capabilities?.inherited_approval_rules : approvalQuery.data?.inherited_approval_rules;
  const defaultWorkspacePath =
    resolvedDefaultWorkspacePath ?? t("agents.form.workspaceCreate.defaultPathUnavailable");
  const queryErrorDetail =
    createStateQuery.error instanceof Error
      ? createStateQuery.error.message.split(" failed: ").at(-1) ?? createStateQuery.error.message
      : "Unable to load this node.";

  useEffect(() => {
    if (!capabilities) return;

    if (!toolsEditedRef.current) {
      const toolDefaults = defaultNames(capabilities.tools);
      setDraft((current) => {
        if (sameStringList(current.tool_allowlist, toolDefaults)) return current;
        if (
          current.tool_allowlist.length > 0 &&
          !sameStringList(current.tool_allowlist, autoDefaultToolsRef.current)
        ) {
          return current;
        }
        autoDefaultToolsRef.current = toolDefaults;
        let next = { ...current, features: Object.fromEntries((capabilities.features ?? []).map(f => [f.key, f.default_on])), tool_allowlist: toolDefaults };
        for (const feature of capabilities.features ?? []) {
          if (feature.default_on) next = changeCapability(next, { kind: "feature", name: feature.key, enabled: true }, capabilityCatalog(capabilities, next.work_mode)).draft;
        }
        return next;
      });
    }
  }, [capabilities]);

  const mutation = useMutation({
    mutationFn: (next: CreateAgentFormState) => createNodeAgent(selectedNodeId, next),
    onSuccess: async (created) => {
      setApplyPending(false);
      setErrorMessage(null);
      setWorkspaceError(null);
      queryClient.setQueryData(["settings", "agents", created.agent_id], created);
      queryClient.setQueryData(["settings", "agents"], (current: AgentSummary[] | undefined) => {
        if (!current) return [created];
        const next = current.filter((agent) => agent.agent_id !== created.agent_id);
        return [created, ...next];
      });
      await queryClient.invalidateQueries({ queryKey: ["settings", "agents"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "nodes"] });
      allowExitRef.current = true;
      navigate(`/settings/agents/${created.agent_id}`);
    },
    onError: (error) => {
      if (isConfigApplyPendingError(error)) {
        setApplyPending(true);
        setErrorMessage(null);
        return;
      }
      setApplyPending(false);
      if (capabilityEditor.reject(error)) { setErrorMessage(null); return; }
      const detail = getAgentConfigRequestDetail(error);
      const status = getAgentConfigRequestStatus(error);
      const code =
        error instanceof Error && "code" in error && typeof error.code === "string"
          ? error.code
          : null;
      const agentId =
        error instanceof Error && "agentId" in error && typeof error.agentId === "string"
          ? error.agentId
          : null;
      if (code === "workspace_confirmation_required") {
        setWorkspaceError(null);
        setErrorMessage(null);
        setExistingConfirmationRequired(true);
        setExistingConfirmed(false);
        return;
      }
      const workspaceMessages: Record<string, string> = {
        workspace_parent_missing: t("agents.form.workspaceCreate.parentMissing", { node: nodeLabel }),
        workspace_parent_unusable: t("agents.form.workspaceCreate.parentUnusable", { node: nodeLabel }),
        workspace_target_not_directory: t("agents.form.workspaceCreate.targetNotDirectory"),
        workspace_initialization_failed: t("agents.form.workspaceCreate.initializationFailed"),
        workspace_already_assigned: t("agents.form.workspaceCreate.alreadyAssigned", {
          agent: agentId ?? t("agents.form.workspaceCreate.unknownAgent")
        })
      };
      if (code && workspaceMessages[code]) {
        setWorkspaceError(workspaceMessages[code]);
        setExistingConfirmationRequired(false);
        return;
      }
      setErrorMessage(
        status === 409
          ? t("agents.form.access.reasoning.saveConflict", { detail: `${status}: ${detail}` })
          : detail,
      );
    }
  });

  useEffect(() => {
    if (!applyPending || mutation.isPending) return;
    const retryTimer = window.setTimeout(() => mutation.mutate(normalizedDraft), 1_000);
    return () => window.clearTimeout(retryTimer);
  }, [applyPending, mutation.isPending, mutation.mutate, normalizedDraft]);

  function markTouched(field: "agent_id" | "display_name") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "agent_id" | "display_name") {
    return (hasSubmitted || touched[field]) && validationErrors[field];
  }

  function confirmExit() {
    if (blocker.state === "blocked") {
      allowExitRef.current = true;
      blocker.proceed();
    }
  }

  function resetWorkspaceFeedback() {
    setWorkspaceError(null);
    setErrorMessage(null);
    setExistingConfirmationRequired(false);
    setExistingConfirmed(false);
  }

  if ((nodesQuery.isLoading || createStateQuery.isLoading) && !capabilities) {
    return <div className="im-agent-panel im-agent-settings im-create-state"><p className="im-agent-field-help">{t("common.loading")}</p></div>;
  }

  if ((nodesQuery.isError || createStateQuery.isError) && !capabilities) {
    return (
      <section className="im-agent-panel im-agent-settings im-create-state">
        <div className="space-y-1">
          <p className="text-sm font-semibold">{t("agents.loadError")}</p>
          <p className="text-sm text-slate-500">
            {nodesQuery.error instanceof Error ? nodesQuery.error.message : queryErrorDetail}
          </p>
        </div>
        <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => {
          void nodesQuery.refetch();
          if (selectedNodeId) void createStateQuery.refetch();
        }}>
          {t("agents.retry")}
        </button>
      </section>
    );
  }

  if (nodesQuery.isSuccess && nodes.length === 0 && !selectedNodeId) {
    return (
      <div className="flex h-full min-w-0 flex-1 overflow-hidden">
        {!isMobile && <AgentsRailDesktop isCreatePage />}
        <div className="im-agent-panel im-agent-settings im-create-state">
          <section className="grid w-full max-w-lg gap-4">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--im-accent)"
              strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8m-4-4v4" />
            </svg>
            <h1 className="im-agent-card-title">{t("agents.create.noDevicesTitle")}</h1>
            <p className="im-agent-card-sub">{t("agents.create.noDevicesBody")}</p>
            <div className="flex flex-wrap gap-2">
              <Link className="im-btn im-btn-primary" to="/settings/nodes">{t("agents.create.manageDevices")}</Link>
              <Link className="im-btn im-btn-muted" to="/settings/agents">{t("agents.create.backToAgents")}</Link>
            </div>
          </section>
        </div>
      </div>
    );
  }

  if (!capabilities) {
    return <div className="im-agent-panel im-agent-settings im-create-state"><p className="im-agent-field-help">{t("common.loading")}</p></div>;
  }


  let footerStatusClass = "im-agent-footer-status";
  let footerStatusText = "";
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


  const createPanel = (
    <form
      data-testid="agent-create"
      className="im-agent-panel im-agent-settings im-agent-create"
      onSubmit={(event) => {
        event.preventDefault();
        setHasSubmitted(true);
        setErrorMessage(null);
        if (hasValidationErrors || hasStaleReasoning || applyPending || !isNodeOnline || !selectedNodeId) return;
        if (workspaceMode === "custom") {
          const workspaceRoot = normalizedDraft.workspace_root;
          if (!workspaceRoot) {
            setWorkspaceError(t("agents.form.workspaceCreate.pathRequired"));
            return;
          }
          if (existingConfirmationRequired && !existingConfirmed) {
            setWorkspaceError(t("agents.form.workspaceCreate.confirmRequired"));
            return;
          }
        }
        setWorkspaceError(null);
        mutation.mutate(normalizedDraft);
      }}
    >
      <header className="im-agent-panel-header">
        <div className="im-agent-panel-header-row">
          {isMobile && <Link className="im-settings-back" aria-label={t("agents.create.backToAgents")} to="/settings/agents">‹</Link>}
          <h2 className="im-agent-panel-title">{t("agents.create.title")}</h2>
        </div>
      </header>
      <div className="im-agent-panel-body im-agent-detail-body im-settings-config">
        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.identity.title")}</h3>
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
                  setIsDirty(true);
                  setDraft({ ...draft, agent_id: event.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") });
                }}
              />
              <p id="agent-id-help" className="im-agent-field-help">
                {t("agents.redesign.createIdHelp")}
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
                placeholder={t("agents.form.identity.displayNamePlaceholder")}
                onBlur={() => markTouched("display_name")}
                onChange={(event) => {
                  setErrorMessage(null);
                  setIsDirty(true);
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
              placeholder={t("agents.form.identity.descriptionPlaceholder")}
              onChange={(event) => {
                setErrorMessage(null);
                setIsDirty(true);
                setDraft({ ...draft, description: event.target.value });
              }}
            />
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="owning-node">{t("agents.form.identity.owningNodeRequired")}</Label.Root>
            <select
              id="owning-node"
              className="im-input"
              value={selectedNodeId}
              onChange={(event) => {
                setSelectedNodeId(event.target.value);
                resetWorkspaceFeedback();
                setIsDirty(true);
              }}
            >
              <option value="">{t("settings.account.defaults.selectNode")}</option>
              {nodes.filter((item) => item.status !== "offline").map((item) => (
                <option key={item.node_id} value={item.node_id}>
                  {item.alias || item.node_name} ({item.status})
                </option>
              ))}
            </select>
          </div>
        </section>

        <section className="im-agent-card">
          <h3 className="im-agent-card-title">{t("agents.redesign.workMode")}</h3>
          <div className="im-create-modes">
            {(["single_thread", "global"] as const).map(mode => <label key={mode} className="im-create-mode">
              <input type="radio" name="work_mode" value={mode} checked={(draft.work_mode ?? "single_thread") === mode} onChange={() => { setDraft({ ...draft, work_mode: mode }); setIsDirty(true); }} />
              <span><strong>{t(`agents.redesign.mode.${mode}`)}</strong><small>{t(`agents.redesign.modeHelp.${mode}`)}</small></span>
            </label>)}
          </div>
          <p className="im-agent-field-help">{t("agents.redesign.modeFixed")}</p>
        </section>

        <section className="im-agent-card">
          <h3 className="im-agent-card-title">{t("agents.redesign.model")}</h3>
          <div className="im-settings-model-fields">
            <ModelFallbackField
              label={t("agents.form.access.model")}
              labelHtmlFor="default-model"
              models={availableModels}
              primary={effectiveReasoningModel(draft.default_model, platformDefaultModel)}
              value={draft.model_fallbacks ?? []}
              onChange={(modelFallbacks) => {
                setErrorMessage(null);
                setIsDirty(true);
                setDraft({ ...draft, model_fallbacks: modelFallbacks });
              }}
            >
              <select
                id="default-model"
                className="im-input"
                value={draft.default_model ?? ""}
                onChange={(event) => {
                  setErrorMessage(null);
                  setIsDirty(true);
                  const defaultModel = event.target.value || null;
                  const effectiveModel = effectiveReasoningModel(defaultModel, platformDefaultModel);
                  setDraft({
                    ...draft,
                    default_model: defaultModel,
                    model_fallbacks: fallbacksAfterPrimaryChange(draft.model_fallbacks ?? [], effectiveModel),
                    reasoning_effort: reasoningEffortAfterModelChange(
                      modelOptions,
                      effectiveModel,
                      draft.reasoning_effort,
                    ),
                  });
                }}
              >
                <option value="">
                  {capabilities.platform_default_model
                    ? t("agents.form.access.modelPlatformDefault", { model: capabilities.platform_default_model })
                    : t("agents.form.access.modelPlatformDefaultPlain")}
                </option>
                {availableModels.map((model) => {
                  const providerName = model.provider_display_name || model.provider;
                  const providerSuffix = providerName ? ` · ${providerName}` : "";
                  const baseLabel = `${model.display_name || model.name}${providerSuffix}`;
                  return (
                    <option key={model.name} value={model.name}>
                      {model.name === capabilities.platform_default_model
                        ? `${baseLabel} ${t("agents.form.access.modelDefaultSuffix")}`
                        : baseLabel}
                    </option>
                  );
                })}
              </select>
            </ModelFallbackField>
            <ModelReasoningField
              idPrefix="create-agent"
              modelOptions={modelOptions}
              selectedModel={effectiveReasoningModel(draft.default_model, platformDefaultModel)}
              value={draft.reasoning_effort}
              applyPending={applyPending}
              onChange={(reasoningEffort) => {
                setErrorMessage(null);
                setIsDirty(true);
                setDraft({ ...draft, reasoning_effort: reasoningEffort });
              }}
            />
          </div>
        </section>

        <section
          className="im-agent-card"
          data-testid="workspace-create-card"
          aria-labelledby="workspace-create-title"
        >
          <div>
            <h3 id="workspace-create-title" className="im-agent-card-title">
              {t("agents.form.workspaceCreate.title")}
            </h3>
            <p className="im-agent-card-sub">
              {t("agents.form.workspaceCreate.sub")}
            </p>
          </div>
          {workspaceMode === "default" ? (
            <button
              className="im-workspace-path-summary"
              type="button"
              onClick={() => {
                setDraft((current) => ({
                  ...current,
                  workspace_root: resolvedDefaultWorkspacePath ?? "",
                }));
                setWorkspaceMode("custom");
                resetWorkspaceFeedback();
                setIsDirty(true);
              }}
            >
              <span className="im-workspace-path-copy">
                <span>{t("agents.form.workspaceCreate.defaultPathLabel")}</span>
                <code>{defaultWorkspacePath}</code>
              </span>
              <span className="im-workspace-path-action">
                {t("agents.form.workspaceCreate.changePath")}
              </span>
            </button>
          ) : (
            <div className="im-agent-field">
              <div className="im-workspace-custom-header">
                <Label.Root htmlFor="workspace-create-root">
                  {t("agents.form.workspaceCreate.customPathLabel")}
                </Label.Root>
                <button
                  type="button"
                  onClick={() => {
                    setWorkspaceMode("default");
                    resetWorkspaceFeedback();
                    setIsDirty(true);
                  }}
                >
                  {t("agents.form.workspaceCreate.useDefault")}
                </button>
              </div>
              <input
                id="workspace-create-root"
                className="im-input im-agent-input-mono"
                autoFocus
                value={draft.workspace_root ?? ""}
                placeholder={t("agents.form.workspaceCreate.pathPlaceholder")}
                aria-describedby="workspace-create-help workspace-create-error"
                aria-invalid={Boolean(workspaceError)}
                onChange={(event) => {
                  setDraft({ ...draft, workspace_root: event.target.value });
                  resetWorkspaceFeedback();
                  setIsDirty(true);
                }}
              />
              <p id="workspace-create-help" className="im-agent-field-help">
                {t("agents.form.workspaceCreate.pathHelp")}
              </p>
              {workspaceError ? (
                <p id="workspace-create-error" className="im-agent-field-error">
                  {workspaceError}
                </p>
              ) : null}
            </div>
          )}

          {existingConfirmationRequired ? (
            <div className="im-workspace-existing-notice" role="alert">
              <div>
                <p className="im-workspace-existing-title">
                  {t("agents.form.workspaceCreate.existingTitle")}
                </p>
                <p>{t("agents.form.workspaceCreate.existingBody")}</p>
              </div>
              <label>
                <input
                  type="checkbox"
                  checked={existingConfirmed}
                  onChange={(event) => {
                    setExistingConfirmed(event.target.checked);
                    setWorkspaceError(null);
                  }}
                />
                <span>{t("agents.form.workspaceCreate.existingConfirm")}</span>
              </label>
            </div>
          ) : null}
        </section>

        {/* feat-379-M5 (ISSUE-1): Behavior card — Custom Instructions + Features + Preview */}
        {capabilityEditor.toast}
        <CreateBehaviorCard
          draft={draft}
          inheritedRules={inheritedApprovalRules}
          capabilityFeatures={capabilities.features ?? []}
          selectedNodeId={selectedNodeId}
          workspaceMode={workspaceMode}
          workspaceRoot={normalizedDraft.workspace_root}
          onApprovalModeChange={(value) => {
            setIsDirty(true);
            setErrorMessage(null);
            setDraft({ ...draft, approval_mode: value });
          }}
          onCustomPromptChange={(value) => {
            setErrorMessage(null);
            setIsDirty(true);
            setDraft({ ...draft, custom_prompt: value });
          }}
          onFeatureToggle={(key, value) => {
            setErrorMessage(null);
            setIsDirty(true);
            void capabilityEditor.apply([{ kind: "feature", name: key, enabled: value }]);
          }}
          onPolicyChange={(value) => {
            setErrorMessage(null);
            setIsDirty(true);
            setDraft({ ...draft, group_reply_policy: value });
          }}
        />

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.access.title")}</h3>
          </div>
          <div className="grid gap-4">
            <SkillSourceSelector
              testId="pill-selector-skills"
              label={t("agents.form.access.skills")}
              selected={draft.skills}
              selectionMode={draft.skills_selection_mode ?? "explicit_denylist"}
              options={capabilities.skills}
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              onChange={(skills) => {
                setIsDirty(true);
                capabilityEditor.skills(skills);
              }}
            />
            <PillSelector
              testId="pill-selector-tools"
              label={t("agents.form.access.tools")}
              selected={[...new Set([...draft.tool_allowlist, ...capabilityCatalog(capabilities, draft.work_mode).fixed_tools])]}
              fixed={capabilityCatalog(capabilities, draft.work_mode).fixed_tools}
              options={[...capabilities.tools, ...capabilityCatalog(capabilities, draft.work_mode).fixed_tools.filter(name => !capabilities.tools.some(t => t.name === name)).map(name => ({ name }))]}
              isLoading={createStateQuery.isLoading}
              errorMessage={createStateQuery.isError ? queryErrorDetail : null}
              onRetry={() => void createStateQuery.refetch()}
              onChange={(toolAllowlist) => {
                toolsEditedRef.current = true;
                setIsDirty(true);
                capabilityEditor.tools(toolAllowlist);
              }}
            />
          </div>

        </section>

      </div>
      <footer className="im-agent-detail-footer im-create-footer">
        {footerStatusText && <p className={footerStatusClass} role={footerStatusClass.includes("error") ? "alert" : "status"}>{footerStatusText}</p>}
        <div className="im-create-actions">
          <Link className="im-settings-action" to="/settings/agents">{t("agents.create.cancel")}</Link>
          <button className="im-settings-action im-settings-action-primary" type="submit" disabled={mutation.isPending || applyPending || hasStaleReasoning || !isNodeOnline}>
            {mutation.isPending ? t("agents.redesign.creating") : t("agents.create.submit")}
          </button>
        </div>
      </footer>
      {blocker.state === "blocked" && (
        <div className={isMobile ? "chat-modal-bottom-sheet" : "chat-modal-backdrop"} role="presentation">
          <section className="chat-modal" role="dialog" aria-modal="true" aria-labelledby="agent-create-unsaved-title">
            <header className="chat-modal-header bg-white">
              {isMobile ? <div className="chat-modal-sheet-handle" aria-hidden="true"><div className="chat-modal-sheet-handle-bar" /></div> : null}
              <h2 id="agent-create-unsaved-title">{t("agents.create.unsavedExitTitle")}</h2>
            </header>
            <div className="chat-modal-body"><p className="m-0 text-sm text-slate-600">{t("agents.create.unsavedExitBody")}</p></div>
            <footer className="chat-modal-footer bg-white">
              <button className="chat-modal-btn-ghost" type="button" onClick={() => blocker.reset()}>
                {t("agents.create.keepEditing")}
              </button>
              <button className="chat-modal-btn-primary" type="button" onClick={confirmExit}>
                {t("agents.create.leaveWithoutSaving")}
              </button>
            </footer>
          </section>
        </div>
      )}
    </form>
  );

  return (
    <div className="flex h-full overflow-hidden">
      {!isMobile && <AgentsRailDesktop isCreatePage />}
      <div className="flex min-w-0 flex-1 overflow-hidden">{createPanel}</div>
    </div>
  );
}
