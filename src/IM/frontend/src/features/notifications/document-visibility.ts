// `visibilityState` 判定:Notification 仅在标签页/窗口非前台时才弹,符合 spec 场景 D。
//
// 这里单独成模块、不内联在 notifier 里,是因为 visibility 判断 + 订阅在 SSR
// 环境下(无 document)需要降级为"永远 visible",抽出一个边界后调用方就不必再判 typeof。

export function isDocumentHidden(): boolean {
  if (typeof document === "undefined") return false;
  return document.visibilityState !== "visible";
}

export function subscribeDocumentVisibility(listener: (hidden: boolean) => void): () => void {
  if (typeof document === "undefined") return () => {};
  const handler = () => listener(isDocumentHidden());
  document.addEventListener("visibilitychange", handler);
  return () => document.removeEventListener("visibilitychange", handler);
}
