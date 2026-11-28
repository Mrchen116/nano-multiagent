import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation } from "react-router-dom";
import { accountEnabled, useAuthStore } from "../features/auth/auth-store";
import { useTranslation } from "../i18n";
import {
  connectDesktopLocalNode,
  DesktopTransferRequiredError,
  inspectDesktopLocalNode,
} from "./desktop-api";
import { desktopScopedKey, getDesktopImOrigin, isDesktopClient } from "./desktop-context";
import "./desktop.css";

function dismissalKey(userId: string): string {
  return desktopScopedKey(`desktop-bind-dismissed:${userId}`);
}

/** Post-login in-app computer binding, same-owner takeover, and foreign-owner transfer guard.
 *
 * Args:
 *   inline: Render inline inside `/onboarding` or `/settings/nodes` instead of a modal overlay.
 *   onConnected: Optional callback invoked once the local node is bound and online.
 */
export function DesktopNodeOnboardingBanner({
  inline = false,
  onConnected,
}: {
  inline?: boolean;
  onConnected?(nodeId: string): void;
}) {
  const { i18n } = useTranslation();
  const location = useLocation();
  const zh = i18n.language.startsWith("zh");
  const text = (cn: string, en: string) => (zh ? cn : en);
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const client = useQueryClient();
  const imOrigin = getDesktopImOrigin();
  const enabled = isDesktopClient() && Boolean(user && accessToken && accountEnabled(user));

  const [dismissed, setDismissed] = useState(() =>
    user ? window.sessionStorage.getItem(dismissalKey(user.id)) === "1" : false,
  );
  const [confirmingTransfer, setConfirmingTransfer] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  const inspectQuery = useQuery({
    queryKey: ["desktop", "local-node", user?.id],
    queryFn: () => inspectDesktopLocalNode(),
    enabled,
    staleTime: 4_000,
  });

  const connectMutation = useMutation({
    mutationFn: (confirmTransfer: boolean) => connectDesktopLocalNode({ confirmTransfer }),
    onSuccess: async (result) => {
      setConnectError(null);
      setConfirmingTransfer(false);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["desktop", "local-node"] }),
        client.invalidateQueries({ queryKey: ["onboarding"] }),
        client.invalidateQueries({ queryKey: ["settings", "nodes"] }),
        client.invalidateQueries({ queryKey: ["chat", "nodes"] }),
      ]);
      onConnected?.(result.node_id);
    },
    onError: (err) => {
      if (err instanceof DesktopTransferRequiredError) {
        setConfirmingTransfer(true);
        setConnectError(null);
        return;
      }
      setConnectError(err instanceof Error ? err.message : text("无法连接这台电脑，请稍后重试。", "Could not connect this computer. Please retry."));
    },
  });

  if (!enabled || !user) return null;
  if (!inline && (dismissed || location.pathname.startsWith("/settings/nodes"))) return null;
  const inspect = inspectQuery.data;
  if (!inspect) return null;
  if (inspect.ownership === "managed_online" || inspect.ownership === "managed_stopped") {
    return null;
  }

  function dismissForSession() {
    if (!user) return;
    window.sessionStorage.setItem(dismissalKey(user.id), "1");
    setDismissed(true);
    setConfirmingTransfer(false);
  }

  const cardClass = inline ? "desktop-bind-card desktop-bind-card--inline" : "desktop-bind-card";

  let content: React.ReactNode;
  if (inspect.ownership === "foreign_owner" || confirmingTransfer) {
    content = (
      <div className={cardClass} data-testid="desktop-bind-foreign">
        <span className="desktop-chip warn">{text("这台电脑已绑定其他账号", "Bound to another account")}</span>
        <h2>{text("确认是否执行整机设备转移？", "Transfer this computer to your account?")}</h2>
        <p style={{ margin: "0 0 12px", color: "var(--im-text-muted)", fontSize: 13 }}>
          {text(
            `本机现有节点 ${inspect.node_name} 归属于另一账号，当前登录账号无权读取其本机配置、日志或私人工作区。`,
            `Existing local node ${inspect.node_name} belongs to another account. Your account cannot read its local settings, logs, or private workspace.`,
          )}
        </p>
        <div className="desktop-server-callout warn">
          <strong>{text("设备归属保护说明：", "Device ownership protection:")}</strong>
          <div style={{ fontSize: 12.5, color: "var(--im-text-muted)" }}>
            {confirmingTransfer
              ? text(
                  `二次确认：将整台电脑「${inspect.node_name}」及普通助手移交给 @${user.username}？原主人的私人助手不会转移。`,
                  `Final confirmation: transfer "${inspect.node_name}" and its standard assistants to @${user.username}? The previous owner's personal assistant will not transfer.`,
                )
              : text(
                  "默认你可以直接进入聊天（不触碰本机现有节点）。仅当确认将整台电脑及普通助手移交给当前账号时才执行设备转移。",
                  "By default you can use chat directly without touching the existing local node. Only confirm device transfer if you intend to move this computer to your account.",
                )}
          </div>
        </div>
        {connectError && (
          <p className="node-form-error" role="alert">
            {connectError}
          </p>
        )}
        <div className="desktop-action-row">
          {!confirmingTransfer ? (
            <>
              {inline ? (
                <a href="/chat" className="desktop-btn primary">
                  {text("仅使用聊天（推荐）", "Chat only (Recommended)")}
                </a>
              ) : (
                <button type="button" className="desktop-btn primary" style={{ flex: 1 }} onClick={dismissForSession}>
                  {text("仅使用聊天（推荐）", "Chat only (Recommended)")}
                </button>
              )}
              <button
                type="button"
                className="desktop-btn"
                disabled={connectMutation.isPending}
                onClick={() => setConfirmingTransfer(true)}
              >
                {text("确认整机转移…", "Transfer this computer…")}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="desktop-btn primary"
                disabled={connectMutation.isPending}
                onClick={() => connectMutation.mutate(true)}
              >
                {connectMutation.isPending
                  ? text("正在转移并接管…", "Transferring…")
                  : text("确认转移并接管", "Confirm transfer and take over")}
              </button>
              <button
                type="button"
                className="desktop-btn"
                disabled={connectMutation.isPending}
                onClick={() => {
                  setConfirmingTransfer(false);
                  if (!inline) dismissForSession();
                }}
              >
                {text("取消，仅使用聊天", "Cancel, chat only")}
              </button>
            </>
          )}
        </div>
      </div>
    );
  } else if (inspect.ownership === "takeover_available") {
    content = (
      <div className={cardClass} data-testid="desktop-bind-takeover">
        <span className="desktop-chip online">{text("检测到当前账号的本机节点", "Existing local node detected")}</span>
        <h2>{text("接管本机已有的助手与工作区", "Take over your existing local node")}</h2>
        <p style={{ margin: "0 0 12px", color: "var(--im-text-muted)", fontSize: 13 }}>
          {text(
            `这台电脑此前已绑定至你当前的账号 @${user.username}。`,
            `This computer is already bound to your current account @${user.username}.`,
          )}
        </p>
        <div className="desktop-server-callout">
          <strong>{text("平滑接管将保留以下全部内容：", "Smooth takeover preserves:")}</strong>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18, color: "var(--im-text-muted)", fontSize: 12.5 }}>
            <li>{text(`原电脑身份 ${inspect.node_name} 与已连接模型凭据`, `Computer identity ${inspect.node_name} and model credentials`)}</li>
            <li>{text("已有助手及原会话历史", "Existing assistants and conversation history")}</li>
            <li>{text("全部本地工作区文件；旧后台启动入口自动停用移交，不产生双实例冲突", "All local workspace files; standalone background launcher is cleanly handed over without dual-instance conflict")}</li>
          </ul>
        </div>
        {connectError && (
          <p className="node-form-error" role="alert">
            {connectError}
          </p>
        )}
        <div className="desktop-action-row">
          <button
            type="button"
            className="desktop-btn primary"
            style={{ flex: 1 }}
            disabled={connectMutation.isPending}
            onClick={() => connectMutation.mutate(false)}
          >
            {connectMutation.isPending
              ? text("正在接管本机节点…", "Taking over…")
              : text("接管并进入工作台", "Take over and continue")}
          </button>
          {!inline && (
            <button type="button" className="desktop-btn" disabled={connectMutation.isPending} onClick={dismissForSession}>
              {text("暂不接管", "Not now")}
            </button>
          )}
        </div>
      </div>
    );
  } else {
    content = (
      <div className={cardClass} data-testid="desktop-bind-fresh">
        <span className="desktop-chip">{text("零命令行接入", "Zero-CLI setup")}</span>
        <h2>{text("将这台电脑连接到当前账号", "Connect this computer to your account")}</h2>
        <p style={{ margin: "0 0 14px", color: "var(--im-text-muted)", fontSize: 13 }}>
          {text(
            "连接后，个人助手和本机数字员工将在这台电脑后台运行，并随系统登录自动启动。",
            "Your personal assistant and local agents will run in the background on this computer and start automatically at login.",
          )}
        </p>
        <div className="local-panel-box" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13 }}>
            <strong>{text("电脑名称：", "Computer name: ")}</strong>
            {inspect.node_name}
          </div>
          <div style={{ fontSize: 13, marginTop: 6 }}>
            <strong>{text("目标服务：", "Server: ")}</strong>
            <code>{imOrigin}</code> · {text("账号", "Account")} <code>@{user.username}</code>
          </div>
          <div style={{ fontSize: 12, color: "var(--im-text-muted)", marginTop: 6 }}>
            {text("内置运行环境已就绪 · 默认开启开机登录自启", "Bundled runtime ready · Login autostart enabled by default")}
          </div>
        </div>
        {connectError && (
          <p className="node-form-error" role="alert">
            {connectError}
          </p>
        )}
        <div className="desktop-action-row">
          <button
            type="button"
            className="desktop-btn primary"
            style={{ flex: 1 }}
            disabled={connectMutation.isPending}
            onClick={() => connectMutation.mutate(false)}
          >
            {connectMutation.isPending
              ? text("正在绑定并启动…", "Binding and starting…")
              : connectError
                ? text("重试连接", "Retry connection")
                : text("绑定并启动这台电脑", "Bind and start this computer")}
          </button>
          {!inline && (
            <button type="button" className="desktop-btn" disabled={connectMutation.isPending} onClick={dismissForSession}>
              {text("暂不绑定", "Skip for now")}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (inline) return content;
  return (
    <div className="desktop-bind-overlay" role="dialog" aria-modal="true" aria-label={text("本机电脑接入", "Connect local computer")}>
      {content}
    </div>
  );
}
