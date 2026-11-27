import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "../features/auth/auth-store";
import { useTranslation } from "../i18n";
import { dismissPendingDesktopServerSwitch, getDesktopContext, switchDesktopServer } from "./desktop-api";
import {
  getDesktopBootContext,
  getDesktopImOrigin,
  isDesktopClient,
  type PendingServerSwitch,
} from "./desktop-context";
import "./desktop.css";

/** Global confirmation & security-alert modal for external `crewden-desktop://connect` invocations. */
export function DesktopServerSwitchModal() {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);

  const boot = getDesktopBootContext();
  const [pendingSwitch, setPendingSwitch] = useState<PendingServerSwitch | null>(
    () => boot?.pendingServerSwitch ?? null,
  );
  const [deepLinkError, setDeepLinkError] = useState<string | null>(
    () => boot?.deepLinkError ?? null,
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const refreshContext = useCallback(async () => {
    if (!isDesktopClient()) return;
    try {
      const ctx = await getDesktopContext();
      setPendingSwitch(ctx.pending_server_switch ?? null);
      setDeepLinkError(ctx.deep_link_error ?? null);
      if (window.__CREWDEN_DESKTOP__) {
        window.__CREWDEN_DESKTOP__ = {
          ...window.__CREWDEN_DESKTOP__,
          imOrigin: ctx.im_origin,
          contextEpoch: ctx.context_epoch,
          pendingServerSwitch: ctx.pending_server_switch ?? null,
          deepLinkError: ctx.deep_link_error ?? null,
        };
      }
    } catch {
      // Ignore transient loopback check errors during initial boot.
    }
  }, []);

  useEffect(() => {
    if (!isDesktopClient()) return;
    void refreshContext();
    const onUpdate = () => {
      void refreshContext();
    };
    window.addEventListener("crewden:host-context-updated", onUpdate);
    window.addEventListener("focus", onUpdate);
    return () => {
      window.removeEventListener("crewden:host-context-updated", onUpdate);
      window.removeEventListener("focus", onUpdate);
    };
  }, [refreshContext]);

  if (!isDesktopClient()) return null;

  const currentOrigin = getDesktopImOrigin() ?? "";

  async function dismiss() {
    setBusy(true);
    setActionError(null);
    try {
      await dismissPendingDesktopServerSwitch();
    } catch {
      // Clear local modal state even if host was restarted.
    } finally {
      setPendingSwitch(null);
      setDeepLinkError(null);
      if (window.__CREWDEN_DESKTOP__) {
        window.__CREWDEN_DESKTOP__ = {
          ...window.__CREWDEN_DESKTOP__,
          pendingServerSwitch: null,
          deepLinkError: null,
        };
      }
      setBusy(false);
    }
  }

  async function confirmSwitch() {
    if (!pendingSwitch) return;
    setBusy(true);
    setActionError(null);
    try {
      const updated = await switchDesktopServer(pendingSwitch.target_origin);
      useAuthStore.getState().clear();
      if (window.__CREWDEN_DESKTOP__) {
        window.__CREWDEN_DESKTOP__ = {
          ...window.__CREWDEN_DESKTOP__,
          imOrigin: updated.im_origin,
          contextEpoch: updated.context_epoch,
          pendingServerSwitch: null,
          deepLinkError: null,
        };
      }
      setPendingSwitch(null);
      window.location.assign("/login");
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : text("切换服务失败，请稍后重试", "Could not switch server"),
      );
      setBusy(false);
    }
  }

  if (deepLinkError) {
    return (
      <div className="desktop-bind-overlay" data-testid="desktop-deep-link-error-modal">
        <div className="desktop-bind-card" role="alertdialog" aria-labelledby="desktop-dl-err-title">
          <span className="desktop-chip warn">
            {text("安全保护已拦截", "Blocked for security")}
          </span>
          <h2 id="desktop-dl-err-title">
            {text("已拦截不安全的明文连接请求", "Insecure cleartext connection blocked")}
          </h2>
          <p style={{ fontSize: 13.5, lineHeight: 1.65, color: "var(--im-text-muted)", margin: "8px 0 14px" }}>
            {deepLinkError}
          </p>
          <div className="desktop-switch-compare">
            <div>
              <span>{text("当前保持连接的服务", "Active server (unchanged)")}</span>
              <code>{currentOrigin}</code>
            </div>
          </div>
          <div className="desktop-action-row" style={{ justifyContent: "flex-end", marginTop: 18 }}>
            <button
              type="button"
              className="desktop-btn primary"
              disabled={busy}
              onClick={() => void dismiss()}
            >
              {text("我知道了", "Got it")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!pendingSwitch) return null;

  return (
    <div className="desktop-bind-overlay" data-testid="desktop-server-switch-modal">
      <div className="desktop-bind-card" role="dialog" aria-modal="true" aria-labelledby="desktop-switch-title">
        <span className="desktop-chip">
          {text("外部连接请求", "External connection request")}
        </span>
        <h2 id="desktop-switch-title">
          {text("确认切换连接的 IM 服务？", "Switch connected IM server?")}
        </h2>
        <p style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--im-text-muted)", margin: "6px 0 14px" }}>
          {text(
            "检测到来自浏览器的服务切换请求。切换后将进入新服务的登录页，原服务的本机配置仍会独立保留。",
            "A browser link requested switching to another IM server. Your existing server settings remain saved separately.",
          )}
        </p>

        <div className="desktop-switch-compare">
          <div>
            <span>{text("当前服务", "Current server")}</span>
            <code>{currentOrigin}</code>
          </div>
          <div>
            <span>{text("目标服务", "Target server")}</span>
            <code>{pendingSwitch.target_origin}</code>
          </div>
        </div>

        {pendingSwitch.is_cleartext_http && (
          <div
            className="desktop-server-callout warn"
            role="alert"
            data-testid="desktop-cleartext-http-warning"
            style={{ marginTop: 12, marginBottom: 0 }}
          >
            <strong>{text("未加密的内网 HTTP 连接", "Unencrypted private HTTP connection")}</strong>
            <span style={{ fontSize: 12.5, lineHeight: 1.55, color: "#7a4d12" }}>
              {text(
                "目标地址未使用 HTTPS 加密，仅建议在受信任的内网局域网环境连接，请勿在公共网络下输入账号密码或密钥。",
                "Target uses cleartext HTTP without TLS. Only proceed on a trusted private LAN.",
              )}
            </span>
          </div>
        )}

        {actionError && (
          <p className="node-form-error" role="alert" style={{ marginTop: 10 }}>
            {actionError}
          </p>
        )}

        <div className="desktop-action-row" style={{ justifyContent: "flex-end", marginTop: 18 }}>
          <button
            type="button"
            className="desktop-btn"
            disabled={busy}
            onClick={() => void dismiss()}
          >
            {text("保留原服务", "Keep current server")}
          </button>
          <button
            type="button"
            className="desktop-btn primary"
            disabled={busy}
            onClick={() => void confirmSwitch()}
          >
            {busy ? text("正在切换…", "Switching…") : text("确认切换", "Confirm switch")}
          </button>
        </div>
      </div>
    </div>
  );
}
