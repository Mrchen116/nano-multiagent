import { MacInstallGuide } from "./mac-install-guide";
import { useState } from "react";
import type { DesktopInstall, OnboardingState } from "../features/onboarding/onboarding-api";
import { WindowsInstallPanel } from "../features/onboarding/windows-install";
import { useTranslation } from "../i18n";
import "./desktop.css";

export type ComputerOsChoice = "macos" | "windows" | "linux";
export type ComputerInstallEntry = "desktop" | "headless";

export function detectSuggestedOs(): ComputerOsChoice {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  if (/Windows/i.test(ua)) return "windows";
  if (/Linux/i.test(ua) && !/Android/i.test(ua)) return "linux";
  return "macos";
}

export function hasDesktopInstallAwareness(install?: OnboardingState["install"]): boolean {
  return Boolean(
    install && (install.desktop_darwin_arm64 !== undefined || install.desktop_win32_x64 !== undefined),
  );
}

/** Dual-entry computer connection selector ("下载完整 Desktop 客户端" vs "仅装轻量后台节点"). */
export function DesktopDualInstallPicker({
  install,
  onRecheck,
  onStartDesktopOrWindows,
  renderUnixHeadless,
}: {
  install: OnboardingState["install"];
  onRecheck(): void;
  onStartDesktopOrWindows?(opened: boolean): void;
  renderUnixHeadless(): React.ReactNode;
}) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const [os, setOs] = useState<ComputerOsChoice>(detectSuggestedOs);
  const [entry, setEntry] = useState<ComputerInstallEntry>("desktop");
  const [desktopPhase, setDesktopPhase] = useState<"initial" | "launched">("initial");

  const supportsDesktop = os !== "linux";
  const activeEntry: ComputerInstallEntry = supportsDesktop ? entry : "headless";
  const desktopMaterials: DesktopInstall | null | undefined =
    os === "macos" ? install.desktop_darwin_arm64 : os === "windows" ? install.desktop_win32_x64 : null;

  const downloadLabel =
    os === "macos"
      ? text("下载 Crewden Desktop (Apple Silicon)", "Download Crewden Desktop (Apple Silicon)")
      : text("下载 Crewden Desktop (Windows x64)", "Download Crewden Desktop (Windows x64)");

  return (
    <div className="desktop-picker-root" data-testid="desktop-dual-install-picker">
      <div className="desktop-os-segmented" role="group" aria-label={text("选择电脑系统", "Choose computer OS")}>
        <button
          type="button"
          aria-pressed={os === "macos"}
          onClick={() => {
            setOs("macos");
            setDesktopPhase("initial");
          }}
        >
          macOS
        </button>
        <button
          type="button"
          aria-pressed={os === "windows"}
          onClick={() => {
            setOs("windows");
            setDesktopPhase("initial");
          }}
        >
          Windows 10 / 11 · x64
        </button>
        <button
          type="button"
          aria-pressed={os === "linux"}
          onClick={() => {
            setOs("linux");
            setDesktopPhase("initial");
          }}
        >
          Linux / WSL
        </button>
      </div>

      {supportsDesktop && (
        <div className="desktop-entry-grid" role="group" aria-label={text("选择安装形态", "Choose installation type")}>
          <button
            type="button"
            className="desktop-entry-card"
            aria-pressed={activeEntry === "desktop"}
            onClick={() => setEntry("desktop")}
          >
            <div>
              <span className="desktop-chip">{text("推荐 · 主力桌面工作台", "Recommended · Desktop workspace")}</span>
            </div>
            <strong>{text("下载完整 Desktop 客户端", "Download Crewden Desktop")}</strong>
            <span className="desc">
              {text(
                "自带聊天工作台与本机节点，点开即用并默认开机自启；本机轨迹与工作区文件直读秒开，内置图形化节点配置。",
                "Built-in chat workspace and local node with login autostart, instant local trajectory & workspace file open, and GUI settings.",
              )}
            </span>
          </button>
          <button
            type="button"
            className="desktop-entry-card"
            aria-pressed={activeEntry === "headless"}
            onClick={() => setEntry("headless")}
          >
            <div>
              <span className="desktop-chip muted">{text("仅后台运行", "Background node only")}</span>
            </div>
            <strong>{text("仅装轻量后台节点", "Lightweight background node only")}</strong>
            <span className="desc">
              {text(
                "不在桌面打开独立客户端，仅保持本机节点在后台常驻（支持 Apple Silicon / Intel Mac 与 Windows），继续用网页或手机对话。",
                "Run only the background node without a desktop window (supports Apple Silicon / Intel Mac & Windows) and chat on web or mobile.",
              )}
            </span>
          </button>
        </div>
      )}

      {activeEntry === "desktop" ? (
        !desktopMaterials ? (
          <div className="desktop-action-box" role="status">
            <h3>{text("当前服务暂未发布该系统的 Desktop 安装包", "Desktop installer is not published for this OS yet")}</h3>
            <p>
              {text(
                "可切换到「仅装轻量后台节点」接入这台电脑，或稍后重新检查。",
                "Switch to the lightweight background node to connect this computer, or check again later.",
              )}
            </p>
            <div className="desktop-action-row">
              <button type="button" className="desktop-btn" onClick={() => setEntry("headless")}>
                {text("改用轻量后台节点", "Use lightweight background node")}
              </button>
              <button type="button" className="desktop-btn subtle" onClick={onRecheck}>
                {text("重新检查", "Check again")}
              </button>
            </div>
          </div>
        ) : desktopPhase === "launched" ? (
          <div className="desktop-action-box" aria-live="polite">
            <h3>{text("已在 Crewden Desktop 中发起连接", "Connecting in Crewden Desktop")}</h3>
            <p>
              {text(
                "请在打开的桌面客户端窗口中登录并确认绑定这台电脑；完成后可直接在桌面端继续对话。",
                "Sign in inside the Crewden Desktop window to confirm this computer, then continue right in Desktop or here.",
              )}
            </p>
            <div className="desktop-action-row">
              <a
                className="desktop-btn primary"
                href={desktopMaterials.connect_url}
                onClick={() => onStartDesktopOrWindows?.(true)}
              >
                {text("重新打开 Desktop", "Reopen Desktop")}
              </a>
              <a
                className="desktop-btn"
                href={desktopMaterials.download_url}
                target="_blank"
                rel="noreferrer"
                onClick={() => onStartDesktopOrWindows?.(false)}
              >
                {text("重新下载安装包", "Download installer again")}
              </a>
              {os === "macos" && <MacInstallGuide materials={desktopMaterials} />}
            </div>
          </div>
        ) : (
          <div className="desktop-action-box">
            <h3>{text("安装并打开 Crewden Desktop", "Install and open Crewden Desktop")}</h3>
            <p>
              {os === "macos"
                ? text(
                    "适用于 macOS 15.0 及以上的 Apple Silicon (M 系列) Mac；Intel 芯片 Mac 请选择「仅装轻量后台节点」。无需安装 Node.js 或打开终端，打开后自动准备运行环境并开启登录自启。",
                    "For Apple Silicon (M-series) Macs running macOS 15.0 or later; for Intel Macs choose 'Lightweight background node only'. Zero terminal or Node.js setup required, with automatic login autostart.",
                  )
                : text(
                    "适用于 Windows 10 / 11 (x64) 电脑。无需安装 Node.js 或打开终端，打开后自动准备运行环境并开启登录自启。",
                    "For Windows 10 / 11 (x64) PCs. Zero terminal or Node.js setup required, with automatic login autostart.",
                  )}
            </p>
            <div className="desktop-action-row">
              <a
                className="desktop-btn primary mobile-full"
                href={desktopMaterials.download_url}
                target="_blank"
                rel="noreferrer"
                onClick={() => {
                  onStartDesktopOrWindows?.(false);
                  setDesktopPhase("launched");
                }}
              >
                {downloadLabel}
              </a>
              <a
                className="desktop-btn mobile-full"
                href={desktopMaterials.connect_url}
                onClick={() => {
                  onStartDesktopOrWindows?.(true);
                  setDesktopPhase("launched");
                }}
              >
                {text("已安装，在桌面端打开", "Already installed? Open in Desktop")}
              </a>
              {os === "macos" && <MacInstallGuide materials={desktopMaterials} />}
            </div>
          </div>
        )
      ) : os === "windows" ? (
        <WindowsInstallPanel
          materials={install.windows_x64}
          onStart={onStartDesktopOrWindows}
          onRecheck={onRecheck}
        />
      ) : (
        renderUnixHeadless()
      )}
    </div>
  );
}
