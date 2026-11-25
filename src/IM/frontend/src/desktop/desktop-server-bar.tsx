import { useState } from "react";
import { useAuthStore } from "../features/auth/auth-store";
import { useTranslation } from "../i18n";
import { switchDesktopServer } from "./desktop-api";
import { getDesktopImOrigin, isDesktopClient } from "./desktop-context";
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

  async function save() {
    const trimmed = draft.trim().replace(/\/+$/, "");
    if (!trimmed) {
      setError(text("请输入有效的 IM 服务地址", "Enter a valid IM server URL"));
      return;
    }
    let parsed: URL;
    try {
      parsed = new URL(trimmed);
    } catch {
      setError(text("服务地址必须是完整的 http:// 或 https:// URL", "Server URL must be a full http:// or https:// address"));
      return;
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      setError(text("仅支持 http:// 或 https:// 服务地址", "Only http:// and https:// server URLs are supported"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await switchDesktopServer(parsed.origin);
      useAuthStore.getState().clear();
      if (window.__CREWDEN_DESKTOP__) {
        window.__CREWDEN_DESKTOP__ = {
          ...window.__CREWDEN_DESKTOP__,
          imOrigin: updated.im_origin,
          contextEpoch: updated.context_epoch,
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
        <strong>{text("连接到的 IM 服务地址", "Target IM server address")}</strong>
        <div className="local-field" style={{ margin: "8px 0" }}>
          <input
            className="desktop-text-input"
            value={draft}
            aria-label={text("IM 服务地址", "IM server address")}
            placeholder="https://im.example.com"
            disabled={saving}
            onChange={(e) => {
              setDraft(e.target.value);
              setError(null);
            }}
          />
        </div>
        {error && (
          <p className="node-form-error" role="alert" style={{ margin: "0 0 8px" }}>
            {error}
          </p>
        )}
        <div className="desktop-action-row">
          <button type="button" className="desktop-btn primary compact" disabled={saving} onClick={() => void save()}>
            {saving ? text("正在切换…", "Switching…") : text("保存服务地址", "Save server address")}
          </button>
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
        </div>
      </div>
    );
  }

  return (
    <div className="desktop-server-bar" data-testid="desktop-server-bar">
      <div>
        <span style={{ color: "var(--im-text-muted)" }}>{text("当前服务：", "Current server: ")}</span>
        <code>{currentOrigin}</code>
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
