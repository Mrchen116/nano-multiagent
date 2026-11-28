import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "../i18n";
import { isDesktopClient } from "./desktop-context";
import "./desktop.css";
import {
  useDesktopUpdater,
  useDesktopUserMenuOpen,
  type MergedDesktopUpdaterView,
} from "./use-desktop-updater";

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function splitReleaseNotes(raw?: string | null): string[] {
  if (!raw) return [];
  return raw
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-*•]\s*/, "").trim())
    .filter(Boolean)
    .slice(0, 4);
}

export function localizeUpdaterError(errorCode: string | null | undefined, zh: boolean): string {
  switch (errorCode) {
    case "switch_rolled_back":
      return zh
        ? "新版本启动未就绪，已自动恢复到原可用版本，你的会话与工作区完好无损。"
        : "The new build could not finish starting, so Crewden restored your working version automatically.";
    case "verification_failed":
      return zh
        ? "下载包完整性核验未通过，当前版本不受影响，点一下重试即可。"
        : "The update package did not pass verification. Your current version is unaffected—tap Retry.";
    case "disk_or_unpack_failed":
      return zh
        ? "准备更新文件时遇到本机存储异常，当前版本可照常使用。"
        : "Could not unpack update files on disk. Your current version keeps working normally.";
    default:
      return zh
        ? "暂时连不上更新源，当前版本可照常使用。"
        : "Could not reach the update source right now. Your current version keeps working normally.";
  }
}

/** Bottom-left rail spark badge + non-blocking 248px popover card (`>= 768px` Desktop shell). */
export function DesktopRailUpdatePill() {
  const desktop = isDesktopClient();
  const updater = useDesktopUpdater();
  const menuOpen = useDesktopUserMenuOpen();
  const location = useLocation();
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const [notesOpen, setNotesOpen] = useState(false);

  if (!desktop || !updater.snapshot) return null;
  const snap = updater.snapshot;
  const isWin = snap.platform === "win32-x64";
  const onNodesPage = location.pathname.startsWith("/settings/nodes");

  const hasReadyHot = snap.phase === "ready_to_switch" && snap.mode === "hot_bundle";
  const hasWaiting = snap.phase === "waiting_for_tasks" || snap.phase === "switching";
  const hasInstaller =
    snap.mode === "installer" &&
    (snap.phase === "available" ||
      snap.phase === "downloading_installer" ||
      snap.phase === "installer_ready");
  const hasRolledBack = snap.phase === "failed" && snap.error_code === "switch_rolled_back";
  const hasJustUpdated = Boolean(snap.just_updated_version) && snap.phase === "up_to_date";

  const showTrigger = hasReadyHot || hasWaiting || hasInstaller || hasRolledBack || hasJustUpdated;
  if (!showTrigger) return null;

  const targetVer = snap.target?.version ?? "";
  const isDismissed = snap.capsule_dismissed && (hasReadyHot || hasInstaller);
  const suppressCard = menuOpen || onNodesPage || isDismissed;

  const notes = splitReleaseNotes(snap.target?.release_notes);
  const needsGatekeeperHint =
    !isWin && snap.target?.macos_distribution !== "developer-id-notarized";

  const progressPct =
    snap.progress?.total_bytes && snap.progress.total_bytes > 0
      ? Math.min(100, Math.round((snap.progress.downloaded_bytes * 100) / snap.progress.total_bytes))
      : null;

  return (
    <div className="desktop-rail-update-anchor" data-testid="desktop-rail-update-anchor">
      <button
        type="button"
        className={`desktop-rail-update-pill${hasJustUpdated ? " mint" : ""}`}
        data-testid="desktop-rail-update-trigger"
        onClick={() => {
          if (hasJustUpdated) {
            void updater.triggerDismiss("just_updated");
            return;
          }
          if (onNodesPage) {
            document
              .querySelector('[data-testid="desktop-client-update-card"]')
              ?.scrollIntoView?.({ behavior: "smooth", block: "start" });
            return;
          }
          if (isDismissed) {
            void updater.triggerDismiss("reopen_capsule");
            return;
          }
          if (hasReadyHot) {
            void updater.triggerApply();
          } else if (snap.phase === "installer_ready") {
            void updater.triggerOpenInstaller();
          } else if (hasInstaller && snap.phase === "available") {
            void updater.triggerApply();
          }
        }}
      >
        {hasJustUpdated ? (
          <>
            <span>✓ {text("已换新", "Updated")}</span>
            <span>v{snap.just_updated_version}</span>
          </>
        ) : (
          <>
            <span className="spark">✨ {text("新版", "New")}</span>
            <span>v{targetVer || snap.current_version}</span>
          </>
        )}
      </button>

      {!suppressCard && hasJustUpdated && (
        <section
          className="desktop-update-capsule-card"
          role="status"
          data-testid="desktop-capsule-just-updated"
        >
          <div className="desktop-capsule-head">
            <span className="desktop-capsule-badge mint">
              ✓ {text(`已换上 v${snap.just_updated_version}`, `Now on v${snap.just_updated_version}`)}
            </span>
            <button
              type="button"
              className="desktop-capsule-close"
              aria-label={text("收起", "Dismiss")}
              onClick={() => void updater.triggerDismiss("just_updated")}
            >
              ×
            </button>
          </div>
          <p className="desktop-capsule-title">
            {text("换新完成，一切都在原位", "All fresh—right where you left off")}
          </p>
          <p className="desktop-capsule-copy">
            {text(
              "刚才所在的会话、未发送草稿与登录状态均完整保留。",
              "Your active chat, unsent draft, and session were all preserved.",
            )}
          </p>
        </section>
      )}

      {!suppressCard && hasReadyHot && (
        <section
          className="desktop-update-capsule-card"
          role="region"
          aria-label={text("新版本已准备就绪", "Update ready")}
          data-testid="desktop-capsule-ready"
        >
          <div className="desktop-capsule-head">
            <span className="desktop-capsule-badge">
              ✨ {text(`新版 v${targetVer} 已备好`, `v${targetVer} is ready`)}
            </span>
            <button
              type="button"
              className="desktop-capsule-close"
              aria-label={text("稍后换新", "Later")}
              onClick={() => {
                void updater.triggerDismiss("capsule");
              }}
            >
              ×
            </button>
          </div>
          <p className="desktop-capsule-title">
            {text("点一下几秒换新", "Switch in seconds")}
          </p>
          <p className="desktop-capsule-copy">
            {text(
              "正在聊的会话与输入框草稿都会原样保留。",
              "Your open chat and composer draft stay intact.",
            )}
          </p>
          {notes.length > 0 && (
            <>
              <button
                type="button"
                className="desktop-capsule-notes-toggle"
                onClick={() => setNotesOpen((v) => !v)}
              >
                {notesOpen
                  ? text("收起更新亮点 ▴", "Hide highlights ▴")
                  : text("看看更新了什么 ▾", "See what’s new ▾")}
              </button>
              {notesOpen && (
                <div className="desktop-capsule-notes-box">
                  <ul>
                    {notes.map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
          <div className="desktop-capsule-actions">
            <button
              type="button"
              className="desktop-btn-spark"
              disabled={updater.applyPending}
              data-testid="desktop-capsule-switch-now"
              onClick={() => void updater.triggerApply()}
            >
              {updater.applyPending
                ? text("正在换新…", "Switching…")
                : text("点一下秒换新", "Switch now")}
            </button>
            <button
              type="button"
              className="desktop-btn compact"
              onClick={() => {
                void updater.triggerDismiss("capsule");
              }}
            >
              {text("稍后", "Later")}
            </button>
          </div>
        </section>
      )}

      {!suppressCard && hasWaiting && (
        <section
          className="desktop-update-capsule-card"
          role="status"
          data-testid="desktop-capsule-waiting"
        >
          <div className="desktop-capsule-head">
            <span className="desktop-capsule-badge amber">
              ⏳ {snap.phase === "switching" ? text("正在平滑换新", "Switching now") : text("等待任务收尾", "Waiting for tasks")}
            </span>
          </div>
          <p className="desktop-capsule-title">
            {snap.phase === "switching"
              ? text(`正在切换至 v${targetVer}…`, `Switching to v${targetVer}…`)
              : text("当前任务跑完就自动换新", "Will switch right after active work")}
          </p>
          <p className="desktop-capsule-copy">
            {text(
              "不会中断正在工作的助手，切换开始前随时可取消。",
              "Active assistant tasks are never interrupted.",
            )}
          </p>
          {snap.phase === "waiting_for_tasks" && (
            <div className="desktop-capsule-actions">
              <button
                type="button"
                className="desktop-btn compact"
                style={{ width: "100%" }}
                disabled={updater.cancelPending}
                onClick={() => void updater.triggerCancel()}
              >
                {text("取消本次换新", "Cancel update")}
              </button>
            </div>
          )}
        </section>
      )}

      {!suppressCard && hasInstaller && (
        <section
          className="desktop-update-capsule-card"
          role="region"
          aria-label={text("桌面客户端升级", "Desktop client upgrade")}
          data-testid="desktop-capsule-installer"
        >
          <div className="desktop-capsule-head">
            <span className="desktop-capsule-badge">
              🚀 {text(`客户端 v${targetVer}`, `App v${targetVer}`)}
            </span>
            {snap.phase !== "downloading_installer" && (
              <button
                type="button"
                className="desktop-capsule-close"
                aria-label={text("稍后", "Later")}
                onClick={() => {
                void updater.triggerDismiss("capsule");
              }}
              >
                ×
              </button>
            )}
          </div>
          <p className="desktop-capsule-title">
            {snap.phase === "installer_ready"
              ? text("新版安装包已就绪", "Installer is ready")
              : snap.phase === "downloading_installer"
                ? text("正在准备新版客户端…", "Downloading update…")
                : text("升级新版桌面客户端", "Upgrade Crewden Desktop")}
          </p>
          <p className="desktop-capsule-copy">
            {snap.phase === "installer_ready"
              ? isWin
                ? text(
                    "点一下即可自动关闭旧窗口、覆盖升级并重新打开。",
                    "Click once to smoothly close, upgrade, and reopen Crewden.",
                  )
                : text(
                    "新版磁盘映像已准备妥当，账号与本地工作区全部保留。",
                    "Disk image verified—your account and workspaces stay intact.",
                  )
              : text(
                  "从当前服务受信源安全下载，登录会话与工作区完整保留。",
                  "Downloaded securely from your server’s trusted release feed.",
                )}
          </p>
          {snap.phase === "downloading_installer" && (
            <div className="desktop-update-progress-wrap" data-testid="desktop-installer-progress">
              <div className="desktop-update-progress-bar">
                <div style={{ width: `${progressPct ?? 35}%` }} />
              </div>
              <span className="desktop-update-progress-meta">
                {snap.progress
                  ? `${formatBytes(snap.progress.downloaded_bytes)}${snap.progress.total_bytes ? ` / ${formatBytes(snap.progress.total_bytes)}` : ""}`
                  : text("正在核验…", "Verifying…")}
              </span>
            </div>
          )}
          {snap.phase === "installer_ready" && !isWin && (
            <div className="desktop-mac-dmg-steps" data-testid="desktop-mac-dmg-guide">
              1. {text("将弹出窗口中的 Crewden 拖入 Applications 替换后重开。", "Drag Crewden into Applications to replace, then reopen.")}
              {needsGatekeeperHint && (
                <>
                  <br />
                  2. {text(
                    "首次打开若提示未验证开发者，在「系统设置 → 隐私与安全性」点「仍要打开」即可。",
                    "If macOS asks to verify, click Open Anyway in System Settings → Privacy & Security.",
                  )}
                </>
              )}
            </div>
          )}
          <div className="desktop-capsule-actions">
            {snap.phase === "downloading_installer" ? (
              <button
                type="button"
                className="desktop-btn compact"
                style={{ width: "100%" }}
                disabled={updater.cancelPending}
                onClick={() => void updater.triggerCancel()}
              >
                {text("取消下载", "Cancel")}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="desktop-btn-spark"
                  disabled={updater.applyPending}
                  data-testid="desktop-capsule-installer-cta"
                  onClick={() =>
                    void (snap.phase === "installer_ready"
                      ? updater.triggerOpenInstaller()
                      : updater.triggerApply())
                  }
                >
                  {snap.phase === "installer_ready"
                    ? isWin
                      ? text("立即覆盖升级", "Install & restart")
                      : text("打开新版映像", "Open disk image")
                    : text("下载并升级客户端", "Download & upgrade")}
                </button>
                <button
                  type="button"
                  className="desktop-btn compact"
                  onClick={() => {
                void updater.triggerDismiss("capsule");
              }}
                >
                  {text("稍后", "Later")}
                </button>
              </>
            )}
          </div>
        </section>
      )}

      {!suppressCard && hasRolledBack && (
        <section
          className="desktop-update-capsule-card"
          role="alert"
          data-testid="desktop-capsule-rolled-back"
        >
          <div className="desktop-capsule-head">
            <span className="desktop-capsule-badge amber">
              {text("已恢复原版本", "Restored working version")}
            </span>
          </div>
          <p className="desktop-capsule-copy" style={{ marginTop: 6 }}>
            {localizeUpdaterError(snap.error_code, zh)}
          </p>
          <div className="desktop-capsule-actions">
            <button
              type="button"
              className="desktop-btn compact"
              style={{ width: "100%" }}
              onClick={() => void updater.triggerCheck()}
            >
              {text("重新检查", "Retry check")}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

/** Slim in-flow top banner for narrow (`< 768px`) Desktop windows so neither messages nor composer are covered. */
export function DesktopNarrowUpdateBanner() {
  const desktop = isDesktopClient();
  const updater = useDesktopUpdater();
  const location = useLocation();
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);

  if (!desktop || !updater.snapshot) return null;
  if (location.pathname.startsWith("/settings/nodes") || location.pathname === "/me") return null;

  const snap = updater.snapshot;
  const isWin = snap.platform === "win32-x64";
  const targetVer = snap.target?.version ?? "";

  if (snap.just_updated_version && snap.phase === "up_to_date") {
    return (
      <div className="desktop-narrow-update-bar" role="status" data-testid="desktop-narrow-updated">
        <span className="desktop-narrow-success">
          ✓ {text(`已换上 v${snap.just_updated_version}，草稿已保留`, `Updated to v${snap.just_updated_version} · draft kept`)}
        </span>
        <button
          type="button"
          className="desktop-capsule-close"
          aria-label={text("收起", "Dismiss")}
          onClick={() => void updater.triggerDismiss("just_updated")}
        >
          ×
        </button>
      </div>
    );
  }

  if (snap.capsule_dismissed && (snap.phase === "ready_to_switch" || snap.phase === "available")) {
    return null;
  }

  if (snap.phase === "ready_to_switch" && snap.mode === "hot_bundle") {
    return (
      <div className="desktop-narrow-update-bar" data-testid="desktop-narrow-ready">
        <div className="desktop-narrow-copy">
          <strong>✨ {text(`新版 v${targetVer} 已备好`, `v${targetVer} is ready`)}</strong>
          <span>{text("点一下几秒换新，不丢草稿", "Switch in seconds · keeps draft")}</span>
        </div>
        <div className="desktop-narrow-actions">
          <button
            type="button"
            className="desktop-btn-spark compact"
            disabled={updater.applyPending}
            onClick={() => void updater.triggerApply()}
          >
            {text("秒换新", "Switch")}
          </button>
          <button
            type="button"
            className="desktop-capsule-close"
            aria-label={text("稍后", "Later")}
            onClick={() => void updater.triggerDismiss("capsule")}
          >
            ×
          </button>
        </div>
      </div>
    );
  }

  if (snap.phase === "waiting_for_tasks" || snap.phase === "switching") {
    return (
      <div className="desktop-narrow-update-bar" role="status" data-testid="desktop-narrow-waiting">
        <div className="desktop-narrow-copy">
          <strong style={{ color: "#95601a" }}>
            ⏳ {snap.phase === "switching" ? text("正在平滑换新…", "Switching…") : text("等待当前任务收尾", "Waiting for active task")}
          </strong>
          <span>{text(`跑完后自动换上 v${targetVer}`, `Auto-switches to v${targetVer} when done`)}</span>
        </div>
        {snap.phase === "waiting_for_tasks" && (
          <button
            type="button"
            className="desktop-btn compact"
            disabled={updater.cancelPending}
            onClick={() => void updater.triggerCancel()}
          >
            {text("取消换新", "Cancel")}
          </button>
        )}
      </div>
    );
  }

  if (
    snap.mode === "installer" &&
    (snap.phase === "available" ||
      snap.phase === "downloading_installer" ||
      snap.phase === "installer_ready")
  ) {
    return (
      <div className="desktop-narrow-update-bar" data-testid="desktop-narrow-installer">
        <div className="desktop-narrow-copy">
          <strong>
            🚀 {text(`客户端 v${targetVer}`, `App v${targetVer}`)}{" "}
            {snap.phase === "installer_ready"
              ? text("安装包已就绪", "ready")
              : snap.phase === "downloading_installer"
                ? text("下载中…", "downloading…")
                : text("可升级", "available")}
          </strong>
          <span>
            {snap.phase === "installer_ready"
              ? isWin
                ? text("点一下覆盖安装并重开", "Click to install & reopen")
                : text("拖入 Applications 替换即可", "Drag into Applications")
              : text("账号与本地工作区完整保留", "Keeps account & workspaces")}
          </span>
        </div>
        <div className="desktop-narrow-actions">
          {snap.phase === "downloading_installer" ? (
            <button
              type="button"
              className="desktop-btn compact"
              onClick={() => void updater.triggerCancel()}
            >
              {text("取消", "Cancel")}
            </button>
          ) : (
            <button
              type="button"
              className="desktop-btn-spark compact"
              onClick={() =>
                void (snap.phase === "installer_ready"
                  ? updater.triggerOpenInstaller()
                  : updater.triggerApply())
              }
            >
              {snap.phase === "installer_ready"
                ? isWin
                  ? text("覆盖升级", "Install")
                  : text("打开映像", "Open DMG")
                : text("下载升级", "Upgrade")}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (snap.phase === "failed") {
    return (
      <div className="desktop-narrow-update-bar" role="alert" data-testid="desktop-narrow-failed">
        <div className="desktop-narrow-copy">
          <strong style={{ color: "#95601a" }}>{text("更新暂未完成", "Update paused")}</strong>
          <span>{text(`当前 v${snap.current_version} 可照常使用`, `v${snap.current_version} works normally`)}</span>
        </div>
        <button
          type="button"
          className="desktop-btn compact"
          onClick={() => void updater.triggerCheck()}
        >
          {text("重试", "Retry")}
        </button>
      </div>
    );
  }

  return null;
}

/** Shared compact update box embedded inside `UserMenu` (`>= 768px`) and `MePage` (`< 768px` `/me`). */
export function DesktopCompactUpdateBox({
  updater: externalUpdater,
  testId = "desktop-compact-update-box",
}: {
  updater?: MergedDesktopUpdaterView;
  testId?: string;
}) {
  const internalUpdater = useDesktopUpdater();
  const updater = externalUpdater ?? internalUpdater;
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);

  if (!isDesktopClient() || !updater.snapshot) return null;
  const snap = updater.snapshot;
  const isWin = snap.platform === "win32-x64";
  const targetVer = snap.target?.version ?? "";
  const isHighlight = snap.phase === "ready_to_switch" || snap.mode === "installer";

  let statusLabel = text(
    `当前 v${snap.current_version}${updater.manualCheckFeedback ? " · 已是最新版本 ✓" : ""}`,
    `Version v${snap.current_version}${updater.manualCheckFeedback ? " · Up to date ✓" : ""}`,
  );
  let subLabel = text("聊天草稿与本机数据保留", "Drafts & local workspaces preserved");
  let actionNode = (
    <button
      type="button"
      className="desktop-um-mini-btn"
      disabled={updater.checkPending || snap.phase === "checking"}
      data-testid={`${testId}-check`}
      onClick={() => void updater.triggerCheck()}
    >
      {updater.checkPending || snap.phase === "checking"
        ? text("检查中…", "Checking…")
        : text("检查更新", "Check")}
    </button>
  );

  if (updater.remoteRecoveryRequired) {
    statusLabel = text("上次换新被中断", "Previous update interrupted");
    subLabel = text("点一下重启本机运行环境即可恢复", "Restart local runtime to recover");
    actionNode = (
      <button
        type="button"
        className="desktop-um-mini-btn primary"
        disabled={updater.recoverPending}
        onClick={() => void updater.triggerRecoverLocalNode()}
      >
        {text("一键恢复", "Recover")}
      </button>
    );
  } else if (snap.phase === "unpublished") {
    statusLabel = text(`当前 v${snap.current_version}`, `Version v${snap.current_version}`);
    subLabel = text("当前服务暂未提供桌面更新包", "No desktop package published on this server");
  } else if (snap.phase === "source_mode") {
    statusLabel = text("开发源码运行中", "Running from source");
    subLabel = text("开发工作区不会被自动覆盖", "Source checkout is never overwritten");
  } else if (snap.phase === "preparing") {
    statusLabel = text(`正在后台准备 v${targetVer}…`, `Preparing v${targetVer}…`);
    subLabel = text("不会打断当前输入与任务", "Runs quietly in the background");
    actionNode = (
      <button
        type="button"
        className="desktop-um-mini-btn"
        disabled={updater.cancelPending}
        onClick={() => void updater.triggerCancel()}
      >
        {text("取消", "Cancel")}
      </button>
    );
  } else if (snap.phase === "available" && snap.mode === "hot_bundle") {
    statusLabel = text(`发现新版本 v${targetVer}`, `New version v${targetVer}`);
    actionNode = (
      <button
        type="button"
        className="desktop-um-mini-btn primary"
        disabled={updater.applyPending}
        onClick={() => void updater.triggerApply()}
      >
        {text("立即更新", "Update")}
      </button>
    );
  } else if (snap.phase === "ready_to_switch") {
    statusLabel = text(`新版 v${targetVer} 已备好`, `v${targetVer} ready to switch`);
    actionNode = (
      <button
        type="button"
        className="desktop-um-mini-btn primary"
        disabled={updater.applyPending}
        data-testid={`${testId}-switch`}
        onClick={() => void updater.triggerApply()}
      >
        {text("秒换新", "Switch now")}
      </button>
    );
  } else if (snap.phase === "waiting_for_tasks" || snap.phase === "switching") {
    statusLabel =
      snap.phase === "switching"
        ? text(`正在切换至 v${targetVer}…`, `Switching to v${targetVer}…`)
        : text("等待任务收尾后换新", "Waiting for active tasks");
    subLabel = text(`跑完当前任务自动升至 v${targetVer}`, `Switches to v${targetVer} when idle`);
    actionNode =
      snap.phase === "waiting_for_tasks" ? (
        <button
          type="button"
          className="desktop-um-mini-btn"
          disabled={updater.cancelPending}
          onClick={() => void updater.triggerCancel()}
        >
          {text("取消", "Cancel")}
        </button>
      ) : (
        <span style={{ fontSize: 11.5, color: "var(--im-accent)" }}>…</span>
      );
  } else if (snap.mode === "installer") {
    if (snap.phase === "downloading_installer") {
      statusLabel = text(`正在下载客户端 v${targetVer}…`, `Downloading v${targetVer}…`);
      subLabel = snap.progress
        ? `${formatBytes(snap.progress.downloaded_bytes)}${snap.progress.total_bytes ? ` / ${formatBytes(snap.progress.total_bytes)}` : ""}`
        : text("正在核验安装包…", "Verifying installer…");
      actionNode = (
        <button
          type="button"
          className="desktop-um-mini-btn"
          onClick={() => void updater.triggerCancel()}
        >
          {text("取消", "Cancel")}
        </button>
      );
    } else if (snap.phase === "installer_ready") {
      statusLabel = text(`客户端 v${targetVer} 安装包已就绪`, `Installer v${targetVer} ready`);
      subLabel = isWin
        ? text("一键关闭旧窗口覆盖升级", "Smoothly upgrades and reopens")
        : text("已下载校验新版磁盘映像", "Verified disk image ready");
      actionNode = (
        <button
          type="button"
          className="desktop-um-mini-btn primary"
          onClick={() => void updater.triggerOpenInstaller()}
        >
          {isWin ? text("立即安装", "Install") : text("打开映像", "Open DMG")}
        </button>
      );
    } else {
      statusLabel = text(`新版客户端 v${targetVer} 可升级`, `Client v${targetVer} available`);
      subLabel = text("安全下载安装包，工作区保留", "Keeps your session & workspaces");
      actionNode = (
        <button
          type="button"
          className="desktop-um-mini-btn primary"
          onClick={() => void updater.triggerApply()}
        >
          {text("升级客户端", "Upgrade")}
        </button>
      );
    }
  } else if (snap.phase === "failed") {
    statusLabel = text("更新暂未完成", "Update incomplete");
    subLabel = localizeUpdaterError(snap.error_code, zh);
    actionNode = (
      <button
        type="button"
        className="desktop-um-mini-btn"
        data-testid={`${testId}-retry`}
        onClick={() => void updater.triggerCheck()}
      >
        {text("重试", "Retry")}
      </button>
    );
  }

  return (
    <div className={`desktop-um-update-box${isHighlight ? " ready" : ""}`} data-testid={testId}>
      <div className="desktop-um-update-top">
        <div style={{ minWidth: 0 }}>
          <strong className="desktop-um-status-title">{statusLabel}</strong>
          <span className="desktop-um-status-sub">{subLabel}</span>
        </div>
        {actionNode}
      </div>
      {snap.mode === "installer" && snap.phase === "installer_ready" && !isWin && (
        <div className="desktop-mac-dmg-steps">
          {text("拖入 Applications 替换即可", "Drag into Applications to replace")}
          {snap.target?.macos_distribution !== "developer-id-notarized"
            ? text(
                "；首次打开若受阻可在「隐私与安全性」点「仍要打开」。",
                "; if prompted on first launch, click Open Anyway in Privacy & Security.",
              )
            : text("。", ".")}
        </div>
      )}
      <div className="desktop-um-auto-row">
        <span>{text("自动保持最新", "Keep Crewden up to date")}</span>
        <button
          type="button"
          className="desktop-switch"
          role="switch"
          aria-label={text("自动保持最新", "Keep Crewden up to date")}
          aria-checked={snap.auto_update}
          disabled={updater.prefsPending}
          data-testid={`${testId}-auto-switch`}
          onClick={() => void updater.triggerToggleAutoUpdate(!snap.auto_update)}
        >
          <i />
        </button>
      </div>
    </div>
  );
}
