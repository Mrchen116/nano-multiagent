// 桌面通知展示器:消费顶层协调器产出的 completion candidate。
//
// 设计要点:
// - user stream 订阅、hydrate/reduce/persist 只有 useGlobalMessageToast 一个 owner。
// - 本组件只保留 visibility/preference/permission 与 Notification 副作用。

import { useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import type { Conversation } from "../chat/chat-types";
import { type AgentCompletionCandidate } from "./agent-completion-accumulator";
import { ensureNotificationPermission, isNotificationSupported, showAgentNotification } from "./notification-api";
import { isDocumentHidden, subscribeDocumentVisibility } from "./document-visibility";
import { useNotificationPreference } from "./notification-preference";
import { useAuthStore } from "../auth/auth-store";

const NOTIFICATION_BODY_MAX = 140;

interface NotificationSpec {
  title: string;
  body: string;
  conversationId: string;
  tag: string;
}

interface BuildSpecContext {
  hidden: boolean;
  enabled: boolean;
  permissionGranted: boolean;
  resolveAgentName(senderUserId: string): string;
}

function truncate(text: string): string {
  if (text.length <= NOTIFICATION_BODY_MAX) return text;
  return `${text.slice(0, NOTIFICATION_BODY_MAX - 1)}…`;
}

function buildCandidateSpec(
  candidate: AgentCompletionCandidate,
  ctx: BuildSpecContext
): NotificationSpec | null {
  if (!ctx.hidden || !ctx.enabled || !ctx.permissionGranted) return null;
  const resolvedName = ctx.resolveAgentName(candidate.senderUserId);
  return {
    title: resolvedName === candidate.senderUserId ? candidate.senderName : resolvedName,
    body: truncate(candidate.preview),
    conversationId: candidate.conversationId,
    tag: `im-conv-${candidate.conversationId}`
  };
}

/**
 * 顶层挂载组件:开 WS、监听 visibility/preference、按 spec 弹通知。
 * 必须放在登录 RequireAuth 之内,确保 access_token 已就绪。
 */
export function AgentCompletionNotifier({
  candidate
}: {
  candidate: AgentCompletionCandidate | null;
}): null {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [preferenceEnabled] = useNotificationPreference();
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const seenCandidateRef = useRef<string | null>(null);
  const hiddenRef = useRef<boolean>(isDocumentHidden());
  const preferenceRef = useRef<boolean>(preferenceEnabled);
  preferenceRef.current = preferenceEnabled;
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  // 用户打开通知时,确保浏览器权限就位(default → 弹一次系统授权框)。
  useEffect(() => {
    if (!preferenceEnabled) return;
    void ensureNotificationPermission();
  }, [preferenceEnabled]);

  // 订阅 visibility 变化(以 ref 形式提供给事件处理器,避免重订 WS)。
  useEffect(() => {
    hiddenRef.current = isDocumentHidden();
    return subscribeDocumentVisibility((hidden) => {
      hiddenRef.current = hidden;
    });
  }, []);

  const resolveAgentName = useMemo(
    () => (senderUserId: string) => {
      const list = queryClient.getQueryData<Conversation[]>(["chat", "conversations"]);
      if (!list) return senderUserId;
      const rawId = senderUserId.replace(/^agent:/, "");
      for (const c of list) {
        const match = c.participants.find((p) => p.type === "agent" && p.id === rawId);
        if (match?.display_name) return match.display_name;
      }
      return senderUserId;
    },
    [queryClient]
  );

  useEffect(() => {
    if (!candidate || !userId || !isNotificationSupported()) return;
    const candidateIdentity = `${userId}:${candidate.messageKey}`;
    if (seenCandidateRef.current === candidateIdentity) return;
    seenCandidateRef.current = candidateIdentity;
    const spec = buildCandidateSpec(candidate, {
      hidden: hiddenRef.current,
      enabled: preferenceRef.current,
      permissionGranted:
        typeof globalThis !== "undefined" &&
        typeof (globalThis as { Notification?: { permission: NotificationPermission } }).Notification?.permission ===
          "string" &&
        (globalThis as { Notification: { permission: NotificationPermission } }).Notification.permission ===
          "granted",
      resolveAgentName
    });
    if (!spec) return;
    showAgentNotification({
      title: spec.title,
      body: spec.body,
      tag: spec.tag,
      onClick: () => {
        try {
          window.focus();
        } catch {
          /* focus 可能在某些浏览器被阻挡,通知点击的导航仍然要发生 */
        }
        navigateRef.current(`/chat/${spec.conversationId}`);
      }
    });
  }, [candidate, resolveAgentName, userId]);

  return null;
}
