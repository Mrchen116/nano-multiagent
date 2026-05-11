// 浏览器 Notification API 的薄封装。
//
// 为什么单独抽一层而不是在调用点 `new Notification()`:
// - 单元测试可以注入 fake 全局,而无需 jsdom polyfill;
// - 不支持 Notification 的环境(SSR / 旧 jsdom / 老浏览器)在这里一次性退化为 no-op,
//   调用方无需处处判 `typeof Notification`;
// - 权限请求和"已 denied 不再追问"的 UX 决策集中在一个地方,避免风险点散落。

type GlobalWithNotification = typeof globalThis & {
  Notification?: {
    new (title: string, options?: NotificationOptions): Notification;
    permission: NotificationPermission;
    requestPermission(): Promise<NotificationPermission>;
  };
};

function getCtor() {
  return (globalThis as GlobalWithNotification).Notification;
}

export function isNotificationSupported(): boolean {
  return typeof getCtor() === "function";
}

/**
 * 返回当前权限;若处于 `default`,会触发一次浏览器原生请求弹窗。
 * 已经 `denied` 不再追问(浏览器一旦拒绝,反复弹只会更打扰用户)。
 */
export async function ensureNotificationPermission(): Promise<NotificationPermission> {
  const Ctor = getCtor();
  if (!Ctor) return "denied";
  if (Ctor.permission === "granted" || Ctor.permission === "denied") {
    return Ctor.permission;
  }
  return Ctor.requestPermission();
}

export interface ShowNotificationInput {
  title: string;
  body: string;
  /** 点击通知时回调(用于聚焦窗口 + 路由跳转)。 */
  onClick: () => void;
  /** 用于 `tag` 折叠同一会话内的连续通知,避免移动端通知中心堆积。 */
  tag?: string;
}

export interface NotificationHandle {
  close(): void;
}

export function showAgentNotification(input: ShowNotificationInput): NotificationHandle | null {
  const Ctor = getCtor();
  if (!Ctor) return null;
  if (Ctor.permission !== "granted") return null;
  const instance = new Ctor(input.title, { body: input.body, tag: input.tag }) as unknown as {
    onclick: ((this: unknown) => void) | null;
    close: () => void;
  };
  instance.onclick = function () {
    try {
      input.onClick();
    } finally {
      this && (this as { close?: () => void }).close?.();
    }
  };
  return { close: () => instance.close() };
}
