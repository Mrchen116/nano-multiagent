import "./capability-editor.css";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  changeCapability,
  effectiveCapabilityFeatures,
  effectiveSelectedTools,
  fixedTools,
  sanitizeStaticToolAllowlist,
  skillSelected,
  type CapabilityAction,
  type CapabilityBlock,
  type CapabilityCatalog,
  type CapabilityDraft,
  type PluginToolCatalogEntry,
} from "@nano/product-contracts/capabilities";
import { useTranslation } from "../../../i18n";
import { getAgentCapabilityUsage, type CapabilitySnapshot, type PluginText } from "./im-agent-config-api";

export function localizePluginText(text: PluginText | null | undefined, language: string): string | undefined {
  if (!text) return undefined;
  if (typeof text === "string") return text.trim() || undefined;
  const candidate = text[language] ?? text[language.split("-")[0]!] ?? text.en ?? Object.values(text)[0];
  return candidate?.trim() || undefined;
}

export function capabilityCatalog(
  caps: CapabilitySnapshot | undefined,
  mode?: string,
  personal = false,
  draft?: CapabilityDraft | null,
  language = "zh",
): CapabilityCatalog & { fixed_tools: string[] } {
  const role = personal ? "personal" : "root";
  const features = (caps?.features ?? []).filter(feature => personal || feature.key !== "proactive_planning");
  const fixed = [...new Set([...(caps?.fixed_tools ?? []), ...fixedTools(mode, role, false)])];
  const baseCatalog: CapabilityCatalog = {
    features,
    tools: caps?.tools.map(x => x.name) ?? [],
    skills: caps?.skills.map(x => x.name) ?? [],
    fixed_tools: fixed,
  };
  const draftAllowsManager = draft ? effectiveSelectedTools(draft, baseCatalog).includes("plugin_manager") : true;
  const pluginTools: Record<string, PluginToolCatalogEntry> = {};
  for (const tool of caps?.tools ?? []) {
    if (tool.source_group !== "workspace") continue;
    pluginTools[tool.name] = {
      bundle: tool.plugin_bundle ?? null,
      title: localizePluginText(tool.plugin_title, language) ?? null,
      enabled: fixed.includes(tool.name) || (draftAllowsManager && tool.enabled !== false),
    };
  }
  return { ...baseCatalog, fixed_tools: fixed, plugin_tools: pluginTools };
}

export function restoreBlockedCapabilities<T extends CapabilityDraft>(
  draft: T,
  blocks: CapabilityBlock[],
  caps: CapabilitySnapshot | undefined,
  personal = false,
): T {
  const hadPersonalFlag = Object.prototype.hasOwnProperty.call(draft, "personal_agent");
  const effectivePersonal = personal || Boolean(draft.personal_agent);
  let next = {
    ...draft,
    ...(effectivePersonal ? { personal_agent: draft.personal_agent ?? true } : {}),
    features: { ...draft.features },
    tool_allowlist: [...(draft.tool_allowlist ?? [])],
    skills: draft.skills ? [...draft.skills] : draft.skills,
  } as T;
  for (const block of blocks) {
    if (block.code === "capability_unavailable") continue;
    const { kind, name } = block.target;
    if (kind === "feature") next.features = { ...next.features, [name]: true };
    if (kind === "tool") next.tool_allowlist = [...new Set([...(next.tool_allowlist ?? []), name])];
    if (kind === "skill") {
      const mode = next.skills_selection_mode ?? (next.skills?.length ? "explicit_allowlist" : "default_discovery");
      if (mode === "explicit_allowlist") next.skills = [...new Set([...(next.skills ?? []), name])];
      if (mode === "explicit_denylist") next.skills = (next.skills ?? []).filter(item => item !== name);
    }
  }
  const catalog = capabilityCatalog(caps, next.work_mode, effectivePersonal, next);
  const resolved = effectiveCapabilityFeatures(next, catalog.features ?? [], catalog);
  const enabled = catalog.features?.find(feature => resolved[feature.key] ?? feature.default_on);
  if (enabled) next = changeCapability(next, { kind: "feature", name: enabled.key, enabled: true }, catalog).draft;
  if (!hadPersonalFlag && "personal_agent" in next) {
    const { personal_agent: _personalAgent, ...clean } = next as T & { personal_agent?: boolean };
    return clean as T;
  }
  return next;
}

function CapabilityToast({ message, anchor, stamp }: { message: string; anchor: HTMLElement | null; stamp: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: 16, top: 16 });
  const [visible, setVisible] = useState(true);
  useLayoutEffect(() => {
    setVisible(true);
    const place = () => {
      if (!anchor?.isConnected) { setVisible(false); return; }
      const r = anchor.getBoundingClientRect();
      const h = ref.current?.getBoundingClientRect().height ?? 40;
      const w = ref.current?.getBoundingClientRect().width ?? 280;
      if (r.bottom < 0 || r.top > window.innerHeight) { setVisible(false); return; }
      const top = r.top - h - 8 >= 16 ? r.top - h - 8 : r.bottom + 8;
      if (top + h > window.innerHeight - 16) { setVisible(false); return; }
      setPosition({ top, left: Math.max(16, Math.min(r.left, window.innerWidth - w - 16)) });
    };
    place();
    const hide = () => setVisible(false);
    window.addEventListener("resize", hide);
    window.addEventListener("scroll", hide, true);
    const timer = window.setTimeout(() => setVisible(false), 2000);
    return () => { clearTimeout(timer); window.removeEventListener("resize", hide); window.removeEventListener("scroll", hide, true); };
  }, [anchor, stamp]);
  return createPortal(<div ref={ref} className="im-capability-toast" role="status" aria-live="polite" aria-atomic="true" aria-hidden={!visible} style={{ position: "fixed", zIndex: 100000, ...position, width: "max-content", maxWidth: "min(320px, calc(100vw - 32px))", padding: "8px 12px", borderRadius: 7, fontSize: 13, lineHeight: 1.5, color: "white", background: "#303638", boxShadow: "0 4px 16px #0002", pointerEvents: "none", opacity: visible ? 1 : 0, transition: "opacity 150ms ease" }}>{message}</div>, document.body);
}

export function useCapabilityEditor<T extends CapabilityDraft | null>(
  draft: T,
  setDraft: (value: T | ((current: T) => T)) => void,
  caps: CapabilitySnapshot | undefined,
  agentId?: string,
  personal = false,
) {
  const { t, i18n } = useTranslation();
  const latest = useRef(draft); latest.current = draft;
  const [toast, setToast] = useState<{ message: string; anchor: HTMLElement | null; stamp: number } | null>(null);
  useEffect(() => {
    if (!agentId || !caps) return;
    // Prime the read when the capability editor becomes available; closing still refreshes it.
    void (async () => { try { await getAgentCapabilityUsage(agentId); } catch { /* The close action reports unavailable usage. */ } })();
  }, [agentId, caps?.node_id]);
  const pending = useRef(false);
  const interactionAnchor = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const remember = (event: Event) => {
      if (event.target instanceof Element) interactionAnchor.current = event.target.closest<HTMLElement>("button, input, label");
    };
    document.addEventListener("pointerdown", remember, true);
    document.addEventListener("keydown", remember, true);
    return () => { document.removeEventListener("pointerdown", remember, true); document.removeEventListener("keydown", remember, true); };
  }, []);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  function show(blocks: CapabilityBlock[], anchor = interactionAnchor.current ?? document.activeElement as HTMLElement | null) {
    const block = blocks.find(item => !["required_by_feature", "fixed_capability"].includes(item.code)) ?? blocks[0]; if (!block) return;
    const names = (block.required_by ?? []).map(key => t(caps?.features?.find(f => f.key === key)?.label_i18n ?? key)).join("、");
    const key = blocks.length > 1 && blocks.every(item => ["required_by_feature", "fixed_capability"].includes(item.code)) ? "retained"
      : block.code === "provided_by_plugin" ? (block.plugin ? "providedByPlugin" : "providedByPluginGeneric")
      : block.code === "plugin_requires_manager" ? (block.plugin ? "pluginRequiresManager" : "pluginRequiresManagerGeneric")
      : block.code === "required_by_feature" ? ((block.required_by?.length ?? 0) === 1 ? "requiredByOne" : "requiredByMany")
      : block.code === "active_tasks" ? "activeTasks" : block.code === "active_schedules" ? "activeSchedules"
      : block.code === "fixed_capability" ? "fixed" : block.code === "capability_busy" ? "busy" : "unavailable";
    const message = t(`agents.capabilityFeedback.${key}`, { feature: names, plugin: block.plugin ?? "" });
    setToast({ message, anchor, stamp: Date.now() });
  }
  async function apply(actions: CapabilityAction[]) {
    if (!latest.current || pending.current) return;
    setToast(null);
    const anchor = interactionAnchor.current ?? document.activeElement as HTMLElement | null;
    const effectivePersonal = personal || Boolean(latest.current.personal_agent);
    let next: CapabilityDraft = effectivePersonal
      ? { ...latest.current, personal_agent: latest.current.personal_agent ?? true }
      : latest.current;
    const blocks: CapabilityBlock[] = [];
    const role = effectivePersonal ? "personal" : "root";
    const workspaceNames = (caps?.tools ?? []).filter(x => x.source_group === "workspace").map(x => x.name);
    for (const action of actions) {
      const catalog = capabilityCatalog(caps, next.work_mode, effectivePersonal, next, i18n.language);
      const result = changeCapability(next, action, catalog);
      blocks.push(...result.blocks); next = result.draft;
    }
    const previous = effectivePersonal
      ? { ...latest.current, personal_agent: latest.current.personal_agent ?? true }
      : latest.current;
    const prevCatalog = capabilityCatalog(caps, previous.work_mode, effectivePersonal, previous, i18n.language);
    const previousFeatures = effectiveCapabilityFeatures(previous, prevCatalog.features ?? [], prevCatalog);
    const previousTools = effectiveSelectedTools(previous, prevCatalog);
    const sanitizedNextTools = sanitizeStaticToolAllowlist(next.tool_allowlist ?? [], next.work_mode, role, workspaceNames);
    next = { ...next, tool_allowlist: sanitizedNextTools };
    const nextEffectiveTools = effectiveSelectedTools(next, prevCatalog);
    const removed = [
      ...Object.keys(previousFeatures).filter(k => previousFeatures[k] && !next.features?.[k]).map(name => ({ kind: "feature" as const, name })),
      ...previousTools.filter(k => !nextEffectiveTools.includes(k) && !prevCatalog.fixed_tools.includes(k)).map(name => ({ kind: "tool" as const, name })),
      ...(caps?.skills ?? []).filter(({name}) => skillSelected(previous, name) && !skillSelected(next, name)).map(({name}) => ({ kind: "skill" as const, name })),
    ];
    if (agentId && removed.length) {
      pending.current = true;
      try {
        const usage = await getAgentCapabilityUsage(agentId);
        for (const target of removed) {
          if (target.name === "task_graph" && usage.active_tasks > 0) blocks.push({ code: "active_tasks", target });
          if (target.kind === "feature" && target.name === "cron_scheduling" && usage.active_schedules > 0) blocks.push({ code: "active_schedules", target });
          if (usage.busy.some(x => x.kind === target.kind && x.name === target.name)) blocks.push({ code: "capability_busy", target });
        }
      } catch { blocks.push({ code: "capability_unavailable", target: removed[0] }); }
      finally { pending.current = false; }
      if (!mounted.current) return;
      if (blocks.some(b => ["active_tasks", "active_schedules", "capability_busy", "capability_unavailable"].includes(b.code))) { show(blocks, anchor); return; }
    }
    // Preserve text/model edits made while the usage request was in flight.
    setDraft(current => current ? { ...current, features: next.features, tool_allowlist: next.tool_allowlist, skills: next.skills, skills_selection_mode: next.skills_selection_mode } as T : current);
    if (blocks.length) show(blocks, anchor);
  }
  function toggleTool(name: string, enabled: boolean) {
    if (!latest.current) return;
    void apply([{ kind: "tool", name, enabled }]);
  }
  function tools(names: string[]) {
    if (!latest.current) return;
    const current = latest.current;
    const effectivePersonal = personal || Boolean(current.personal_agent);
    const catalog = capabilityCatalog(caps, current.work_mode, effectivePersonal, current, i18n.language);
    const selected = [...new Set([...effectiveSelectedTools(current, catalog), ...catalog.fixed_tools])];
    void apply([...new Set([...selected, ...names])].filter(n => selected.includes(n) !== names.includes(n)).map(name => ({ kind: "tool", name, enabled: names.includes(name) })));
  }
  function skills(disabled: string[]) {
    if (!latest.current) return;
    const current = latest.current;
    const enabled = (name: string) => skillSelected(current, name);
    const names = [...new Set([...(caps?.skills ?? []).map(x => x.name), ...(current.skills ?? []), ...disabled])];
    void apply(names.filter(n => enabled(n) === disabled.includes(n)).map(name => ({ kind: "skill", name, enabled: !disabled.includes(name) })));
  }
  function reject(error: unknown) {
    const blocks = (error as { blocks?: CapabilityBlock[] })?.blocks;
    if (!blocks?.length) return false;
    setDraft(current => current ? restoreBlockedCapabilities(current, blocks, caps, personal) : current);
    show(blocks); return true;
  }
  return { apply, toggleTool, tools, skills, reject, toast: toast ? <CapabilityToast {...toast} /> : null };
}
