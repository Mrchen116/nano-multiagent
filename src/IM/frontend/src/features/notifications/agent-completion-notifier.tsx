// 桌面通知触发器:订阅 IM WS 流,在 agent 回复完成 + tab 非前台时弹出系统通知。
//
// 设计要点:
// - 纯归约 + 纯 spec 函数(`reduceNotifierEvent` / `buildNotificationSpec`)便于单测覆盖
//   各 gating 条件,React glue 只负责副作用(订阅 WS / 订阅 visibility / 调 Notification)。
// - 单独开一条 `openChatStream` 而非寄生在 chat workspace,因为通知需要在用户离开 /chat 路由
//   时也持续工作(spec 场景 D:用户在 Me 页时 agent 完成,也要弹)。
// - 跟踪 agent 发出的消息 id,排除"用户自己发出的消息回声"误弹。

import { useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import type { Conversation, WsEvent } from "../chat/v2/chat-types";
import { openChatStream } from "../chat/v2/chat-stream";
import { ensureNotificationPermission, isNotificationSupported, showAgentNotification } from "./notification-api";
import { isDocumentHidden, subscribeDocumentVisibility } from "./document-visibility";
import { useNotificationPreference } from "./notification-preference";

const NOTIFICATION_BODY_MAX = 140;

export interface NotifierState {
  agentMessages: Record<string, { conversation_id: string; sender_user_id: string }>;
}

export const emptyNotifierState: NotifierState = { agentMessages: {} };

export function reduceNotifierEvent(state: NotifierState, ev: WsEvent): NotifierState {
  if (ev.type === "message.created") {
    if (ev.sender_type !== "agent") return state;
    return {
      agentMessages: {
        ...state.agentMessages,
        [ev.message_id]: { conversation_id: ev.conversation_id, sender_user_id: ev.sender_user_id }
      }
    };
  }
  if (ev.type === "message.completed") {
    if (!(ev.message_id in state.agentMessages)) return state;
    const next = { ...state.agentMessages };
    delete next[ev.message_id];
    return { agentMessages: next };
  }
  return state;
}

export interface NotificationSpec {
  title: string;
  body: string;
  conversationId: string;
  tag: string;
}

export interface BuildSpecContext {
  hidden: boolean;
  enabled: boolean;
  permissionGranted: boolean;
  resolveAgentName(senderUserId: string): string;
  resolveConversationTitle(conversationId: string): string;
}

function truncate(text: string): string {
  if (text.length <= NOTIFICATION_BODY_MAX) return text;
  return `${text.slice(0, NOTIFICATION_BODY_MAX - 1)}…`;
}

export function buildNotificationSpec(
  state: NotifierState,
  ev: WsEvent,
  ctx: BuildSpecContext
): NotificationSpec | null {
  if (ev.type !== "message.completed") return null;
  const tracked = state.agentMessages[ev.message_id];
  if (!tracked) return null;
  if (!ctx.hidden || !ctx.enabled || !ctx.permissionGranted) return null;
  const senderName = ctx.resolveAgentName(tracked.sender_user_id);
  const body = truncate(ev.content?.trim() ? ev.content : ctx.resolveConversationTitle(tracked.conversation_id));
  return {
    title: senderName,
    body,
    conversationId: tracked.conversation_id,
    tag: `im-conv-${tracked.conversation_id}`
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
  const stateRef = useRef<NotifierState>(emptyNotifierState);
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

  const resolveConversationTitle = useMemo(
    () => (cid: string) => {
      const list = queryClient.getQueryData<Conversation[]>(["chat-v2", "conversations"]);
      return list?.find((c) => c.id === cid)?.title ?? cid;
    },
    [queryClient]
  );

  const resolveAgentName = useMemo(
    () => (senderUserId: string) => {
      const list = queryClient.getQueryData<Conversation[]>(["chat-v2", "conversations"]);
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
    const handle = openChatStream({
      onEvent: (ev) => {
        const prior = stateRef.current;
        stateRef.current = reduceNotifierEvent(prior, ev);
        const spec = buildNotificationSpec(prior, ev, {
          hidden: hiddenRef.current,
          enabled: preferenceRef.current,
          permissionGranted:
            typeof globalThis !== "undefined" &&
            typeof (globalThis as { Notification?: { permission: NotificationPermission } }).Notification?.permission ===
              "string" &&
            (globalThis as { Notification: { permission: NotificationPermission } }).Notification.permission ===
              "granted",
          resolveAgentName,
          resolveConversationTitle
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
    return () => handle.close();
  }, [resolveAgentName, resolveConversationTitle]);

  return null;
}
