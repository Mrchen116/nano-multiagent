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
      ? "所选专用自动审批模型尚未在本机模型目录注册，请先选择已注册模型或恢复默认继承。"
      : "The selected dedicated approval model is not registered on this computer.";
  }
  if (code === "invalid_env_var" || raw.includes("environment variable") || raw.includes("managed automatically")) {
    return zh
      ? "环境变量名称或取值格式不合法（请使用字母/下划线开头且不重复，代理变量请在上方代理区设置）。"
      : "Invalid or duplicate environment variable name/value.";
  }
  if (code === "restart_rolled_back" || raw.includes("rolled back")) {
    return zh
      ? "新配置重启后未能正常就绪，已自动回退至原先可用的节点配置与运行状态。"
      : "Restart failed under the new settings; automatically rolled back to the previous working configuration.";
  }
  return raw || (zh ? "保存配置失败，已保留原可用配置。" : "Failed to apply settings; previous configuration preserved.");
}

const WORKER_LABELS: Record<WorkerRuntime, { zh: string; en: string }> = {
  dsh: { zh: "内置 DSH 运行时（默认）", en: "Bundled DSH runtime (Default)" },
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
                  {text("本机在线 · 运行时正常", "Online · Runtime ready")}
                </span>
              ) : (
                <span className="desktop-chip muted">
                  <span className="desktop-status-dot" />
                  {text("本机节点已停止", "Local node stopped")}
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
              "登录系统后静默驻留托盘并自动拉起本机节点（免重启即时保存）",
              "Stay silently in tray/menubar on login and start local node automatically (saved without restarting active tasks)",
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

      <details className="local-section-disclosure">
        <summary>
          <span>
            {text(
              "本机运行配置（Worker 框架 · 网络代理 · 审批模型 · 环境变量）",
              "Local runtime settings (Workers · Proxy · Approval model · Environment)",
            )}
          </span>
          <span style={{ fontSize: 12, color: "var(--im-accent)" }}>
            {dirty ? text("● 有待保存修改", "● Unsaved changes") : text("展开配置 ▾", "Expand ▾")}
          </span>
        </summary>
        <div className="local-sections-grid">
          <div className="local-panel-box">
            <h3>{text("一级委派 Worker 框架", "Delegated Worker runtime")}</h3>
            <p className="hint">{text("按合并后的运行 PATH 实时探测本机可执行状态。", "Probed against merged service PATH in real time.")}</p>
            <div className="local-worker-options" role="radiogroup" aria-label={text("本机一级委派 Worker 框架", "Delegated Worker runtime")}>
              {workerRuntimes.map((rt) => {
                const probe = workers.find((w) => w.runtime === rt);
                const available = rt === "dsh" ? true : Boolean(probe?.available);
                const detailText =
                  probe?.resolved_path
                    ? `${text("已检测到", "Detected")} · ${probe.resolved_path}`
                    : probe?.detail || (rt === "dsh" ? text("随应用受管提供 · 已就绪", "Bundled · Ready") : text("未检测到可执行文件", "Not found in PATH"));
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
                      {available ? text("可用", "Ready") : text("未就绪", "Missing")}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="local-panel-box">
            <h3>{text("网络代理与专用审批模型", "Network proxy & approval model")}</h3>
            <p className="hint">{text("仅支持 HTTP/HTTPS 代理地址，自动同步本机出站与子进程代理变量。", "HTTP/HTTPS proxies only; automatically syncs all 9 outbound proxy variables.")}</p>
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
              <label htmlFor="desktop-approval-model">{text("专用自动审批模型", "Dedicated approval model")}</label>
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
                    {m.name}（{m.display_name || text("已注册", "Registered")}）
                  </option>
                ))}
                <option value="__custom__">{text("手动输入模型标识…", "Enter custom model identifier…")}</option>
              </select>
            </div>
            {approvalSelect === "__custom__" && (
              <div className="local-field" style={{ marginBottom: 0 }}>
                <input
                  className="desktop-text-input"
                  aria-label={text("自定义审批模型标识", "Custom approval model identifier")}
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
              <span>{text("本机运行环境变量", "Local environment variables")}</span>
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
            <p className="hint">{text("独立管理非代理环境变量（如自定义工具 PATH、本地搜索地址）。", "Manage non-proxy environment variables (such as custom PATH or local tool endpoints).")}</p>
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
                      : text("保存后将自动重启本机节点并验证恢复上线。", "Saving restarts the local node and verifies readiness.")}
                  </>
                ) : (
                  <>
                    <strong>{text("有待保存修改：", "Unsaved changes: ")}</strong>
                    {text("保存后将写入本机配置，下次启动即生效。", "Saving updates local configuration for the next start.")}
                  </>
                )
              ) : (
                <span style={{ color: "var(--im-text-muted)" }}>
                  {text("当前显示的是本机节点已确认生效的配置。", "Showing the active confirmed configuration of this computer.")}
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
                        ? text("保存并重启本机节点", "Save and restart local node")
                        : text("保存配置", "Save settings")}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </details>

      <details className="local-section-disclosure">
        <summary>
          <span>{text("本机运行日志与连接诊断", "Local logs & diagnostics")}</span>
          <span style={{ fontSize: 12, color: "var(--im-text-muted)" }}>{text("查看 / 搜索日志 ▾", "View / search logs ▾")}</span>
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
