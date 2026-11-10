import { authFetch } from "../../features/auth/auth-fetch";
import { useAuthStore } from "../../features/auth/auth-store";

/** Confirm actual receipt after an authenticated client has decoded message content. */
export function confirmMessageDelivery(messages: { id?: unknown; sender_user_id?: unknown; receipts_requested?: unknown }[]) {
  const viewer = useAuthStore.getState().user?.id;
  if (!viewer) return;
  const ids = messages.flatMap(message => message.receipts_requested === true && message.sender_user_id !== viewer
    && typeof message.id === "string" ? [message.id] : []);
  if (!ids.length) return;
  for (let start = 0; start < ids.length; start += 100) {
    void authFetch("/im/v1/message-receipts", {
      method: "POST", body: JSON.stringify({ message_ids: ids.slice(start, start + 100) })
    }).catch(() => {});
  }
}
