import { isBlockedDesktopOpenPath } from "@nano/product-contracts/desktop-local";
import { useState } from "react";
import { useTranslation } from "../i18n";
import { openDesktopWorkspacePath } from "./desktop-api";
import { getDesktopBootContext, isDesktopClient } from "./desktop-context";
import { useDesktopLocalAgentMap, useWorkspaceAgentId } from "./use-desktop-local-agents";
import "./desktop.css";

function normalizeFileUrlToPath(fileUrl: string): string | null {
  try {
    const parsed = new URL(fileUrl);
    if (parsed.protocol !== "file:") return null;
    const decoded = decodeURIComponent(parsed.pathname);
    if (/^\/[a-zA-Z]:\//.test(decoded)) {
      return decoded.slice(1);
    }
    return decoded;
  } catch {
    return null;
  }
}

/** Render compact Open / Reveal buttons next to a workspace file path when authorized on this local node. */
export function WorkspacePathActions({
  path,
  agentId: explicitAgentId,
}: {
  path: string;
  agentId?: string | null;
}) {
  if (!isDesktopClient() || !path.trim()) {
    return null;
  }
  return <WorkspacePathActionsInner path={path} explicitAgentId={explicitAgentId} />;
}

function WorkspacePathActionsInner({
  path,
  explicitAgentId,
}: {
  path: string;
  explicitAgentId?: string | null;
}) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const contextAgentId = useWorkspaceAgentId();
  const agentId = explicitAgentId ?? contextAgentId;
  const localAgents = useDesktopLocalAgentMap();
  const [busy, setBusy] = useState<"open" | "reveal" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!agentId || !localAgents.has(agentId)) {
    return null;
  }

  const boot = getDesktopBootContext();
  const revealLabel =
    boot?.platform === "win32-x64"
      ? text("在资源管理器中显示", "Show in Explorer")
      : text("在 Finder 中显示", "Show in Finder");
  const blocked = isBlockedDesktopOpenPath(path);

  async function trigger(action: "open" | "reveal") {
    if (!agentId) return;
    setBusy(action);
    setError(null);
    try {
      await openDesktopWorkspacePath({ agent_id: agentId, path, action });
    } catch (err) {
      setError(err instanceof Error ? err.message : text("无法打开本地路径", "Could not open local path"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <span className="desktop-path-actions" data-testid="workspace-path-actions">
      {!blocked && (
        <button
          type="button"
          className="desktop-btn primary compact"
          disabled={busy !== null}
          onClick={(e) => {
            e.stopPropagation();
            void trigger("open");
          }}
        >
          {text("打开文件", "Open file")}
        </button>
      )}
      <button
        type="button"
        className="desktop-btn compact"
        disabled={busy !== null}
        title={
          blocked
            ? text("可执行脚本或应用仅支持在文件管理器中定位，避免误运行", "Executable files can only be revealed in the file manager")
            : undefined
        }
        onClick={(e) => {
          e.stopPropagation();
          void trigger("reveal");
        }}
      >
        {revealLabel}
      </button>
      {error && (
        <span className="desktop-path-feedback" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}

/** Render a Markdown `file://` link inside Desktop chat messages with safe local workspace actions. */
export function DesktopWorkspaceFileLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  const localPath = normalizeFileUrlToPath(href);
  if (!isDesktopClient() || !localPath) {
    return <span className="im-md-link-unsupported">{children}</span>;
  }
  return <DesktopWorkspaceFileLinkInner href={href} localPath={localPath}>{children}</DesktopWorkspaceFileLinkInner>;
}

function DesktopWorkspaceFileLinkInner({
  href,
  localPath,
  children,
}: {
  href: string;
  localPath: string;
  children: React.ReactNode;
}) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const agentId = useWorkspaceAgentId();
  const localAgents = useDesktopLocalAgentMap();
  const [error, setError] = useState<string | null>(null);

  if (!agentId || !localAgents.has(agentId)) {
    return <span className="im-md-link-unsupported">{children}</span>;
  }

  const blocked = isBlockedDesktopOpenPath(localPath);
  const action: "open" | "reveal" = blocked ? "reveal" : "open";

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <a
        href={href}
        className="im-md-link"
        onClick={(event) => {
          event.preventDefault();
          setError(null);
          void openDesktopWorkspacePath({ agent_id: agentId, path: localPath, action }).catch((err) => {
            setError(err instanceof Error ? err.message : text("无法打开本地文件", "Could not open local file"));
          });
        }}
      >
        {children}
      </a>
      <WorkspacePathActions path={localPath} agentId={agentId} />
      {error && (
        <span className="desktop-path-feedback" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
