import { useTranslation } from "../i18n";
import { isDesktopClient } from "./desktop-context";
import "./desktop.css";
import { localizeUpdaterError } from "./desktop-update-pill";
import { useDesktopUpdater } from "./use-desktop-updater";

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Top-pinned Crewden Desktop client version & seamless auto-update card on `/settings/nodes`
 * (works identically in pure-chat unbound mode and bound local-node mode).
 */
export function DesktopClientUpdateCard() {
  const desktop = isDesktopClient();
  const updater = useDesktopUpdater();
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);

  if (!desktop || !updater.snapshot) return null;
  const snap = updater.snapshot;
  const isWin = snap.platform === "win32-x64";
  const targetVer = snap.target?.version ?? "";

  let badgeClass = "online";
  let badgeText = updater.manualCheckFeedback
    ? text("✓ 已是最新版本", "✓ Up to date")
    : text("已开启更新守护", "Update protection active");
  if (!snap.auto_update && snap.phase === "idle") {
    badgeClass = "muted";
    badgeText = text("手动检查模式", "Manual updates");
  }
  let description = snap.auto_update
    ? text(
        "已连接当前 IM 服务的桌面发布通道，发现新版本后会在后台静默准备，空闲或重开时平滑换新。",
        "Connected to this server’s desktop release channel. Updates prepare quietly in the background and switch when idle.",
      )
    : text(
        "自动更新已关闭；你可以随时手动点击右侧「检查更新」获取最新版本。",
        "Automatic background updates are off. Click Check for updates anytime.",
      );

  let cta = (
    <button
      type="button"
      className="desktop-btn"
      disabled={updater.checkPending || snap.phase === "checking"}
      data-testid="desktop-client-check-btn"
      onClick={() => void updater.triggerCheck()}
    >
      {updater.checkPending || snap.phase === "checking"
        ? text("正在检查…", "Checking…")
        : text("检查更新", "Check for updates")}
    </button>
  );

  if (updater.remoteRecoveryRequired) {
    badgeClass = "warn";
    badgeText = text("需要重启恢复", "Needs quick restart");
    description = text(
      "上一次本机运行环境换新被中断，聊天记录与本地工作区均已保留，点一下即可重启恢复。",
      "A previous local update was interrupted. Your chats and workspaces are safe—click once to restart and recover.",
    );
    cta = (
      <button
        type="button"
        className="desktop-btn primary"
        disabled={updater.recoverPending}
        data-testid="desktop-client-recover-btn"
        onClick={() => void updater.triggerRecoverLocalNode()}
      >
        {updater.recoverPending
          ? text("正在恢复…", "Recovering…")
          : text("一键重启恢复", "Restart & recover")}
      </button>
    );
  } else if (snap.phase === "up_to_date") {
    badgeClass = "online";
    badgeText = updater.manualCheckFeedback
      ? text("已是最新版本 ✓", "Up to date ✓")
      : snap.just_updated_version
        ? text(`✓ 已换上 v${snap.just_updated_version}`, `✓ Updated to v${snap.just_updated_version}`)
        : text("已是最新版本 ✓", "Up to date ✓");
  } else if (snap.phase === "unpublished") {
    badgeClass = "muted";
    badgeText = text("当前服务暂未提供桌面更新包", "No desktop release published yet");
    description = text(
      "当前连接的 IM 服务尚未放置桌面端更新包，你正在使用的版本可正常聊天与协作。",
      "This IM server has not published a desktop update package yet. Your current version works normally.",
    );
  } else if (snap.phase === "source_mode") {
    badgeClass = "muted";
    badgeText = text("源码开发模式", "Source development mode");
    description = text(
      "当前客户端由本地代码仓直接运行，不会覆盖你的开发目录。",
      "Running directly from a local source checkout; automatic bundle updates are disabled.",
    );
  } else if (snap.phase === "preparing") {
    badgeClass = "butter";
    badgeText = text(`正在静默准备 v${targetVer}…`, `Preparing v${targetVer}…`);
    description = text(
      "正在后台下载并校验新版本文件，不会打断你当前的聊天或助手任务。",
      "Downloading and verifying the new build in the background without interrupting your work.",
    );
    cta = (
      <button
        type="button"
        className="desktop-btn"
        disabled={updater.cancelPending}
        onClick={() => void updater.triggerCancel()}
      >
        {text("取消准备", "Cancel")}
      </button>
    );
  } else if (snap.phase === "available" && snap.mode === "hot_bundle") {
    badgeClass = "butter";
    badgeText = text(`✨ 发现新版本 v${targetVer}`, `✨ New version v${targetVer}`);
    description =
      snap.target?.release_notes ||
      text(
        "点击立即更新即可下载并在数秒内完成平滑换新，保留当前会话与输入草稿。",
        "Click Update now to download and switch in seconds while keeping your chats and drafts.",
      );
    cta = (
      <button
        type="button"
        className="desktop-btn primary"
        disabled={updater.applyPending}
        data-testid="desktop-client-apply-btn"
        onClick={() => void updater.triggerApply()}
      >
        {updater.applyPending ? text("正在准备…", "Preparing…") : text("立即更新", "Update now")}
      </button>
    );
  } else if (snap.phase === "ready_to_switch") {
    badgeClass = "butter";
    badgeText = text(`✨ 新版 v${targetVer} 已就绪`, `✨ v${targetVer} ready to switch`);
    description =
      snap.target?.release_notes ||
      text(
        "新版本已在本地校验就绪，点击秒换新将在几秒内平滑生效，不丢失登录态与草稿。",
        "Verified and ready locally—switch in seconds without losing your session or drafts.",
      );
    cta = (
      <button
        type="button"
        className="desktop-btn primary"
        disabled={updater.applyPending}
        data-testid="desktop-client-switch-btn"
        onClick={() => void updater.triggerApply()}
      >
        {updater.applyPending
          ? text("正在换新…", "Switching…")
          : text("点一下秒换新", "Switch now")}
      </button>
    );
  } else if (snap.phase === "waiting_for_tasks" || snap.phase === "switching") {
    badgeClass = "warn";
    badgeText =
      snap.phase === "switching"
        ? text(`正在切换至 v${targetVer}…`, `Switching to v${targetVer}…`)
        : text("⏳ 等待任务收尾后换新", "⏳ Waiting for tasks to finish");
    description = text(
      `本机助手任务完成后将自动平滑升至 v${targetVer}，不会强行中断正在执行的工作。`,
      `Crewden will switch to v${targetVer} automatically once active tasks finish.`,
    );
    cta =
      snap.phase === "waiting_for_tasks" ? (
        <button
          type="button"
          className="desktop-btn"
          disabled={updater.cancelPending}
          data-testid="desktop-client-cancel-btn"
          onClick={() => void updater.triggerCancel()}
        >
          {text("取消本次换新", "Cancel update")}
        </button>
      ) : (
        <span className="desktop-chip">{text("换新中…", "Switching…")}</span>
      );
  } else if (snap.mode === "installer") {
    badgeClass = "butter";
    badgeText =
      snap.phase === "installer_ready"
        ? text(`🚀 客户端 v${targetVer} 安装包已就绪`, `🚀 Installer v${targetVer} ready`)
        : snap.phase === "downloading_installer"
          ? text(`正在下载客户端 v${targetVer}…`, `Downloading client v${targetVer}…`)
          : text(`🚀 客户端 v${targetVer} 可升级`, `🚀 Client v${targetVer} available`);
    description =
      snap.phase === "installer_ready"
        ? isWin
          ? text(
              "新版安装程序已校验完毕，点击即可自动关闭旧窗口、覆盖安装并重新打开，会话与工作区完整保留。",
              "Verified installer is ready. Click once to smoothly close, upgrade, and reopen Crewden.",
            )
          : text(
              "新版磁盘映像已准备完毕，账号登录态、连接的服务地址与本地工作区全部保留。",
              "Verified disk image is ready. Your account session, server address, and local workspaces are preserved.",
            )
        : text(
            "本次更新包含新版桌面窗口客户端，点击即可从当前受信源安全下载完整安装包平滑升级。",
            "This update includes an upgraded desktop app shell. Download and upgrade directly in one click.",
          );
    cta =
      snap.phase === "downloading_installer" ? (
        <button
          type="button"
          className="desktop-btn"
          disabled={updater.cancelPending}
          onClick={() => void updater.triggerCancel()}
        >
          {text("取消下载", "Cancel")}
        </button>
      ) : (
        <button
          type="button"
          className="desktop-btn primary"
          disabled={updater.applyPending}
          data-testid="desktop-client-installer-btn"
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
      );
  } else if (snap.phase === "failed") {
    badgeClass = "warn";
    badgeText = text("更新未完成 · 原版本正常可用", "Update paused · Current version active");
    description = localizeUpdaterError(snap.error_code, zh);
    cta = (
      <button
        type="button"
        className="desktop-btn primary"
        disabled={updater.checkPending}
        data-testid="desktop-client-retry-btn"
        onClick={() => void updater.triggerCheck()}
      >
        {text("重试更新", "Retry update")}
      </button>
    );
  }

  const progressPct =
    snap.progress?.total_bytes && snap.progress.total_bytes > 0
      ? Math.min(100, Math.round((snap.progress.downloaded_bytes * 100) / snap.progress.total_bytes))
      : null;

  return (
    <section
      className="desktop-client-update-card"
      aria-label={text("Crewden 桌面端更新", "Crewden Desktop updates")}
      data-testid="desktop-client-update-card"
    >
      <div className="desktop-client-update-main">
        <div style={{ flex: "1 1 280px", minWidth: 0 }}>
          <div className="desktop-client-update-title">
            <h2>{text("Crewden 桌面端", "Crewden Desktop")}</h2>
            <span className="desktop-chip">v{snap.current_version}</span>
            <span className={`desktop-chip ${badgeClass}`}>{badgeText}</span>
          </div>
          <p className="desktop-client-update-desc">{description}</p>
          {(snap.phase === "preparing" || snap.phase === "downloading_installer") && snap.progress && (
            <div className="desktop-update-progress-wrap" style={{ maxWidth: 380 }}>
              <div className="desktop-update-progress-bar">
                <div style={{ width: `${progressPct ?? 35}%` }} />
              </div>
              <span className="desktop-update-progress-meta">
                {formatBytes(snap.progress.downloaded_bytes)}
                {snap.progress.total_bytes ? ` / ${formatBytes(snap.progress.total_bytes)}` : ""}
              </span>
            </div>
          )}
          {snap.mode === "installer" && snap.phase === "installer_ready" && !isWin && (
            <div className="desktop-mac-dmg-steps" style={{ marginTop: 10 }}>
              {text(
                "将弹出窗口中的 Crewden 拖入 Applications 替换后重开即可",
                "Drag Crewden into Applications in the opened window to replace, then reopen",
              )}
              {snap.target?.macos_distribution !== "developer-id-notarized"
                ? text(
                    "；首次打开若提示未验证开发者，在「系统设置 → 隐私与安全性」点击「仍要打开」。",
                    "; if macOS prompts on first launch, click Open Anyway in System Settings → Privacy & Security.",
                  )
                : text("。", ".")}
            </div>
          )}
        </div>
        <div className="desktop-action-row">{cta}</div>
      </div>

      <div className="desktop-client-auto-strip">
        <div>
          <strong style={{ fontSize: 13 }}>{text("自动保持最新", "Keep Crewden up to date")}</strong>
          <span style={{ fontSize: 12, color: "var(--im-text-muted)", marginLeft: 8 }}>
            {text(
              "发现新版本后静默准备，窗口收进后台空闲或下次打开时无感换新",
              "Silently prepare new releases and apply them when hidden in tray or on next launch",
            )}
          </span>
        </div>
        <button
          type="button"
          className="desktop-switch"
          role="switch"
          aria-label={text("自动保持最新", "Keep Crewden up to date")}
          aria-checked={snap.auto_update}
          disabled={updater.prefsPending}
          data-testid="desktop-client-auto-switch"
          onClick={() => void updater.triggerToggleAutoUpdate(!snap.auto_update)}
        >
          <i />
        </button>
      </div>
    </section>
  );
}
