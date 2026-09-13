import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { subscribeUserStream } from "../../realtime/user-stream";
import { listConversations } from "./chat-api";
import { composerStoreFor, forgetComposerConversation, restoreComposerMembership } from "./components/composer-draft-store";
import { useAuthStore } from "../auth/auth-store";
import type { Conversation } from "./chat-types";

/** Membership changes also invalidate chats while the user is viewing settings. */
export function useMembershipCache() {
  const client = useQueryClient();
  useEffect(() => {
    async function refresh() {
      const userId = useAuthStore.getState().user?.id;
      const conversations = await listConversations();
      if (useAuthStore.getState().user?.id !== userId) return;
      const visible = new Set(conversations.map(c => c.id));
      const previous = client.getQueryData<Conversation[]>(["chat", "conversations"]) ?? [];
      for (const chat of previous) {
        if (visible.has(chat.id)) continue;
        await client.cancelQueries({ queryKey: ["chat", "messages", chat.id] });
        client.removeQueries({ queryKey: ["chat", "messages", chat.id] });
        forgetComposerConversation(composerStoreFor(userId ?? null), chat.id);
      }
      client.removeQueries({ queryKey: ["chat", "slash-candidates"] });
      restoreComposerMembership(composerStoreFor(userId ?? null), visible);
      client.setQueryData(["chat", "conversations"], conversations);
    }
    return subscribeUserStream({ onRecovery: refresh, onEvent: event => {
      if (event.eventType !== "conversation.membership_changed" && event.eventType !== "conversation.deleted") return;
      const id = event.payload.conversation_id;
      if (typeof id !== "string") return;
      void client.cancelQueries({ queryKey: ["chat", "messages", id] });
      client.removeQueries({ queryKey: ["chat", "messages", id] });
      void refresh().catch(() => client.invalidateQueries({ queryKey: ["chat", "conversations"] }));
    } });
  }, [client]);
}
