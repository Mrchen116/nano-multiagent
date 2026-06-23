import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { createDirectChatByAgentUserId, listAgents } from "../../chat/chat-api";
import { Avatar, colorForAgent } from "../../chat/v2/components/avatar";
import { PillSelector } from "./pill-selector";
import { useAgentStatusBroadcastConsumer } from "./agent-status-ws-consumer";
import {
  AgentConfig,
  AgentFeature,
  AgentSummary,
  CronJobSummary,
  ModelOption,
  getAgentDetailState,
  getAgentHeartbeatMd,
  listAgentSummaries,
  listAgentCronJobs,
  deleteAgentCronJob,
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

function resolveModelOptions(modelOptions: ModelOption[] | undefined, currentModel: string | null): ModelOption[] {
  const resolved: ModelOption[] = [];
  const seen = new Set<string>();
  for (const option of modelOptions ?? []) {
    const name = option.name.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    resolved.push({ name, provider: option.provider });
  }
  // bugfix-429 R5: keep the agent's current model selectable even if it is no
  // longer advertised by the node (provider unknown → label degrades to name).
  if (currentModel && !seen.has(currentModel)) {
    resolved.unshift({ name: currentModel, provider: "" });
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
  // feat-379-M9 (決策 14): tool_ids comes directly from draft.tool_allowlist; the old
  // effectiveToolIds hack that injected capability-inferred tools is removed because
  // _build_tool_names() now correctly includes all tools (R1 fix).
  const fetchPreview = useCallback(async () => {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const text = await promptPreview(agentId, {
        features: effectiveFeatures,
        custom_prompt: draft.custom_prompt ?? "",
        tool_ids: draft.tool_allowlist ?? [],
        skill_ids: draft.skills ?? []
      });
      setPreviewText(text);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  }, [agentId, effectiveFeatures, draft.custom_prompt, draft.tool_allowlist, draft.skills]);

  // Debounce preview re-fetch when draft changes while preview is open.
  useEffect(() => {
    if (!previewOpen) return;
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => { void fetchPreview(); }, 600);
    return () => { if (previewTimer.current) clearTimeout(previewTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewOpen, draft.custom_prompt, draft.features, draft.tool_allowlist, draft.skills]);

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
              // feat-379-M9 (決策 12): features are always enabled — disabled state removed.
              // tool_allowlist is the linkage authority; features follow tools, not vice versa.
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

// feat-394 decision 5: HeartbeatCard — per-agent heartbeat enable/disable + cadence + activeHours.
// Shows a toggle for heartbeat_enabled, an optional "every" interval input and optional
// active-hours start/end time inputs when enabled.
// feat-394-M7 R5-3 fix: added activeHours start/end UI (spec S2.5 requirement).
// feat-394-M11 decision E: cadence input binds to backend config value (no hardcoded 30m fallback).
// feat-394-M13: adds collapsible HEARTBEAT.md read-only preview panel via RPC (Decision G).
// feat-394 followup: cadence is edited as a number stepper + unit dropdown rather than
// a free-text duration box.  This guarantees the stored value is always in the backend's
// strict `<int><unit>` shape (scheduler parser is `\d+[smhd]`), so an invalid duration that
// only blows up at tick time can never be produced from the UI.
const HEARTBEAT_UNITS = ["m", "h", "d"] as const;
type HeartbeatUnit = "s" | "m" | "h" | "d";

function parseCadence(every: string): { amount: string; unit: HeartbeatUnit } {
  const match = /^\s*(\d+)\s*([smhd])\s*$/i.exec(every);
  if (!match) return { amount: "", unit: "m" };
  return { amount: match[1], unit: match[2].toLowerCase() as HeartbeatUnit };
}

interface HeartbeatCardProps {
  agentId: string;
  draft: AgentConfigFormState;
  onToggle: (enabled: boolean) => void;
  onEveryChange: (every: string) => void;
  onActiveHoursChange: (start: string, end: string) => void;
  // feat-394 M9 R6: when heartbeat enable is managed by the Features checkbox list
  // (heartbeat is in capabilityFeatures), hide the redundant inline enable toggle.
  hideEnableToggle?: boolean;
}

function HeartbeatCard({ agentId, draft, onToggle, onEveryChange, onActiveHoursChange, hideEnableToggle = false }: HeartbeatCardProps) {
  const { t } = useTranslation();
  // feat-394-M11 decision E: no hardcoded fallback — cadence binds directly to backend value.
  // When heartbeat is not configured, every is undefined → input shows empty (placeholder "30m").
  const heartbeat = draft.heartbeat;
  // feat-394 M9-E: enable is the single-true-source in features["heartbeat"], not heartbeat.enabled.
  const enabled = draft.features?.heartbeat ?? false;
  const every = heartbeat?.every ?? "";
  const { amount: cadenceAmount, unit: cadenceUnit } = parseCadence(every);
  // Show m/h/d; keep a legacy "s" value as an extra option so opening the form never
  // silently rewrites a seconds-based cadence into minutes.
  const cadenceUnitOptions: HeartbeatUnit[] = (HEARTBEAT_UNITS as readonly string[]).includes(cadenceUnit)
    ? [...HEARTBEAT_UNITS]
    : [cadenceUnit, ...HEARTBEAT_UNITS];
  const emitCadence = (amount: string, unit: HeartbeatUnit) => {
    const trimmed = amount.trim();
    // Empty amount → unconfigured (backend falls back to default 30m); never emit a unit-only string.
    onEveryChange(trimmed === "" ? "" : `${trimmed}${unit}`);
  };
  const activeStart = heartbeat?.active_hours?.start ?? "";
  const activeEnd = heartbeat?.active_hours?.end ?? "";

  // feat-394-M13: HEARTBEAT.md collapsible read-only preview — fetched via RPC, not direct file access.
  // Decision G: IM process must never directly read gateway-side workspace files.
  const [hbMdOpen, setHbMdOpen] = useState(false);
  const [hbMdContent, setHbMdContent] = useState<string | null>(null);
  const [hbMdLoading, setHbMdLoading] = useState(false);
  const [hbMdNodeOnline, setHbMdNodeOnline] = useState(true);

  async function handleHbMdToggle() {
    if (!hbMdOpen) {
      setHbMdOpen(true);
      setHbMdLoading(true);
      try {
        const resp = await getAgentHeartbeatMd(agentId);
        setHbMdContent(resp.content);
        setHbMdNodeOnline(resp.node_online);
      } catch {
        setHbMdContent(null);
        setHbMdNodeOnline(false);
      } finally {
        setHbMdLoading(false);
      }
    } else {
      setHbMdOpen(false);
    }
  }

  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">{t("agents.form.heartbeat.title")}</h3>
        <p className="im-agent-card-sub">{t("agents.form.heartbeat.sub")}</p>
      </div>
      {/* feat-394 M9 R6: enable toggle shown only when not managed by Features list */}
      {!hideEnableToggle && (
        <div className="im-agent-field">
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              data-testid="heartbeat-enabled-toggle"
              checked={enabled}
              className="im-feature-checkbox"
              onChange={(e) => onToggle(e.target.checked)}
            />
            <div>
              <p className="m-0 text-[13px] font-semibold text-slate-900 leading-5">
                {t("agents.form.heartbeat.enabledLabel")}
              </p>
              <p className="m-0 text-[11px] text-slate-500 leading-[1.4]">
                {t("agents.form.heartbeat.enabledHelp")}
              </p>
            </div>
          </label>
        </div>
      )}
      {/* When hideEnableToggle, the card is only rendered when enabled=true (controlled externally),
          so we always show cadence/activeHours config panels. */}
      {(enabled || hideEnableToggle) && (
        <>
          <div className="im-agent-field">
            <Label.Root htmlFor="heartbeat-every">{t("agents.form.heartbeat.everyLabel")}</Label.Root>
            <div className="flex gap-2 items-center">
              <input
                id="heartbeat-every"
                className="im-input"
                type="number"
                min={1}
                step={1}
                value={cadenceAmount}
                placeholder="30"
                aria-describedby="heartbeat-every-help"
                onChange={(e) => emitCadence(e.target.value, cadenceUnit)}
                // feat-394-M3 minor Issue 4: select-all on focus so typing replaces the old value
                // rather than appending to it (standard UX for numeric input fields).
                onFocus={(e) => e.target.select()}
              />
              <select
                id="heartbeat-every-unit"
                className="im-input"
                data-testid="heartbeat-every-unit"
                value={cadenceUnit}
                aria-label={t("agents.form.heartbeat.everyUnitLabel")}
                onChange={(e) => emitCadence(cadenceAmount, e.target.value as HeartbeatUnit)}
              >
                {cadenceUnitOptions.map((u) => (
                  <option key={u} value={u}>
                    {t(`agents.form.heartbeat.unit.${u}`)}
                  </option>
                ))}
              </select>
            </div>
            <p id="heartbeat-every-help" className="im-agent-field-help">
              {t("agents.form.heartbeat.everyHelp")}
            </p>
          </div>
          {/* feat-394-M7 R5-3 fix: activeHours UI — spec S2.5 "活跃时段外不打扰" */}
          <div className="im-agent-field">
            <Label.Root htmlFor="heartbeat-active-start">
              {t("agents.form.heartbeat.activeHoursLabel", "Active hours (optional)")}
            </Label.Root>
            <div className="flex gap-2 items-center">
              <input
                id="heartbeat-active-start"
                className="im-input"
                data-testid="heartbeat-active-hours-start"
                type="time"
                value={activeStart}
                placeholder="09:00"
                aria-label="Active hours start"
                onChange={(e) => onActiveHoursChange(e.target.value, activeEnd)}
              />
              <span className="text-slate-500 text-sm">–</span>
              <input
                id="heartbeat-active-end"
                className="im-input"
                data-testid="heartbeat-active-hours-end"
                type="time"
                value={activeEnd}
                placeholder="22:00"
                aria-label="Active hours end"
                onChange={(e) => onActiveHoursChange(activeStart, e.target.value)}
              />
            </div>
            <p className="im-agent-field-help">
              {t("agents.form.heartbeat.activeHoursHelp", "Heartbeat only triggers within this time window (leave blank for always-on)")}
            </p>
          </div>

          {/* feat-394-M13: HEARTBEAT.md read-only preview — content fetched from gateway via RPC
              so IM never directly reads gateway-side workspace files (Decision G). */}
          <div>
            <button
              type="button"
              className={`im-behavior-preview-toggle ${hbMdOpen ? "im-behavior-preview-toggle--open" : ""}`}
              onClick={() => { void handleHbMdToggle(); }}
              aria-expanded={hbMdOpen}
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
              <span aria-hidden="true">{hbMdOpen ? "▾" : "▸"}</span>
              <span>{t("agents.form.heartbeat.heartbeatMdToggle", "View HEARTBEAT.md")}</span>
            </button>

            {hbMdOpen && (
              <div className="im-behavior-preview-panel im-behavior-preview-panel--open" style={{ marginTop: 8 }}>
                {hbMdLoading && (
                  <p className="text-[11px] text-slate-500">{t("agents.form.heartbeat.heartbeatMdLoading", "Loading...")}</p>
                )}
                {!hbMdLoading && !hbMdNodeOnline && (
                  <p className="text-[11px] text-slate-400 italic">
                    {t("agents.form.heartbeat.heartbeatMdOffline", "Node is offline — HEARTBEAT.md unavailable")}
                  </p>
                )}
                {!hbMdLoading && hbMdNodeOnline && hbMdContent !== null && hbMdContent === "" && (
                  <p className="text-[11px] text-slate-400 italic">
                    {t("agents.form.heartbeat.heartbeatMdEmpty", "HEARTBEAT.md not found")}
                  </p>
                )}
                {!hbMdLoading && hbMdNodeOnline && hbMdContent !== null && hbMdContent !== "" && (
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
                    {hbMdContent}
                  </pre>
                )}
              </div>
            )}
          </div>

        </>
      )}
    </section>
  );
}

// feat-394-M2 decision 5: CronCard — per-agent cron enable/disable.
// feat-394-M3 WARNING-3: also shows task list + delete (spec Scenario: 配置页查看并手动删除任务).
interface CronCardProps {
  agentId: string;
  draft: AgentConfigFormState;
  onToggle: (enabled: boolean) => void;
  // feat-394 M9 R6: when cron enable is managed by the Features checkbox list, hide inline toggle.
  hideEnableToggle?: boolean;
}

function CronCard({ agentId, draft, onToggle, hideEnableToggle = false }: CronCardProps) {
  const { t } = useTranslation();
  // feat-394 M9-E: enable is the single-true-source in features["cron_scheduling"]; no draft.cron object.
  const enabled = draft.features?.cron_scheduling ?? false;
  const queryClient = useQueryClient();

  // feat-394-M3: fetch cron jobs list for this agent
  // When hideEnableToggle the card only renders when cron is on, so enabled||hideEnableToggle.
  const jobsQuery = useQuery({
    queryKey: ["cron-jobs", agentId],
    queryFn: () => listAgentCronJobs(agentId),
    enabled: enabled || hideEnableToggle,  // when controlled externally, always fetch
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => deleteAgentCronJob(agentId, jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cron-jobs", agentId] });
    },
  });

  const jobs = jobsQuery.data ?? [];

  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">{t("agents.form.cron.title")}</h3>
        <p className="im-agent-card-sub">{t("agents.form.cron.sub")}</p>
      </div>
      {/* feat-394 M9 R6: enable toggle shown only when not managed by Features list */}
      {!hideEnableToggle && (
        <div className="im-agent-field">
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              data-testid="cron-enabled-toggle"
              checked={enabled}
              className="im-feature-checkbox"
              onChange={(e) => onToggle(e.target.checked)}
            />
            <div>
              <p className="m-0 text-[13px] font-semibold text-slate-900 leading-5">
                {t("agents.form.cron.enabledLabel")}
              </p>
              <p className="m-0 text-[11px] text-slate-500 leading-[1.4]">
                {t("agents.form.cron.enabledHelp")}
              </p>
            </div>
          </label>
        </div>
      )}
      {/* feat-394-M3: cron jobs task list (spec Scenario: 配置页查看并手动删除任务) */}
      {(enabled || hideEnableToggle) && (
        <div className="im-agent-field" data-testid="cron-jobs-list">
          {jobsQuery.isError && (
            <p className="text-[12px] text-red-500">{t("agents.form.cron.loadError")}</p>
          )}
          {!jobsQuery.isError && jobs.length === 0 && (
            <p className="text-[12px] text-slate-400 italic">{t("agents.form.cron.noJobs")}</p>
          )}
          {jobs.length > 0 && (
            <ul className="space-y-2" role="list" aria-label={t("agents.form.cron.jobsListLabel")}>
              {jobs.map((job: CronJobSummary) => (
                <li
                  key={job.id}
                  className="flex items-start justify-between gap-2 p-2 bg-slate-50 rounded border border-slate-200"
                  data-testid={`cron-job-${job.id}`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-slate-800 truncate">{job.name}</p>
                    <p className="text-[11px] text-slate-500 truncate">{job.instruction}</p>
                    <p className="text-[10px] text-slate-400 font-mono truncate">
                      {JSON.stringify(job.schedule)}
                    </p>
                  </div>
                  <button
                    type="button"
                    data-testid={`cron-job-delete-${job.id}`}
                    className="shrink-0 text-[12px] text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 transition-colors"
                    onClick={() => deleteMutation.mutate(job.id)}
                    disabled={deleteMutation.isPending}
                    aria-label={`${t("agents.form.cron.deleteJob")} ${job.name}`}
                  >
                    {t("agents.form.cron.deleteJob")}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
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
  // feat-394 M9-C: once the user manually edits tool_allowlist, stop treating empty as
  // "use product defaults" — the empty list becomes a genuine empty whitelist.
  const [allowlistUserTouched, setAllowlistUserTouched] = useState(false);

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
      // Reset touched flag when server data (re)loads — fresh state, back to "empty = defaults".
      setAllowlistUserTouched(false);
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
            color={colorForAgent(draft)}
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
            // feat-379-M9 (決策 12): tick → add requires_tool to allowlist; untick → keep tool.
            const capFeats = capabilities?.features ?? [];
            const requiresTool = capFeats.find((f) => f.key === key)?.requires_tool ?? null;
            // bugfix: mirror the materialize logic in PillSelector onChange — only materialize the
            // default set when we are actually about to add a requires_tool entry. This guards against
            // ticking a feature that has no requires_tool (e.g. heartbeat) incorrectly kicking the
            // agent out of default mode and freezing its tool_allowlist as an explicit set.
            const willAddTool =
              value && requiresTool && !draft.tool_allowlist.includes(requiresTool);
            const effectiveBase =
              willAddTool && !allowlistUserTouched && draft.tool_allowlist.length === 0
                ? (capabilities?.tools ?? [])
                    .filter((t: { default_on?: boolean }) => t.default_on === true)
                    .map((t: { name: string }) => t.name)
                : draft.tool_allowlist;
            const nextAllowlist = willAddTool ? [...effectiveBase, requiresTool!] : effectiveBase;
            // Mark as touched only when defaults were actually materialized.
            if (effectiveBase !== draft.tool_allowlist) setAllowlistUserTouched(true);
            // feat-394 M9-E: features is the single-true-source for enable state.
            // HeartbeatCard reads features["heartbeat"]; CronCard reads features["cron_scheduling"].
            // No parallel sync into draft.heartbeat.enabled or draft.cron needed.
            const nextDraft = { ...draft, features: { ...(draft.features ?? {}), [key]: value }, tool_allowlist: nextAllowlist };
            setDraft(nextDraft);
          }}
          onPolicyChange={(value) => {
            setSaved(false);
            setErrorMessage(null);
            setDraft({ ...draft, group_reply_policy: value as AgentConfig["group_reply_policy"] });
          }}
        />

        {/* feat-394 M9 R6: HeartbeatCard — show cadence/activeHours config panel.
            When heartbeat is in capabilityFeatures (M9+), enable is controlled by
            the Features checkbox list above; the card renders only when enabled. */}
        {(() => {
          const hbInFeatures = capabilities?.features?.some((f: { key: string }) => f.key === "heartbeat") ?? false;
          // When heartbeat is a registered feature, show card only when the feature is on.
          // Otherwise (old Gateway), always show (backward compat).
          if (hbInFeatures && !draft.features?.heartbeat) return null;
          return (
            <HeartbeatCard
              agentId={agentId}
              draft={draft}
              onToggle={(enabled) => {
                // feat-394 M9-E: enable is in features["heartbeat"]; toggle via features only.
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, features: { ...(draft.features ?? {}), heartbeat: enabled } });
              }}
              onEveryChange={(every) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, heartbeat: { ...(draft.heartbeat ?? {}), every } });
              }}
              onActiveHoursChange={(start, end) => {
                setSaved(false);
                setErrorMessage(null);
                // feat-394-M11: no hardcoded "30m" fallback when spreading prev heartbeat.
                const prevHb = draft.heartbeat ?? {};
                const active_hours = start || end
                  ? { ...(prevHb.active_hours ?? {}), start, end }
                  : undefined;
                setDraft({ ...draft, heartbeat: { ...prevHb, active_hours } });
              }}
              hideEnableToggle={hbInFeatures}
            />
          );
        })()}

        {/* feat-394-M2 decision 5: CronCard — per-agent cron enable/disable.
            feat-394 M9 R6: when cron_scheduling is in capabilityFeatures, the enable
            toggle moves to the Features list; card renders only when cron feature is on. */}
        {(() => {
          const cronInFeatures = capabilities?.features?.some((f: { key: string }) => f.key === "cron_scheduling") ?? false;
          if (cronInFeatures && !draft.features?.cron_scheduling) return null;
          return (
            <CronCard
              agentId={agentId}
              draft={draft}
              onToggle={(enabled) => {
                // feat-394 M9-E: enable is in features["cron_scheduling"]; no draft.cron object.
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, features: { ...(draft.features ?? {}), cron_scheduling: enabled } });
              }}
              hideEnableToggle={cronInFeatures}
            />
          );
        })()}

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
              useDefaultOn={!allowlistUserTouched}
              onChange={(toolAllowlist) => {
                setSaved(false);
                setErrorMessage(null);
                // feat-394 M9-C: mark as touched so empty list means "no tools" not "defaults".
                setAllowlistUserTouched(true);
                // feat-379-M9 (決策 12): removed tool → uncheck any feature that requires it.
                const capFeats = capabilities?.features ?? [];
                // When transitioning from default mode (empty allowlist), the "removed" set is
                // derived from the effective defaults rather than the stored empty list.
                const effectiveAllowlist =
                  !allowlistUserTouched && draft.tool_allowlist.length === 0
                    ? (capabilities?.tools ?? [])
                        .filter((t: { default_on?: boolean }) => t.default_on === true)
                        .map((t: { name: string }) => t.name)
                    : draft.tool_allowlist;
                const removed = effectiveAllowlist.filter((t: string) => !toolAllowlist.includes(t));
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
              {availableModels.map((model) => {
                const providerSuffix = model.provider ? ` · ${model.provider}` : "";
                const baseLabel = `${model.name}${providerSuffix}`;
                return (
                  <option key={model.name} value={model.name}>
                    {model.name === platformDefaultModel
                      ? `${baseLabel} ${t("agents.form.access.modelDefaultSuffix")}`
                      : baseLabel}
                  </option>
                );
              })}
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
