import { authFetch } from "../../features/auth/auth-fetch";
import { useAuthStore } from "../../features/auth/auth-store";

type DeliveryQueue = { viewer: string; pending: Set<string> };
let delivery: DeliveryQueue | undefined;

async function flushDelivery(queue: DeliveryQueue) {
  const unsubscribe = useAuthStore.subscribe(state => {
    if (delivery === queue && state.user?.id !== queue.viewer) delivery = undefined;
  });
  let delay = 1000;
  try {
    while (delivery === queue && queue.pending.size) {
      const ids = [...queue.pending].slice(0, 100);
      const response = await authFetch("/im/v1/message-receipts", {
        method: "POST", body: JSON.stringify({ message_ids: ids })
      }).catch(() => undefined);
      if (response && (response.ok || (response.status >= 400 && response.status < 500 && ![401, 408, 429].includes(response.status)))) {
        for (const id of ids) queue.pending.delete(id);
        delay = 1000;
      } else if (delivery === queue) {
        await new Promise(resolve => setTimeout(resolve, delay));
        delay = Math.min(delay * 2, 30_000);
      }
    }
  } finally {
    unsubscribe();
    if (delivery === queue) delivery = undefined;
  }
}

/** Confirm actual receipt after an authenticated client has decoded message content. */
export function confirmMessageDelivery(messages: { id?: unknown; sender_user_id?: unknown; receipts_requested?: unknown }[]) {
  const viewer = useAuthStore.getState().user?.id;
  if (!viewer) return;
  const ids = messages.flatMap(message => message.receipts_requested === true && message.sender_user_id !== viewer
    && typeof message.id === "string" ? [message.id] : []);
  if (!ids.length) return;
  if (delivery?.viewer === viewer) {
    for (const id of ids) delivery.pending.add(id);
  } else {
    delivery = { viewer, pending: new Set(ids) };
    void flushDelivery(delivery);
  }
}
