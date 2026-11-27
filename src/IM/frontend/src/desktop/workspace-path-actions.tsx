import { isBlockedDesktopOpenPath } from "@nano/product-contracts/desktop-local";
import { useState } from "react";
import { useTranslation } from "../i18n";
import { DesktopApiError, openDesktopWorkspacePath } from "./desktop-api";
import { getDesktopBootContext, isDesktopClient } from "./desktop-context";
import { useDesktopLocalAgentMap, useWorkspaceAgentId } from "./use-desktop-local-agents";
import "./desktop.css";

function localizeWorkspaceError(err: unknown, zh: boolean): string {
  const code = err instanceof DesktopApiError ? err.code : undefined;
  const raw = err instanceof Error ? err.message : "";
  if (code === "executable_open_blocked" || raw.includes("Executable scripts")) {
    return zh
      ? "可执行脚本或应用仅支持在文件管理器中显示，不支持直接运行。"
      : "Executable files can only be revealed in Finder/Explorer, not launched directly.";
  }
  if (code === "outside_workspace" || raw.includes("outside the Agent workspace")) {
    return zh ? "该路径超出当前助手工作区范围，已拒绝打开。" : "Target path is outside this assistant's workspace.";
  }
  if (code === "path_not_found" || raw.includes("no longer exists")) {
    return zh ? "本机未找到该文件，可能已被移动或删除。" : "File no longer exists on this computer.";
  }
  if (code === "workspace_missing") {
    return zh ? "本机工作区目录不存在。" : "Local workspace directory does not exist.";
  }
  if (code === "foreign_owner" || (err instanceof DesktopApiError && err.status === 403)) {
    return zh ? "当前账号无权直接打开该本机工作区文件。" : "Your account is not authorized to open this local workspace path.";
  }
  return raw || (zh ? "无法打开本地路径" : "Could not open local path");
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
  blocked = isBlockedDesktopOpenPath(path),
}: {
  path: string;
  explicitAgentId?: string | null;
  blocked?: boolean;
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

  async function trigger(action: "open" | "reveal") {
    if (!agentId) return;
    setBusy(action);
    setError(null);
    try {
      await openDesktopWorkspacePath({ agent_id: agentId, path, action });
    } catch (err) {
      setError(localizeWorkspaceError(err, zh));
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
  if (isDesktopClient()) {
    try {
      const url = new URL(href);
      if (url.protocol === "file:" && url.pathname) {
        // Decode only for the button policy. The host resolves the complete URL on its own OS.
        const blocked = isBlockedDesktopOpenPath(decodeURIComponent(url.pathname));
        return <DesktopWorkspaceFileLinkInner href={href} blocked={blocked}>{children}</DesktopWorkspaceFileLinkInner>;
      }
    } catch {
      // Malformed file links render as plain text.
    }
  }
  return <span className="im-md-link-unsupported">{children}</span>;
}

function DesktopWorkspaceFileLinkInner({
  href,
  blocked,
  children,
}: {
  href: string;
  blocked: boolean;
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

  const action: "open" | "reveal" = blocked ? "reveal" : "open";

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <a
        href={href}
        className="im-md-link"
        onClick={(event) => {
          event.preventDefault();
          setError(null);
          void openDesktopWorkspacePath({ agent_id: agentId, path: href, action }).catch((err) => {
            setError(localizeWorkspaceError(err, zh));
          });
        }}
      >
        {children}
      </a>
      <WorkspacePathActionsInner path={href} explicitAgentId={agentId} blocked={blocked} />
      {error && (
        <span className="desktop-path-feedback" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
