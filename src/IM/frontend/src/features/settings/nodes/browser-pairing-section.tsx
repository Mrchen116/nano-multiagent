import type {
  DesktopBrowserActionInput,
  DesktopBrowserActionResponse,
  DesktopBrowserStatus,
  DesktopLocalInspectResponse,
} from "@nano/product-contracts/desktop-local";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { DesktopApiError, manageDesktopLocalBrowser } from "../../../desktop/desktop-api";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../auth/auth-store";
import { manageNodeBrowser, NodeBrowserRequestError } from "../im-settings-api";
import "./browser-pairing-section.css";

function localizeBrowserError(err: unknown, zh: boolean): string {
  const code =
    err instanceof DesktopApiError || err instanceof NodeBrowserRequestError ? err.code : undefined;
  const raw = err instanceof Error ? err.message : "";
  if (code === "invalid_browser_token") {
    return zh
      ? "请粘贴官方 Playwright 扩展显示的合法 Token（支持直接粘贴 PLAYWRIGHT_MCP_EXTENSION_TOKEN=… 整行）。"
      : "Paste a valid token from the official Playwright Extension (the full PLAYWRIGHT_MCP_EXTENSION_TOKEN=… line also works).";
  }
  if (code === "browser_extension_missing") {
    return zh
      ? "所选 Chrome 配置尚未安装 Playwright Extension (0.5.0+)，请先点击上方按钮在 Chrome 中完成安装。"
      : "Playwright Extension (0.5.0+) is not installed in the selected Chrome profile yet.";
  }
  if (code === "chrome_not_installed") {
    return zh
      ? "未在该电脑检测到 Google Chrome，请先安装 Chrome 158+。"
      : "Google Chrome was not found on this computer. Install Chrome 158+ first.";
  }
  if (code === "invalid_browser_profile") {
    return zh
      ? "请选择合法的 Chrome 配置目录（如 Default 或 Profile 1）。"
      : "Choose a valid Chrome profile directory name (such as Default or Profile 1).";
  }
  return raw || (zh ? "浏览器配对操作失败。" : "Browser pairing action failed.");
}

export interface BrowserPairingSectionProps {
  nodeId?: string;
  computerName?: string;
  online?: boolean;
  variant: "desktop-strip" | "drawer" | "agent-callout";
  initialBrowser?: DesktopBrowserStatus;
  localDesktopTransport?: boolean;
  defaultExpanded?: boolean;
}

/** Shared 2-step Daily Chrome guided pairing widget across Crewden Desktop, Web Computer Drawer, and Agent Tool settings. */
export function BrowserPairingSection({
  nodeId,
  computerName,
  online = true,
  variant,
  initialBrowser,
  localDesktopTransport = false,
  defaultExpanded = false,
}: BrowserPairingSectionProps) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const userId = useAuthStore((s) => s.user?.id);
  const client = useQueryClient();
  const fieldId = useId();

  const [setupOpen, setSetupOpen] = useState(Boolean(defaultExpanded));
  const [browserProfile, setBrowserProfile] = useState("Default");
  const [browserToken, setBrowserToken] = useState("");
  const [browserError, setBrowserError] = useState<string | null>(null);
  const [waitingExtension, setWaitingExtension] = useState(false);
  const [tokenPageOpened, setTokenPageOpened] = useState(false);
  const tokenInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (defaultExpanded) {
      setSetupOpen(true);
    }
  }, [defaultExpanded]);

  const runAction = (input: DesktopBrowserActionInput): Promise<DesktopBrowserActionResponse> => {
    if (localDesktopTransport) {
      return manageDesktopLocalBrowser(input);
    }
    if (!nodeId) {
      return Promise.reject(new Error("Missing nodeId"));
    }
    return manageNodeBrowser(nodeId, input);
  };

  const remoteStatusQuery = useQuery({
    queryKey: ["node-browser", nodeId],
    queryFn: () => manageNodeBrowser(nodeId!, { action: "status" }).then((r) => r.browser),
    enabled: !localDesktopTransport && Boolean(nodeId) && online,
    retry: false,
    staleTime: 15_000,
  });

  const browser = localDesktopTransport ? initialBrowser : (remoteStatusQuery.data ?? initialBrowser);

  const syncBrowserCache = (nextBrowser: DesktopBrowserStatus) => {
    if (localDesktopTransport) {
      client.setQueryData<DesktopLocalInspectResponse>(
        ["desktop", "local-node", userId],
        (prev) => (prev ? { ...prev, browser: nextBrowser } : prev),
      );
    }
    if (nodeId) {
      client.setQueryData<DesktopBrowserStatus>(["node-browser", nodeId], nextBrowser);
    }
  };

  useEffect(() => {
    if (!setupOpen && browser?.selected_profile) {
      setBrowserProfile(browser.selected_profile);
    }
  }, [setupOpen, browser?.selected_profile]);

  useEffect(() => {
    if (!setupOpen || !waitingExtension || (!localDesktopTransport && (!nodeId || !online))) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      void runAction({ action: "status", profile: browserProfile })
        .then(async (res) => {
          if (cancelled) return;
          syncBrowserCache(res.browser);
          if (res.browser.extension_installed) {
            setWaitingExtension(false);
            setTokenPageOpened(true);
            await runAction({ action: "open-guide", profile: browserProfile, target: "token" }).catch(() => {});
            if (!cancelled) tokenInputRef.current?.focus();
          }
        })
        .catch(() => {});
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [browserProfile, localDesktopTransport, nodeId, online, setupOpen, userId, waitingExtension]);

  const browserMutation = useMutation({
    mutationFn: runAction,
    onSuccess: (res, vars) => {
      setBrowserError(null);
      syncBrowserCache(res.browser);
      if (vars.action === "open-guide") {
        if (res.opened === "store") {
          setWaitingExtension(true);
          setTokenPageOpened(false);
        } else {
          setWaitingExtension(false);
          setTokenPageOpened(true);
          window.setTimeout(() => tokenInputRef.current?.focus(), 0);
        }
      } else if (vars.action === "pair") {
        setBrowserToken("");
        setWaitingExtension(false);
        setTokenPageOpened(false);
        setSetupOpen(false);
      } else if (vars.action === "disconnect") {
        setBrowserToken("");
        setWaitingExtension(false);
        setTokenPageOpened(false);
      }
    },
    onError: (err) => {
      setBrowserError(localizeBrowserError(err, zh));
    },
  });

  if (!online && !localDesktopTransport) return null;
  if (!browser || !browser.supported) return null;

  const selectedInstalled =
    browser.profiles.find((p) => p.profile === browserProfile)?.extension_installed ?? browser.extension_installed;
  const isConnected = browser.state === "paired" || browser.state === "verified";
  const chipClass = isConnected ? "online" : browser.state === "reconnect" ? "warn" : "muted";
  const chipLabel =
    browser.state === "verified"
      ? text(`已验证 · ${browser.paired_profile ?? "Default"}`, `Verified · ${browser.paired_profile ?? "Default"}`)
      : browser.state === "paired"
        ? text(`已配对 · ${browser.paired_profile ?? "Default"}`, `Paired · ${browser.paired_profile ?? "Default"}`)
        : browser.state === "reconnect"
          ? text(
              `需重新配对${browser.paired_profile ? ` · ${browser.paired_profile}` : ""}`,
              `Reconnect needed${browser.paired_profile ? ` · ${browser.paired_profile}` : ""}`,
            )
          : text("未配对", "Not paired");

  const targetHostLabel = !localDesktopTransport && computerName ? computerName : null;

  const summaryNote =
    variant === "agent-callout"
      ? isConnected
        ? text(
            "助手可在后台标签页复用该 Chrome 的已登录状态，或按需使用隔离浏览器",
            "Assistant can reuse Chrome sign-ins in background tabs or use an isolated browser",
          )
        : browser.state === "reconnect"
          ? text("日常 Chrome 连接已失效，当前仅能使用干净隔离浏览器", "Daily Chrome needs re-pairing; only the isolated browser is currently available")
          : text("尚未连接日常 Chrome（当前仅可使用干净隔离浏览器）", "Daily Chrome not paired yet (only the clean isolated browser is currently available)")
      : browser.state === "verified"
        ? text("助手可在后台独立标签页复用已登录账号", "Assistants can reuse signed-in sessions in background tabs")
        : browser.state === "paired"
          ? text("将在首次执行日常网页任务时验证连接（免重启生效）", "Verified automatically on the first daily browser task")
          : browser.state === "reconnect"
            ? text("扩展缺失或 Token 已变更，请重新配对", "Extension missing or token changed; pair again")
            : text("配对一次后，助手可在后台标签页复用已登录状态（免重启生效）", "Pair once so assistants reuse your Chrome sign-ins in background tabs");

  const submitPair = () => {
    if (!browserToken.trim() || browserMutation.isPending) return;
    browserMutation.mutate({
      action: "pair",
      profile: browserProfile,
      token: browserToken.trim(),
    });
  };

  const containerClass =
    variant === "desktop-strip"
      ? "local-browser-strip"
      : variant === "drawer"
        ? "browser-pairing-drawer"
        : `browser-pairing-callout ${!isConnected ? "unpaired" : ""}`;

  const containerTestId =
    variant === "desktop-strip"
      ? "desktop-browser-strip"
      : variant === "drawer"
        ? "node-drawer-browser-pairing"
        : "agent-computer-use-browser-callout";

  const setupTestId =
    variant === "desktop-strip"
      ? "desktop-browser-setup"
      : variant === "drawer"
        ? "node-drawer-browser-setup"
        : "agent-browser-setup";

  return (
    <div className={containerClass} data-testid={containerTestId}>
      <div className="browser-pairing-head">
        <div className="browser-pairing-title">
          <strong style={{ fontSize: 13 }}>{text("日常 Chrome 浏览器", "Daily Chrome")}</strong>
          <span className={`browser-pairing-chip ${chipClass}`}>{chipLabel}</span>
          <span style={{ fontSize: 12, color: "var(--im-text-muted, #68736b)" }}>{summaryNote}</span>
        </div>
        <div className="browser-pairing-actions">
          {setupOpen ? (
            <button
              type="button"
              className="browser-pairing-btn"
              disabled={browserMutation.isPending}
              onClick={() => {
                setSetupOpen(false);
                setWaitingExtension(false);
                setTokenPageOpened(false);
                setBrowserError(null);
                setBrowserToken("");
              }}
            >
              {text("收起", "Close")}
            </button>
          ) : isConnected ? (
            <>
              <button
                type="button"
                className="browser-pairing-btn"
                disabled={browserMutation.isPending}
                onClick={() => {
                  setBrowserProfile(browser.paired_profile ?? browser.selected_profile);
                  setBrowserError(null);
                  setBrowserToken("");
                  setWaitingExtension(false);
                  setTokenPageOpened(false);
                  setSetupOpen(true);
                }}
              >
                {text("更换 Token", "Update token")}
              </button>
              {variant !== "agent-callout" && (
                <button
                  type="button"
                  className="browser-pairing-btn subtle"
                  disabled={browserMutation.isPending}
                  onClick={() => browserMutation.mutate({ action: "disconnect" })}
                >
                  {text("断开", "Disconnect")}
                </button>
              )}
            </>
          ) : (
            <button
              type="button"
              className="browser-pairing-btn"
              disabled={browserMutation.isPending}
              onClick={() => {
                setBrowserProfile(browser.paired_profile ?? browser.selected_profile);
                setBrowserError(null);
                setBrowserToken("");
                setWaitingExtension(false);
                setTokenPageOpened(false);
                setSetupOpen(true);
              }}
            >
              {browser.state === "reconnect" ? text("重新配对…", "Re-pair…") : text("连接 Chrome…", "Connect Chrome…")}
            </button>
          )}
        </div>
      </div>

      {setupOpen && (
        <div className="browser-pairing-setup" data-testid={setupTestId}>
          {browser.profiles.length > 1 && (
            <div>
              <label
                htmlFor={`${fieldId}-profile`}
                style={{ display: "block", fontSize: 12.5, fontWeight: 600, marginBottom: 5 }}
              >
                {text("Chrome 配置目录", "Chrome profile")}
              </label>
              <select
                id={`${fieldId}-profile`}
                className="browser-pairing-select"
                value={browserProfile}
                disabled={browserMutation.isPending}
                onChange={(e) => {
                  const nextProfile = e.target.value;
                  setBrowserProfile(nextProfile);
                  setWaitingExtension(false);
                  setTokenPageOpened(false);
                  setBrowserError(null);
                  browserMutation.mutate({ action: "status", profile: nextProfile });
                }}
              >
                {browser.profiles.map((item) => (
                  <option key={item.profile} value={item.profile}>
                    {item.profile}（{item.extension_installed ? text("已装扩展", "Extension installed") : text("未装扩展", "Not installed")}）
                  </option>
                ))}
              </select>
            </div>
          )}

          {!browser.chrome_installed ? (
            <p style={{ margin: 0, fontSize: 12.5, color: "#95601a" }}>
              {text(
                "未在该电脑检测到 Google Chrome。日常登录态复用需要 Chrome 158+；不连接时助手仍可使用独立隔离浏览器。",
                "Google Chrome was not detected on this computer. Install Chrome 158+ to attach your signed-in profile, or keep using the isolated browser.",
              )}
            </p>
          ) : (
            <>
              <div className="browser-pairing-step-row">
                <div style={{ fontSize: 12.5, minWidth: 0, flex: "1 1 220px" }}>
                  {selectedInstalled ? (
                    <span style={{ display: "inline-flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
                      <span className="browser-pairing-chip online">
                        {text("✓ 已安装 Playwright 扩展", "✓ Playwright Extension installed")}
                      </span>
                      <span style={{ color: "var(--im-text-muted, #68736b)" }}>
                        {tokenPageOpened
                          ? targetHostLabel
                            ? text(
                                `已在「${targetHostLabel}」的 Chrome 打开 Token 页，复制后粘贴到下方即可。`,
                                `Opened the token page in Chrome on ${targetHostLabel} — copy and paste it below.`,
                              )
                            : text("已在 Chrome 打开 Token 页面，复制后粘贴到下方即可。", "Opened the token page in Chrome — copy and paste it below.")
                          : targetHostLabel
                            ? text(
                                `点击右侧将在「${targetHostLabel}」屏幕上的 Chrome 打开 Token 页。`,
                                `Opens the extension token page in Chrome on ${targetHostLabel}.`,
                              )
                            : text("点击右侧打开扩展 Token 页并复制。", "Open the extension token page in Chrome and copy the token.")}
                      </span>
                    </span>
                  ) : waitingExtension ? (
                    <span style={{ color: "#95601a" }}>
                      {targetHostLabel
                        ? text(
                            `已在「${targetHostLabel}」的 Chrome 打开官方商店页：请点击「添加至 Chrome → 添加扩展程序」，装好后将自动弹出 Token 页面…`,
                            `Opened Chrome Web Store on ${targetHostLabel}: click 'Add to Chrome → Add extension'; the token page will open automatically once installed…`,
                          )
                        : text(
                            "已在 Chrome 打开官方商店页：请点击「添加至 Chrome → 添加扩展程序」，安装完成后将自动为你弹出 Token 页面…",
                            "Opened Chrome Web Store: click 'Add to Chrome → Add extension'; the token page will open automatically once installed…",
                          )}
                    </span>
                  ) : (
                    <span>
                      {targetHostLabel
                        ? text(
                            `第 1 步：在「${targetHostLabel}」的日常 Chrome 中安装官方 Playwright 扩展（装好后自动跳 Token 页）`,
                            `Step 1: Install the official Playwright Extension in Chrome on ${targetHostLabel} (opens token page automatically once installed)`,
                          )
                        : text(
                            "第 1 步：在日常 Chrome 中安装微软官方 Playwright 扩展（装好后自动跳转 Token 页）",
                            "Step 1: Install the official Playwright Extension in Chrome (opens token page automatically once installed)",
                          )}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className={`browser-pairing-btn ${!selectedInstalled && !waitingExtension ? "primary" : ""}`}
                  disabled={browserMutation.isPending}
                  onClick={() =>
                    browserMutation.mutate({
                      action: "open-guide",
                      profile: browserProfile,
                      target: selectedInstalled ? "token" : "store",
                    })
                  }
                >
                  {selectedInstalled
                    ? tokenPageOpened
                      ? text("重新打开 Token 页", "Reopen token page")
                      : targetHostLabel
                        ? text(`1. 在 ${targetHostLabel} 打开 Token 页`, `1. Open token page on ${targetHostLabel}`)
                        : text("1. 打开 Chrome 复制 Token", "1. Open Chrome token page")
                    : waitingExtension
                      ? text("重新打开商店页", "Reopen Web Store")
                      : targetHostLabel
                        ? text(`1. 去 ${targetHostLabel} 安装扩展`, `1. Install in Chrome on ${targetHostLabel}`)
                        : text("1. 去 Chrome 安装扩展", "1. Install in Chrome")}
                </button>
              </div>

              <div
                className="browser-pairing-token-row"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    submitPair();
                  }
                }}
              >
                <input
                  ref={tokenInputRef}
                  id={`${fieldId}-token`}
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  className="browser-pairing-input"
                  aria-label={text("Playwright 扩展 Token", "Playwright Extension token")}
                  placeholder={text(
                    "第 2 步：粘贴 Token（支持整行 PLAYWRIGHT_MCP_EXTENSION_TOKEN=…）",
                    "Step 2: Paste token (or PLAYWRIGHT_MCP_EXTENSION_TOKEN=… line)",
                  )}
                  value={browserToken}
                  disabled={browserMutation.isPending}
                  onChange={(e) => {
                    setBrowserToken(e.target.value);
                    setBrowserError(null);
                  }}
                />
                <button
                  type="button"
                  className="browser-pairing-btn primary"
                  disabled={browserMutation.isPending || !browserToken.trim()}
                  onClick={submitPair}
                >
                  {browserMutation.isPending ? text("保存中…", "Saving…") : text("保存配对", "Save pairing")}
                </button>
              </div>

              {browser.chrome_running && !browser.chrome_version_ok && (
                <p style={{ margin: 0, fontSize: 12, color: "#95601a" }}>
                  {text(
                    "提示：建议将该电脑上的 Chrome 升级至 158.0.8127.2 或更高版本，以支持连接页完全后台静默打开。",
                    "Tip: Update Chrome to 158.0.8127.2+ so extension connections open silently in the background.",
                  )}
                </p>
              )}
            </>
          )}

          {browserError && (
            <p className="browser-pairing-error" role="alert">
              {browserError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
