// 桌面通知触发器:订阅 IM WS 流,在 agent 回复完成 + tab 非前台时弹出系统通知。
//
// 设计要点:
// - app toast 与桌面通知复用同一纯 lifecycle accumulator；本组件只保留
//   visibility/preference/permission 展示策略与 Notification 副作用。
// - 订阅全局 user stream 而非寄生在 chat workspace,因为通知需要在用户离开 /chat 路由
//   时也持续工作(spec 场景 D:用户在 Me 页时 agent 完成,也要弹)。
// - 跟踪 agent 发出的消息 id,排除"用户自己发出的消息回声"误弹。

import { useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import type { Conversation } from "../chat/chat-types";
import { subscribeUserStream } from "../../realtime/user-stream";
import {
  type AgentCompletionCandidate,
  type AgentCompletionState,
  emptyAgentCompletionState,
  hydrateAgentCompletionState,
  persistAgentCompletionState,
  reduceAgentCompletionEvent
} from "./agent-completion-accumulator";
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
export function AgentCompletionNotifier(): null {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [preferenceEnabled] = useNotificationPreference();
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const stateRef = useRef<AgentCompletionState>(emptyAgentCompletionState);
  const hiddenRef = useRef<boolean>(isDocumentHidden());
  const preferenceRef = useRef<boolean>(preferenceEnabled);
  preferenceRef.current = preferenceEnabled;
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  useEffect(() => {
    stateRef.current = hydrateAgentCompletionState(userId);
  }, [userId]);

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
    if (!isNotificationSupported()) return;
    return subscribeUserStream({
      onEvent: (event) => {
        const reduced = reduceAgentCompletionEvent(stateRef.current, event);
        stateRef.current = reduced.state;
        persistAgentCompletionState(userId, reduced.state);
        if (!reduced.candidate) return;
        const spec = buildCandidateSpec(reduced.candidate, {
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
      }
    });
  }, [resolveAgentName, userId]);

  return null;
}
