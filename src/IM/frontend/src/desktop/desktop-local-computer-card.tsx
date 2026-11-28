import { DEFAULT_DESKTOP_NO_PROXY, type DesktopLocalInspectResponse, type DesktopWorkerProbeItem } from "@nano/product-contracts/desktop-local";
import { workerRuntimes, type WorkerRuntime } from "@nano/product-contracts/worker-runtimes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "../features/auth/auth-store";
import type { NodeSettingsProfile } from "../features/settings/im-settings-api";
import { BrowserPairingSection } from "../features/settings/nodes/browser-pairing-section";
import { computerName, computerVersion } from "../features/settings/nodes/node-display";
import { nodeUpdateNeedsRecovery, nodeUpdateSwitching } from "../features/settings/nodes/node-update-panel";
import { useTranslation } from "../i18n";
import {
  controlDesktopLocalNode,
  DesktopApiError,
  inspectDesktopLocalNode,
  probeDesktopWorkers,
  saveDesktopLocalNodeConfig,
} from "./desktop-api";
import { getDesktopBootContext, isDesktopClient } from "./desktop-context";
import { DesktopNodeOnboardingBanner } from "./desktop-node-onboarding-banner";
import { useDesktopUnsavedForm } from "./use-desktop-unsaved-form";
import "./desktop.css";

function localizeConfigSaveError(err: unknown, zh: boolean): string {
  const code = err instanceof DesktopApiError ? err.code : undefined;
  const raw = err instanceof Error ? err.message : "";
  if (code === "invalid_proxy_scheme" || raw.includes("socks://")) {
    return zh
      ? "仅支持 http:// 或 https:// 代理地址，暂不支持 socks:// 协议；原配置已保留。"
      : "Only http:// and https:// proxy URLs are supported (socks:// is not supported).";
  }
  if (code === "invalid_proxy_url" || raw.includes("Proxy URL")) {
    return zh
      ? "请填写合法的 http:// 或 https:// 代理地址（例如 http://127.0.0.1:7890）。"
      : "Enter a valid http:// or https:// proxy address (for example http://127.0.0.1:7890).";
  }
  if (code === "unregistered_approval_model" || raw.includes("tool_approval_model is not registered")) {
    return zh
      ? "所选安全审核模型尚未在本机注册，请先在「AI 模型与 API」中添加或恢复默认跟随。"
      : "The selected safety review model is not registered yet; add it in AI Models & API or reset to default.";
  }
  if (code === "invalid_env_var" || raw.includes("environment variable") || raw.includes("managed automatically")) {
    return zh
      ? "环境变量名称或取值格式不合法（请使用字母/下划线开头且不重复，代理变量请在上方代理区设置）。"
      : "Invalid or duplicate environment variable name/value.";
  }
  if (code === "restart_rolled_back" || raw.includes("rolled back")) {
    return zh
      ? "新设置重启后未能正常就绪，已自动回退至原先可用的设置与运行状态。"
      : "Restart failed under the new settings; automatically rolled back to the previous working configuration.";
  }
  return raw || (zh ? "保存设置失败，已保留原可用设置。" : "Failed to apply settings; previous configuration preserved.");
}

const WORKER_LABELS: Record<WorkerRuntime, { zh: string; en: string }> = {
  dsh: { zh: "内置默认引擎（开箱即用）", en: "Built-in default engine (Ready out of the box)" },
  codex: { zh: "Codex CLI", en: "Codex CLI" },
  claude: { zh: "Claude Code", en: "Claude Code" },
  antigravity: { zh: "Antigravity CLI", en: "Antigravity CLI" },
};

/** Top-pinned "这台电脑" progressive-disclosure card on `/settings/nodes` inside Crewden Desktop. */
export function DesktopLocalComputerCard({
  nodes,
  onSaveAlias,
  aliasSaving,
  aliasError,
  onResetAliasError,
  defaultPairBrowserOpen,
}: {
  nodes: NodeSettingsProfile[];
  onSaveAlias(node: NodeSettingsProfile, alias: string): Promise<unknown>;
  aliasSaving: boolean;
  aliasError: boolean;
  onResetAliasError(): void;
  onOpenRecovery?(nodeId: string): void;
  defaultPairBrowserOpen?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const userId = useAuthStore((s) => s.user?.id);
  const client = useQueryClient();

  const inspectQuery = useQuery({
    queryKey: ["desktop", "local-node", userId],
    queryFn: () => inspectDesktopLocalNode(),
    enabled: isDesktopClient() && Boolean(userId),
    refetchInterval: 10_000,
  });

  useEffect(() => {
    const refresh = () => { void client.invalidateQueries({ queryKey: ["desktop", "local-node", userId] }); };
    window.addEventListener("crewden:login-autostart-changed", refresh);
    return () => window.removeEventListener("crewden:login-autostart-changed", refresh);
  }, [client, userId]);

  const inspect = inspectQuery.data;
  const matchedNode = inspect?.node_id ? nodes.find((n) => n.node_id === inspect.node_id) : undefined;

  const [renaming, setRenaming] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");
  const [renameEmpty, setRenameEmpty] = useState(false);

  const [workerRuntime, setWorkerRuntime] = useState<WorkerRuntime>("dsh");
  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [proxyUrl, setProxyUrl] = useState("");
  const [noProxy, setNoProxy] = useState(DEFAULT_DESKTOP_NO_PROXY);
  const [approvalSelect, setApprovalSelect] = useState<string>("");
  const [customApprovalModel, setCustomApprovalModel] = useState<string>("");
  const [envVars, setEnvVars] = useState<{ key: string; value: string }[]>([]);
  const [dirty, setDirty] = useState(false);
  useDesktopUnsavedForm(dirty || renaming);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [confirmBusyCount, setConfirmBusyCount] = useState<number | null>(null);
  const [liveWorkers, setLiveWorkers] = useState<DesktopWorkerProbeItem[] | null>(null);

  const [logQuery, setLogQuery] = useState("");
  const [logCopied, setLogCopied] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [logsOpen, setLogsOpen] = useState(false);

  function syncDraftFromInspect(data: DesktopLocalInspectResponse) {
    setWorkerRuntime(data.worker_runtime ?? "dsh");
    setProxyEnabled(Boolean(data.proxy?.enabled));
    setProxyUrl(data.proxy?.url ?? "");
    setNoProxy(data.proxy?.no_proxy ?? DEFAULT_DESKTOP_NO_PROXY);
    const currentApproval = data.tool_approval_model ?? "";
    const isKnown = !currentApproval || Boolean(data.registered_models?.some((m) => m.name === currentApproval));
    setApprovalSelect(isKnown ? currentApproval : "__custom__");
    setCustomApprovalModel(isKnown ? "" : currentApproval);
    setEnvVars((data.environment ?? []).map((item) => ({ ...item })));
    setLiveWorkers(null);
    setDirty(false);
  }

  useEffect(() => {
    if (inspect && !dirty && !saveError && (inspect.ownership === "managed_online" || inspect.ownership === "managed_stopped")) {
      syncDraftFromInspect(inspect);
    }
  }, [inspect, dirty, saveError]);

  const windows = getDesktopBootContext()?.platform === "win32-x64";
  const candidatePath = [...envVars].reverse().find(({ key }) =>
    (windows ? key.trim().toUpperCase() : key.trim()) === "PATH",
  )?.value;
  useEffect(() => {
    if (!dirty || !inspect || (inspect.ownership !== "managed_online" && inspect.ownership !== "managed_stopped")) return;
    const timer = window.setTimeout(() => {
      void probeDesktopWorkers(candidatePath)
        .then((res) => setLiveWorkers(res.workers))
        .catch(() => {});
    }, 300);
    return () => window.clearTimeout(timer);
  }, [candidatePath, dirty, inspect]);

  const lifecycleMutation = useMutation({
    mutationFn: controlDesktopLocalNode,
    onSuccess: async (next) => {
      client.setQueryData<DesktopLocalInspectResponse>(
        ["desktop", "local-node", userId],
        (prev) => (prev ? { ...prev, ...next } : next),
      );
      await Promise.all([
        client.invalidateQueries({ queryKey: ["settings", "nodes"] }),
        client.invalidateQueries({ queryKey: ["onboarding"] }),
        client.invalidateQueries({ queryKey: ["chat", "nodes"] }),
      ]);
    },
  });

  const configMutation = useMutation({
    mutationFn: saveDesktopLocalNodeConfig,
    onSuccess: async (next) => {
      setSaveError(null);
      setConfirmBusyCount(null);
      client.setQueryData(["desktop", "local-node", userId], next);
      syncDraftFromInspect(next);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["settings", "nodes"] }),
        client.invalidateQueries({ queryKey: ["onboarding"] }),
      ]);
    },
    onError: (err) => {
      if (err instanceof DesktopApiError && (err.code === "active_tasks_running" || err.status === 409)) {
        const match = err.message.match(/(\d+)/);
        setConfirmBusyCount(match ? Math.max(1, Number(match[1])) : Math.max(1, inspect?.active_tasks ?? 1));
        setSaveError(null);
        return;
      }
      setConfirmBusyCount(null);
      setSaveError(localizeConfigSaveError(err, zh));
    },
  });

  if (!isDesktopClient() || !inspect) return null;

  if (
    inspect.ownership === "unbound" ||
    inspect.ownership === "takeover_available" ||
    inspect.ownership === "foreign_owner"
  ) {
    return <DesktopNodeOnboardingBanner inline />;
  }

  const displayName = matchedNode ? computerName(matchedNode, inspect.node_name) : inspect.node_name;
  const running = Boolean(inspect.running);
  const canManageRemote =
    Boolean(matchedNode) &&
    matchedNode!.status === "online" &&
    !nodeUpdateSwitching(matchedNode!.update) &&
    !nodeUpdateNeedsRecovery(matchedNode!.update);
  const versionText = matchedNode ? computerVersion(matchedNode) : inspect.version || "—";
  const agentList = inspect.agents ?? [];
  const assistantSummary = agentList.length
    ? text(
        `${agentList.length} 位助手（${agentList.map((a) => a.display_name).join("、")}）`,
        `${agentList.length} assistants (${agentList.map((a) => a.display_name).join(", ")})`,
      )
    : t("computers.assistantCount", { count: matchedNode?.agent_count ?? 0 });

  const workers = liveWorkers ?? inspect.workers ?? [];
  const logs = (inspect.logs ?? []).filter(
    (line) => !logQuery.trim() || line.toLowerCase().includes(logQuery.trim().toLowerCase()),
  );
  const effectiveApprovalModel =
    approvalSelect === "__custom__" ? customApprovalModel.trim() || null : approvalSelect || null;

  return (
    <section className="local-computer-card" aria-label={text("这台电脑", "This computer")} data-testid="desktop-local-computer-card">
      <div className="local-computer-summary">
        <div style={{ flex: "1 1 260px", minWidth: 0 }}>
          {renaming && matchedNode ? (
            <form
              className="desktop-action-row"
              onSubmit={(e) => {
                e.preventDefault();
                if (!renameDraft.trim()) {
                  setRenameEmpty(true);
                  return;
                }
                void onSaveAlias(matchedNode, renameDraft.trim())
                  .then(() => setRenaming(false))
                  .catch(() => {});
              }}
            >
              <input
                className="desktop-text-input"
                style={{ maxWidth: 240 }}
                aria-label={t("computers.name")}
                value={renameDraft}
                disabled={aliasSaving}
                onChange={(e) => {
                  setRenameDraft(e.target.value);
                  setRenameEmpty(false);
                  onResetAliasError();
                }}
              />
              <button type="submit" className="desktop-btn primary compact" disabled={aliasSaving}>
                {t(aliasSaving ? "settings.nodes.saving" : "computers.saveName")}
              </button>
              <button
                type="button"
                className="desktop-btn compact"
                disabled={aliasSaving}
                onClick={() => {
                  setRenaming(false);
                  setRenameEmpty(false);
                  onResetAliasError();
                }}
              >
                {t("common.cancel")}
              </button>
              {(renameEmpty || aliasError) && (
                <p className="node-form-error" role="alert" style={{ width: "100%", margin: "4px 0 0" }}>
                  {t(renameEmpty ? "computers.nameRequired" : "computers.saveFailed")}
                </p>
              )}
            </form>
          ) : (
            <div className="local-computer-title-row">
              <h2>{displayName}</h2>
              <span className="desktop-chip">{text("这台电脑", "This computer")}</span>
              {running ? (
                <span className="desktop-chip online">
                  <span className="desktop-status-dot online" />
                  {text("在线 · 运行正常", "Online · Ready")}
                </span>
              ) : (
                <span className="desktop-chip muted">
                  <span className="desktop-status-dot" />
                  {text("已停止运行", "Stopped")}
                </span>
              )}
              {matchedNode && (
                <button
                  type="button"
                  className="desktop-btn subtle compact"
                  disabled={!canManageRemote}
                  onClick={() => {
                    setRenameDraft(displayName);
                    setRenameEmpty(false);
                    onResetAliasError();
                    setRenaming(true);
                  }}
                >
                  {text("改名", "Rename")}
                </button>
              )}
            </div>
          )}
          <div className="local-computer-meta">
            <span>Nano {versionText}</span>
            <span>·</span>
            <span>{assistantSummary}</span>
          </div>
        </div>

        <div className="local-computer-controls">
          {running && matchedNode && canManageRemote ? (
            <Link className="desktop-btn compact" to={`/settings/nodes/${encodeURIComponent(matchedNode.node_id)}/agents/new`}>
              + {text("新建助手", "Create assistant")}
            </Link>
          ) : (
            <button type="button" className="desktop-btn compact" disabled>
              + {text("新建助手", "Create assistant")}
            </button>
          )}
          {running ? (
            <>
              <button
                type="button"
                className="desktop-btn compact"
                disabled={lifecycleMutation.isPending}
                onClick={() => lifecycleMutation.mutate({ action: "restart" })}
              >
                {text("重启", "Restart")}
              </button>
              <button
                type="button"
                className="desktop-btn compact"
                disabled={lifecycleMutation.isPending}
                onClick={() => lifecycleMutation.mutate({ action: "stop" })}
              >
                {text("停止", "Stop")}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="desktop-btn primary compact"
              disabled={lifecycleMutation.isPending}
              onClick={() => lifecycleMutation.mutate({ action: "start" })}
            >
              {text("启动", "Start")}
            </button>
          )}
        </div>
      </div>

      {lifecycleMutation.isError && (
        <p className="node-form-error" role="alert" style={{ padding: "0 22px 10px", margin: 0 }}>
          {lifecycleMutation.error instanceof Error ? lifecycleMutation.error.message : text("操作失败", "Action failed")}
        </p>
      )}

      <div className="local-quick-strip">
        <div>
          <strong style={{ fontSize: 13 }}>{text("开机登录自启", "Start at login")}</strong>
          <span style={{ fontSize: 12, color: "var(--im-text-muted)", marginLeft: 6 }}>
            {text(
              "登录电脑后静默驻留托盘并在后台自动启动（即时保存，不打断当前任务）",
              "Stay silently in tray/menubar on login and start automatically in the background (saved instantly)",
            )}
          </span>
        </div>
        <button
          type="button"
          className="desktop-switch"
          role="switch"
          aria-label={text("开机登录自启", "Start at login")}
          aria-checked={Boolean(inspect.autostart)}
          disabled={lifecycleMutation.isPending}
          onClick={() => lifecycleMutation.mutate({ action: "autostart", enabled: !inspect.autostart })}
        >
          <i />
        </button>
      </div>

      {inspect.browser?.supported && (
        <BrowserPairingSection
          variant="desktop-strip"
          nodeId={inspect.node_id}
          initialBrowser={inspect.browser}
          localDesktopTransport
          defaultExpanded={defaultPairBrowserOpen}
        />
      )}

      <details className="local-section-disclosure" onToggle={(e) => setAdvancedOpen(e.currentTarget.open)}>
        <summary>
          <span>
            {text(
              "高级运行设置（外部编程工具 · 网络代理 · 安全审核模型 · 环境变量）",
              "Advanced runtime settings (External coding tools · Proxy · Safety review model · Environment)",
            )}
          </span>
          <span style={{ fontSize: 12, color: "var(--im-accent)" }}>
            {dirty
              ? text("● 有待保存修改", "● Unsaved changes")
              : advancedOpen
                ? text("收起设置 ▴", "Collapse ▴")
                : text("展开设置 ▾", "Expand ▾")}
          </span>
        </summary>
        <div className="local-sections-grid">
          <div className="local-panel-box">
            <h3>{text("外部编程工具接入", "External coding tools")}</h3>
            <p className="hint">
              {text(
                "选择助手处理编程与复杂电脑任务时使用的引擎；电脑上装好的工具会自动识别。",
                "Choose the engine assistants use for coding and complex tasks; installed CLI tools are detected automatically.",
              )}
            </p>
            <div className="local-worker-options" role="radiogroup" aria-label={text("外部编程工具接入", "External coding tools")}>
              {workerRuntimes.map((rt) => {
                const probe = workers.find((w) => w.runtime === rt);
                const available = rt === "dsh" ? true : Boolean(probe?.available);
                const detailText =
                  rt === "dsh"
                    ? text("随客户端内置 · 无需额外安装", "Built into Crewden · No extra install needed")
                    : probe?.resolved_path
                      ? `${text("已检测到", "Detected")} · ${probe.resolved_path}`
                      : text(
                          "本机暂未安装（安装后自动识别，也可在下方补充 PATH）",
                          "Not installed yet (auto-detected once installed, or add PATH below)",
                        );
                return (
                  <button
                    key={rt}
                    type="button"
                    className="local-worker-option"
                    role="radio"
                    aria-checked={workerRuntime === rt}
                    onClick={() => {
                      setWorkerRuntime(rt);
                      setDirty(true);
                      setSaveError(null);
                    }}
                  >
                    <div>
                      <strong style={{ fontSize: 13 }}>{zh ? WORKER_LABELS[rt].zh : WORKER_LABELS[rt].en}</strong>
                      <small>{detailText}</small>
                    </div>
                    <span className={`desktop-chip ${available ? "online" : "warn"}`}>
                      {available ? text("可用", "Ready") : text("未安装", "Not found")}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="local-panel-box">
            <h3>{text("网络代理与安全审核模型", "Network proxy & safety review model")}</h3>
            <p className="hint">
              {text(
                "为助手联网与命令行工具统一配置 HTTP/HTTPS 代理，或指定独立模型审核敏感操作。",
                "Route assistant and CLI traffic through an HTTP/HTTPS proxy, or pick a dedicated model to review sensitive actions.",
              )}
            </p>
            <div className="local-toggle-row">
              <strong style={{ fontSize: 13 }}>{text("启用本机 HTTP/HTTPS 代理", "Enable HTTP/HTTPS proxy")}</strong>
              <button
                type="button"
                className="desktop-switch"
                role="switch"
                aria-label={text("启用本机代理", "Enable HTTP/HTTPS proxy")}
                aria-checked={proxyEnabled}
                onClick={() => {
                  setProxyEnabled((v) => !v);
                  setDirty(true);
                  setSaveError(null);
                }}
              >
                <i />
              </button>
            </div>
            <div className="local-field" style={{ marginTop: 8 }}>
              <label htmlFor="desktop-proxy-url">{text("代理地址", "Proxy URL")}</label>
              <input
                id="desktop-proxy-url"
                className="desktop-text-input"
                value={proxyUrl}
                placeholder="http://127.0.0.1:7890"
                disabled={!proxyEnabled}
                onChange={(e) => {
                  setProxyUrl(e.target.value);
                  setDirty(true);
                  setSaveError(null);
                }}
              />
            </div>
            <div className="local-field">
              <label htmlFor="desktop-no-proxy">{text("直连排除地址 (NO_PROXY)", "Bypass hosts (NO_PROXY)")}</label>
              <input
                id="desktop-no-proxy"
                className="desktop-text-input"
                value={noProxy}
                disabled={!proxyEnabled}
                onChange={(e) => {
                  setNoProxy(e.target.value);
                  setDirty(true);
                  setSaveError(null);
                }}
              />
            </div>
            <div className="local-field" style={{ marginBottom: approvalSelect === "__custom__" ? 8 : 0 }}>
              <label htmlFor="desktop-approval-model">{text("安全审核模型", "Safety review model")}</label>
              <select
                id="desktop-approval-model"
                className="desktop-select-input"
                value={approvalSelect}
                onChange={(e) => {
                  setApprovalSelect(e.target.value);
                  setDirty(true);
                  setSaveError(null);
                }}
              >
                <option value="">{text("跟随各助手自身模型（默认）", "Follow each assistant's model (Default)")}</option>
                {(inspect.registered_models ?? []).map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.name}（{m.display_name || text("已添加", "Added")}）
                  </option>
                ))}
                <option value="__custom__">{text("手动输入模型标识…", "Enter custom model identifier…")}</option>
              </select>
            </div>
            {approvalSelect === "__custom__" && (
              <div className="local-field" style={{ marginBottom: 0 }}>
                <input
                  className="desktop-text-input"
                  aria-label={text("自定义安全审核模型标识", "Custom safety review model identifier")}
                  placeholder="provider:model-id"
                  value={customApprovalModel}
                  onChange={(e) => {
                    setCustomApprovalModel(e.target.value);
                    setDirty(true);
                    setSaveError(null);
                  }}
                />
              </div>
            )}
          </div>

          <div className="local-panel-box full">
            <h3>
              <span>{text("本机环境变量", "Environment variables")}</span>
              <button
                type="button"
                className="desktop-btn subtle compact"
                onClick={() => {
                  setEnvVars((rows) => [...rows, { key: "", value: "" }]);
                  setDirty(true);
                  setSaveError(null);
                }}
              >
                + {text("添加变量", "Add variable")}
              </button>
            </h3>
            <p className="hint">
              {text(
                "为本机命令行工具补充自定义环境变量（例如自定义 PATH 目录或内网工具地址）。",
                "Pass custom environment variables to local CLI tools (such as custom PATH folders or internal service URLs).",
              )}
            </p>
            <div className="local-env-list">
              {envVars.map((row, idx) => (
                <div key={idx} className="env-item-card">
                  <input
                    className="desktop-text-input"
                    value={row.key}
                    placeholder={text("变量名（如 SEARXNG_URL）", "Variable name (e.g. PATH)")}
                    aria-label={text("环境变量名", "Environment variable name")}
                    onChange={(e) => {
                      const val = e.target.value;
                      setEnvVars((rows) => rows.map((r, i) => (i === idx ? { ...r, key: val } : r)));
                      setDirty(true);
                      setSaveError(null);
                    }}
                  />
                  <input
                    className="desktop-text-input"
                    value={row.value}
                    placeholder={text("变量值", "Variable value")}
                    aria-label={text("环境变量值", "Environment variable value")}
                    onChange={(e) => {
                      const val = e.target.value;
                      setEnvVars((rows) => rows.map((r, i) => (i === idx ? { ...r, value: val } : r)));
                      setDirty(true);
                      setSaveError(null);
                    }}
                  />
                  <button
                    type="button"
                    className="desktop-btn compact"
                    onClick={() => {
                      setEnvVars((rows) => rows.filter((_, i) => i !== idx));
                      setDirty(true);
                      setSaveError(null);
                    }}
                  >
                    {text("移除此项", "Remove")}
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div
            className={`local-save-bar ${saveError ? "error" : confirmBusyCount !== null || dirty ? "warn" : ""}`}
            role={saveError || confirmBusyCount !== null ? "alert" : undefined}
          >
            <div style={{ fontSize: 13, flex: "1 1 220px", minWidth: 0 }}>
              {confirmBusyCount !== null ? (
                <>
                  <strong>{text("存在运行中的本机任务：", "Active local tasks running: ")}</strong>
                  {text(
                    `当前有 ${confirmBusyCount} 项任务正在执行，立即重启将中断当前轮次。请确认立即重启，或等待任务完成后再保存。`,
                    `${confirmBusyCount} task(s) are currently running on this computer. Confirm immediate restart or wait until they finish.`,
                  )}
                </>
              ) : saveError ? (
                <>
                  <strong>{text("配置未生效：", "Settings not applied: ")}</strong>
                  {saveError}
                </>
              ) : dirty ? (
                running ? (
                  <>
                    <strong>{text("待重启生效：", "Restart required: ")}</strong>
                    {(inspect.active_tasks ?? 0) > 0
                      ? text(
                          `当前有 ${inspect.active_tasks} 项本机任务正在执行；点击保存时会再次向你确认重启时机。`,
                          `${inspect.active_tasks} task(s) currently running; you will be asked to confirm before restarting.`,
                        )
                      : text("保存后将自动平滑重启本机服务以应用新设置。", "Saving smoothly restarts the local service to apply changes.")}
                  </>
                ) : (
                  <>
                    <strong>{text("有待保存修改：", "Unsaved changes: ")}</strong>
                    {text("保存后将写入本机设置，下次启动即生效。", "Saving updates local settings for the next start.")}
                  </>
                )
              ) : (
                <span style={{ color: "var(--im-text-muted)" }}>
                  {text("当前显示的是这台电脑正在生效的设置。", "Showing the active settings on this computer.")}
                </span>
              )}
            </div>
            <div className="desktop-action-row">
              {confirmBusyCount !== null ? (
                <>
                  <button
                    type="button"
                    className="desktop-btn compact"
                    disabled={configMutation.isPending}
                    onClick={() => setConfirmBusyCount(null)}
                  >
                    {text("等待任务完成", "Wait for tasks")}
                  </button>
                  <button
                    type="button"
                    className="desktop-btn primary compact"
                    disabled={configMutation.isPending}
                    onClick={() =>
                      configMutation.mutate({
                        worker_runtime: workerRuntime,
                        proxy: {
                          enabled: proxyEnabled,
                          url: proxyUrl,
                          no_proxy: noProxy,
                        },
                        tool_approval_model: effectiveApprovalModel,
                        environment: envVars.filter((r) => r.key.trim() !== "" || r.value.trim() !== ""),
                        confirm_restart: true,
                      })
                    }
                  >
                    {configMutation.isPending
                      ? text("正在重启…", "Restarting…")
                      : text("确认立即保存并重启", "Confirm restart now")}
                  </button>
                </>
              ) : (
                <>
                  {(dirty || saveError) && (
                    <button
                      type="button"
                      className="desktop-btn compact"
                      disabled={configMutation.isPending}
                      onClick={() => {
                        setSaveError(null);
                        setConfirmBusyCount(null);
                        syncDraftFromInspect(inspect);
                      }}
                    >
                      {text("放弃修改", "Discard changes")}
                    </button>
                  )}
                  <button
                    type="button"
                    className="desktop-btn primary compact"
                    disabled={(!dirty && !saveError) || configMutation.isPending}
                    onClick={() => {
                      if (running && (inspect.active_tasks ?? 0) > 0) {
                        setConfirmBusyCount(inspect.active_tasks ?? 1);
                        return;
                      }
                      configMutation.mutate({
                        worker_runtime: workerRuntime,
                        proxy: {
                          enabled: proxyEnabled,
                          url: proxyUrl,
                          no_proxy: noProxy,
                        },
                        tool_approval_model: effectiveApprovalModel,
                        environment: envVars.filter((r) => r.key.trim() !== "" || r.value.trim() !== ""),
                      });
                    }}
                  >
                    {configMutation.isPending
                      ? text("正在保存…", "Saving…")
                      : running
                        ? text("保存并重启生效", "Save & restart to apply")
                        : text("保存设置", "Save settings")}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </details>

      <details className="local-section-disclosure" onToggle={(e) => setLogsOpen(e.currentTarget.open)}>
        <summary>
          <span>{text("本机运行日志与连接诊断", "Local logs & diagnostics")}</span>
          <span style={{ fontSize: 12, color: "var(--im-text-muted)" }}>
            {logsOpen ? text("收起日志 ▴", "Collapse logs ▴") : text("查看 / 搜索日志 ▾", "View / search logs ▾")}
          </span>
        </summary>
        <div style={{ padding: "4px 22px 20px" }}>
          <div className="local-log-toolbar">
            <input
              className="desktop-text-input"
              style={{ maxWidth: 260, minHeight: 32 }}
              placeholder={text("搜索日志关键字（如 WARN、probe）…", "Filter logs (e.g. WARN, probe)…")}
              aria-label={text("搜索运行日志", "Filter runtime logs")}
              value={logQuery}
              onChange={(e) => setLogQuery(e.target.value)}
            />
            <button type="button" className="desktop-btn compact" onClick={() => void inspectQuery.refetch()}>
              {text("刷新", "Refresh")}
            </button>
            <button
              type="button"
              className="desktop-btn compact"
              onClick={() => {
                void navigator.clipboard
                  ?.writeText(logs.join("\n"))
                  .then(() => {
                    setLogCopied(true);
                    window.setTimeout(() => setLogCopied(false), 1800);
                  })
                  .catch(() => {});
              }}
            >
              {logCopied ? text("已复制", "Copied") : text("复制日志", "Copy logs")}
            </button>
          </div>
          <div className="local-log-viewer" data-testid="desktop-local-log-viewer">
            {logs.length ? logs.join("\n") : text("无匹配的日志记录", "No matching log entries")}
          </div>
        </div>
      </details>
    </section>
  );
}
