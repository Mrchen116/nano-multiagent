import { useState } from "react";
import { useAuthStore } from "../features/auth/auth-store";
import { useTranslation } from "../i18n";
import { switchDesktopServer } from "./desktop-api";
import { classifyDesktopImOrigin, getDesktopImOrigin, isDesktopClient } from "./desktop-context";
import "./desktop.css";

/** Inline server-origin switcher rendered inside Login/Register cards on Crewden Desktop. */
export function DesktopServerBar() {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const currentOrigin = getDesktopImOrigin();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(currentOrigin ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isDesktopClient() || !currentOrigin) return null;

  const currentSecurity = classifyDesktopImOrigin(currentOrigin);
  const draftSecurity = classifyDesktopImOrigin(draft);

  async function save() {
    const trimmed = draft.trim().replace(/\/+$/, "");
    if (!trimmed) {
      setError(text("请输入有效的 IM 服务地址", "Enter a valid IM server URL"));
      return;
    }
    const check = classifyDesktopImOrigin(trimmed);
    if (check.kind === "rejected_public_http") {
      setError(
        text(
          "官方与公网 IM 服务必须使用 https:// 加密连接（仅本机回环或局域网私有地址允许 http://）",
          "Official and public IM servers require https:// (http:// is allowed only for loopback or private LAN)",
        ),
      );
      return;
    }
    if (check.kind === "invalid" || !check.normalizedOrigin) {
      setError(
        text(
          "请输入不含子路径或查询参数的完整 http(s):// 服务根地址（例如 https://im.example.com）",
          "Enter a valid scheme://host[:port] server origin without path or query",
        ),
      );
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await switchDesktopServer(check.normalizedOrigin);
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
      window.location.assign("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : text("无法切换服务地址", "Could not switch server address"));
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="desktop-server-callout" data-testid="desktop-server-editor">
        <div className="desktop-server-editor-head">
          <strong>{text("连接到的 IM 服务地址", "Target IM server address")}</strong>
          <div className="desktop-action-row">
            <button
              type="button"
              className="desktop-btn compact"
              disabled={saving}
              onClick={() => {
                setDraft(currentOrigin);
                setError(null);
                setEditing(false);
              }}
            >
              {text("取消", "Cancel")}
            </button>
            <button type="button" className="desktop-btn primary compact" disabled={saving} onClick={() => void save()}>
              {saving ? text("正在切换…", "Switching…") : text("保存切换", "Save & switch")}
            </button>
          </div>
        </div>
        <div className="local-field" style={{ margin: "8px 0 0" }}>
          <input
            className="desktop-text-input"
            value={draft}
            aria-label={text("IM 服务地址", "IM server address")}
            placeholder="https://im.crewden.work"
            disabled={saving}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void save();
              } else if (e.key === "Escape" && !saving) {
                setDraft(currentOrigin);
                setError(null);
                setEditing(false);
              }
            }}
            onChange={(e) => {
              setDraft(e.target.value);
              setError(null);
            }}
          />
        </div>
        {draftSecurity.kind === "private_http" && !error && (
          <p className="desktop-private-http-hint" data-testid="desktop-private-http-hint">
            {text(
              "内网 HTTP 未加密传输，仅建议在可信局域网环境连接。",
              "Unencrypted private LAN HTTP — use only on a trusted local network.",
            )}
          </p>
        )}
        {error && (
          <p className="node-form-error" role="alert" style={{ margin: "8px 0 0" }}>
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="desktop-server-bar" data-testid="desktop-server-bar">
      <div className="desktop-server-bar-info">
        <span style={{ color: "var(--im-text-muted)" }}>{text("当前服务：", "Server: ")}</span>
        <code>{currentOrigin}</code>
        {currentSecurity.kind === "private_http" && (
          <span className="desktop-chip warn" data-testid="desktop-private-http-badge">
            {text("内网 HTTP", "Private HTTP")}
          </span>
        )}
      </div>
      <button
        type="button"
        className="desktop-btn subtle compact"
        onClick={() => {
          setDraft(currentOrigin);
          setError(null);
          setEditing(true);
        }}
      >
        {text("切换服务", "Switch server")}
      </button>
    </div>
  );
}
