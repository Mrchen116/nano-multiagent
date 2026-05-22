import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { createDirectChatByAgentUserId, listAgents } from "../../chat/chat-api";
import { Avatar } from "../../chat/v2/components/avatar";
import { PillSelector } from "./pill-selector";
import { useAgentStatusBroadcastConsumer } from "./agent-status-ws-consumer";
import {
  AgentConfig,
  AgentFeature,
  AgentSummary,
  getAgentDetailState,
  listAgentSummaries,
  promptPreview,
  updateAgentConfig
} from "./im-agent-config-api";

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
    // feat-379-M3: system_prompt preserved for API compat but no longer user-editable
    system_prompt: config.system_prompt.trim(),
    custom_prompt: (config.custom_prompt ?? "").trim(),
    skills: normalizeAllowlist(config.skills),
    tool_allowlist: normalizeAllowlist(config.tool_allowlist),
    default_model: normalizeText(config.default_model ?? "") || null
  };
}

function validateDraft(draft: AgentConfigFormState) {
  // feat-379-M3: system_prompt required validation removed — segment system replaces it
  const errors: Partial<Record<"display_name", string>> = {};
  if (!draft.display_name) errors.display_name = "Display name is required.";
  return errors;
}

// feat-379-M3: resolve effective feature values from draft + capabilities defaults.
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

function initialsOf(displayName: string): string {
  const trimmed = displayName.trim();
  if (!trimmed) return "AG";
  return trimmed.slice(0, 2).toUpperCase();
}

function colorForAgent(agent: AgentSummary): string {
  return colorForSeed(agent.agent_id || agent.display_name);
}

function colorForSeed(seedValue: string): string {
  let hash = 0;
  for (let i = 0; i < seedValue.length; i += 1) hash = (hash << 5) - hash + seedValue.charCodeAt(i);
  return `oklch(0.52 0.14 ${Math.abs(hash) % 360})`;
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

// feat-379-M3: Behavior card — features checkbox group + custom_prompt textarea + collapsible preview.
// Uses the same checkbox idiom as allowlist-selector.tsx (appearance:none + :checked → --im-accent)
// and the same collapsible pattern as tool-calls-panel.tsx (aria-expanded + ▸/▾ + class toggle).
interface BehaviorCardProps {
  agentId: string;
  draft: AgentConfigFormState;
  capabilityFeatures: AgentFeature[];
  onCustomPromptChange: (value: string) => void;
  onFeatureToggle: (key: string, value: boolean) => void;
  onPolicyChange: (value: string) => void;
}

function BehaviorCard({
  agentId,
  draft,
  capabilityFeatures,
  onCustomPromptChange,
  onFeatureToggle,
  onPolicyChange
}: BehaviorCardProps) {
  const { t } = useTranslation();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  // Debounce handle for preview re-fetch on change
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const effectiveFeatures = useMemo(
    () => resolveEffectiveFeatures(draft.features, capabilityFeatures),
    [draft.features, capabilityFeatures]
  );

  // Fetch preview when opened or when draft changes while open.
  // feat-379-M6 (ISSUE-3): pass tool_allowlist as tool_ids so the assembler's
  // has_tool() gate is active — without it, feature gates that require a tool
  // (e.g. memory_curation requires "memory") never fire.
  const fetchPreview = useCallback(async () => {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const text = await promptPreview(agentId, {
        features: effectiveFeatures,
        custom_prompt: draft.custom_prompt ?? "",
        tool_ids: draft.tool_allowlist ?? []
      });
      setPreviewText(text);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  }, [agentId, effectiveFeatures, draft.custom_prompt, draft.tool_allowlist]);

  // Debounce preview re-fetch when draft changes while preview is open
  useEffect(() => {
    if (!previewOpen) return;
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => { void fetchPreview(); }, 600);
    return () => { if (previewTimer.current) clearTimeout(previewTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewOpen, draft.custom_prompt, draft.features, draft.tool_allowlist]);

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

      {/* Custom Instructions — optional textarea replacing legacy system_prompt */}
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
              const checked = effectiveFeatures[feat.key] ?? feat.default_on;
              const disabled = !feat.available;
              const tooltipText = disabled && feat.requires_tool
                ? t("agents.form.behavior.featureDisabledTooltip", { tool: feat.requires_tool })
                : undefined;
              return (
                <label
                  key={feat.key}
                  title={tooltipText}
                  className={`flex items-start gap-3 rounded-xl border px-3 py-[10px] transition-colors ${
                    disabled
                      ? "border-[var(--im-border)] bg-white/60 opacity-55 cursor-not-allowed"
                      : checked
                        ? "border-teal-300 bg-teal-50/60 cursor-pointer"
                        : "border-[var(--im-border)] bg-white/90 cursor-pointer hover:border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    data-feature-key={feat.key}
                    checked={checked}
                    disabled={disabled}
                    className="im-feature-checkbox mt-[2px] shrink-0"
                    onChange={(e) => { if (!disabled) onFeatureToggle(feat.key, e.target.checked); }}
                  />
                  <div className="min-w-0">
                    {/* label_i18n / help_i18n are i18n keys provided by the backend registry */}
                    <p className="m-0 text-[13px] font-semibold text-slate-900 leading-5">{t(feat.label_i18n)}</p>
                    <p className="m-0 text-[11px] text-slate-500 leading-[1.4]">{t(feat.help_i18n)}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* Group reply policy — scene-mandatory, not a toggle */}
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
              <>
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
                <p
                  style={{
                    fontSize: "0.70rem",
                    color: "var(--im-muted, oklch(0.55 0.01 240))",
                    marginTop: 4,
                    marginBottom: 0
                  }}
                >
                  {t("agents.form.behavior.previewHelp")}
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// M20/R12-bis-1: desktop split layout — left 240px dark agent rail.
// Prototype `im-settings-page.jsx::AgentListView` desktop: 240px dark sidebar
// (`oklch(0.24 0.012 240)` bg) with clickable agent rows, active highlight.
function AgentsRailDesktop({ activeId }: { activeId: string }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["settings", "agents"], queryFn: listAgentSummaries, staleTime: 30_000 });
  const agents = query.data ?? [];

  return (
    <aside
      data-testid="agents-rail-desktop"
      className="hidden md:flex md:w-[240px] md:flex-col md:border-r md:border-[oklch(0.29_0.010_240)]"
      style={{ background: "oklch(0.24 0.012 240)" }}
      aria-label={t("agents.title")}
    >
      <div className="flex items-center justify-between px-3 py-[10px] border-b border-[oklch(0.29_0.010_240)]">
        <span className="text-[11px] font-bold tracking-[0.08em] uppercase text-[oklch(0.55_0.01_240)]">
          {t("agents.title")}
        </span>
        <Link
          to="/settings/agents/new"
          className="inline-flex h-9 items-center rounded-lg px-3 text-[13px] font-semibold text-white"
          style={{ background: "oklch(0.30 0.012 240)" }}
        >
          {t("agents.newButton")}
        </Link>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-[6px]" aria-label={t("agents.title")}>
        {agents.map((agent) => {
          const active = agent.agent_id === activeId;
          const online = agent.node_status === "online";
          return (
            <button
              key={agent.agent_id}
              type="button"
              onClick={() => navigate(`/settings/agents/${agent.agent_id}`)}
              className={`flex w-full items-center gap-3 rounded-xl border-none text-left font-inherit mb-1 min-h-[52px] px-[10px] py-[9px] transition-colors ${
                active
                  ? "outline outline-1 outline-[oklch(0.40_0.08_180)]"
                  : "outline-none"
              }`}
              style={{
                background: active ? "oklch(0.31 0.015 240)" : "transparent",
                cursor: "pointer"
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = "oklch(0.28 0.012 240)";
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.background = "transparent";
              }}
              aria-current={active ? "page" : undefined}
            >
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] font-bold text-white"
                style={{ background: colorForAgent(agent) }}
                aria-hidden="true"
              >
                {initialsOf(agent.display_name)}
              </span>
              <div className="min-w-0 flex-1">
                <p className={`m-0 text-[13px] font-semibold truncate ${active ? "text-white" : "text-[oklch(0.18_0.01_240)]"}`}>
                  {agent.display_name}
                </p>
                <p className="m-0 mt-[2px] font-mono text-[11px] text-[oklch(0.50_0.01_240)] truncate">
                  {agent.agent_id}
                </p>
              </div>
              <span
                className="inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ background: online ? "oklch(0.55 0.18 145)" : "oklch(0.45 0.01 240)" }}
                aria-label={online ? "online" : "offline"}
              />
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

export function AgentDetailPage() {
  const { agentId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const isMobile = useIsMobile();
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

  // feat-340-M18 R9-2: fetch the agent summary list to obtain ``user_id``.
  // ``getAgentDetailState`` only returns the AgentConfig shape (no user_id), so we
  // pair it with the list endpoint. Using a separate query keeps cache invalidation
  // simple and lets the Open chat button re-attempt after a transient miss.
  const agentsSummaryQuery = useQuery({
    queryKey: ["settings", "agents", "summary"],
    queryFn: () => listAgents(),
    staleTime: 30_000
  });
  const currentAgentSummary = useMemo(
    () => agentsSummaryQuery.data?.find((item) => item.agent_id === agentId) ?? null,
    [agentsSummaryQuery.data, agentId]
  );

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
        const nextConfig = {
          ...updated,
          node_id: updated.node_id ?? owningNode?.node_id ?? capabilities.node_id,
          node_name: owningNode?.node_name ?? updated.node_name ?? null,
          node_status: owningNode?.status ?? updated.node_status ?? capabilities.node_status ?? null
        };
        setDraft(nextConfig);
        queryClient.setQueryData(["settings", "agents", agentId, "detail-state"], {
          config: nextConfig,
          capabilities,
          owningNode
        });
      }
      void queryClient.invalidateQueries({ queryKey: ["settings", "agents"], exact: true });
      void queryClient.invalidateQueries({ queryKey: ["settings", "agents", "summary"], exact: true });
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
    mutationFn: async () => {
      // feat-340-M18 R9-2: drive the create directly off agent.user_id (returned
      // by /im/v1/agents since R9-1). Bypassing the legacy bootstrap path
      // sidesteps the /im/v1/users 404 that previously made this button
      // appear broken in fresh sessions.
      if (!currentAgentSummary || !currentAgentSummary.user_id) {
        throw new Error(
          "This agent has no associated IM user yet. Try refreshing the page in a moment."
        );
      }
      return createDirectChatByAgentUserId({
        agentId,
        agentUserId: currentAgentSummary.user_id,
        agentDisplayName: currentAgentSummary.display_name || draft?.display_name || agentId
      });
    },
    onSuccess: async ({ conversation_id }) => {
      setErrorMessage(null);
      // Invalidate both legacy and v2 conversation caches so whichever chat
      // surface the user lands on shows the new direct conv without a reload.
      // (M17/R7-4: without v2 invalidation the workspace renders the empty
      // "select a conversation" pane, which users read as a 404.)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }),
        queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] }),
      ]);
      navigate(`/chat/${conversation_id}`);
    },
    onError: (error) => {
      // R9-2: surface the failure prominently instead of swallowing it. Older
      // builds left the user staring at an unresponsive button after a 404 on
      // /im/v1/users; that "broken-feeling" silence is now an explicit banner.
      setErrorMessage(
        error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Open direct chat failed"
      );
    }
  });

  function markTouched(field: "display_name") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "display_name") {
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
  const headerSaveText = mutation.isPending
    ? t("agents.detail.saving")
    : saved
      ? t("agents.detail.saved")
      : isDirty
        ? t("agents.detail.save")
        : t("agents.detail.noChanges");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setHasAttemptedSave(true);
    setErrorMessage(null);
    if (hasValidationErrors || !isDirty || !normalizedDraft) return;
    mutation.mutate(normalizedDraft);
  }

  const detailPanel = (
    <form
      data-testid="agent-detail"
      className="im-agent-panel"
      onSubmit={handleSubmit}
    >
      <header className="im-agent-panel-header">
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
          <Avatar
            initials={initialsOf(draft.display_name)}
            color={colorForSeed(draft.agent_id || draft.display_name)}
            size={isMobile ? 38 : 42}
            status={displayedNodeStatus === "online" ? "online" : "offline"}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="im-agent-panel-title">{draft.display_name || draft.agent_id}</h2>
            <p className="im-agent-panel-subtitle im-agent-panel-node-line">
              <span className="im-agent-panel-agent-id">{draft.agent_id}</span>
              <span
                className={`im-agent-panel-node ${displayedNodeStatus === "online" ? "online" : ""}`}
              >
                <span className="dot" /> {displayedNodeName}
              </span>
            </p>
          </div>
          {!isMobile && (
            <div className="im-agent-header-actions">
              <button
                type="button"
                className="im-btn im-btn-muted"
                disabled={openDirectChatMutation.isPending}
                onClick={() => openDirectChatMutation.mutate()}
              >
                {openDirectChatMutation.isPending ? t("agents.detail.openChatPending") : t("agents.detail.openChat")}
              </button>
              <button className="im-btn im-btn-primary" type="submit" disabled={mutation.isPending || !isDirty}>
                {headerSaveText}
              </button>
            </div>
          )}
        </div>
        {openDirectChatMutation.isError && errorMessage ? (
          <p
            data-testid="open-chat-error"
            role="alert"
            className="im-agent-footer-status error"
            aria-live="polite"
          >
            {errorMessage}
          </p>
        ) : null}
      </header>

      <div className="im-agent-panel-body">
        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.identity.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.identity.subEdit")}</p>
          </div>
          {/* M19/R11-4: Identity row1 = Agent ID + Display Name (Owner UUID 对用户无意义, 移除). */}
          <div className="im-agent-card-grid-2" data-testid="agent-identity-row1">
            <div className="im-agent-field">
              <Label.Root htmlFor="agent-id">{t("agents.form.identity.agentId")}</Label.Root>
              <input id="agent-id" className="im-input im-agent-input-mono" value={draft.agent_id} disabled />
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
                {t("agents.form.identity.displayNameHelper")}
              </p>
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

        {/* feat-379-M3: Behavior card replaced with BehaviorCard component */}
        <BehaviorCard
          agentId={agentId}
          draft={draft}
          capabilityFeatures={capabilities.features ?? []}
          onCustomPromptChange={(value) => {
            setSaved(false);
            setErrorMessage(null);
            setDraft({ ...draft, custom_prompt: value });
          }}
          onFeatureToggle={(key, value) => {
            setSaved(false);
            setErrorMessage(null);
            setDraft({ ...draft, features: { ...(draft.features ?? {}), [key]: value } });
          }}
          onPolicyChange={(value) => {
            setSaved(false);
            setErrorMessage(null);
            setDraft({ ...draft, group_reply_policy: value as AgentConfig["group_reply_policy"] });
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
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
              onChange={(skills) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, skills });
              }}
            />
            <PillSelector
              testId="pill-selector-tools"
              label={t("agents.form.access.tools")}
              selected={draft.tool_allowlist}
              options={capabilities.tools}
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
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

      <footer
        className="im-agent-footer im-agent-detail-footer"
        aria-live="polite"
        style={{
          paddingBottom: isMobile ? "calc(14px + env(safe-area-inset-bottom, 0px))" : "14px"
        }}
      >
        <p className={footerStatusClass}>{footerStatusText}</p>
        <div className="im-agent-footer-actions">
          {isMobile && (
            <button
              type="button"
              className="im-btn im-btn-muted"
              disabled={openDirectChatMutation.isPending}
              onClick={() => openDirectChatMutation.mutate()}
            >
              {openDirectChatMutation.isPending ? t("agents.detail.openChatPending") : t("agents.detail.openChat")}
            </button>
          )}
          {isDirty && (
            <button
              className="im-btn im-btn-muted"
              type="button"
              disabled={mutation.isPending}
              onClick={handleDiscard}
            >
              {t("agents.detail.discard")}
            </button>
          )}
          <button className="im-btn im-btn-primary" type="submit" disabled={mutation.isPending || !isDirty}>
            {mutation.isPending ? t("agents.detail.saving") : t("agents.detail.saveAgent")}
          </button>
        </div>
      </footer>
    </form>
  );

  if (isMobile) {
    return detailPanel;
  }

  return (
    <div className="flex h-full overflow-hidden">
      <AgentsRailDesktop activeId={agentId} />
      <div className="flex-1 overflow-y-auto bg-[oklch(0.93_0.007_240)]">
        {detailPanel}
      </div>
    </div>
  );
}
