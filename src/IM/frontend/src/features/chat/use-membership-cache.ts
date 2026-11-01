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
    let pending = false;
    let disposed = false;
    let invalidateOnFailure = false;
    let running: Promise<void> | undefined;
    function refresh(fromEvent = false): Promise<void> {
      pending = true;
      invalidateOnFailure ||= fromEvent;
      if (running) return running;
      // Coalesce a replay burst, but read again when a change arrives during a request.
      running = Promise.resolve().then(async () => {
        while (pending && !disposed) {
          pending = false;
          const userId = useAuthStore.getState().user?.id;
          const conversations = await listConversations();
          if (disposed || useAuthStore.getState().user?.id !== userId) continue;
          if (pending) continue;
          const visible = new Set(conversations.map(c => c.id));
          const previous = client.getQueryData<Conversation[]>(["chat", "conversations"]) ?? [];
          const removed = previous.filter(chat => !visible.has(chat.id));
          await Promise.all(removed.map(chat => client.cancelQueries({ queryKey: ["chat", "messages", chat.id] })));
          // Cancellation yields; no older authority response may restore revoked membership.
          if (pending || disposed || useAuthStore.getState().user?.id !== userId) continue;
          for (const chat of removed) {
            client.removeQueries({ queryKey: ["chat", "messages", chat.id] });
            forgetComposerConversation(composerStoreFor(userId ?? null), chat.id);
          }
          client.removeQueries({ queryKey: ["chat", "slash-candidates"] });
          restoreComposerMembership(composerStoreFor(userId ?? null), visible);
          client.setQueryData(["chat", "conversations"], conversations);
        }
      }).catch(error => {
        if (invalidateOnFailure) void client.invalidateQueries({ queryKey: ["chat", "conversations"] });
        throw error;
      }).finally(() => { running = undefined; invalidateOnFailure = false; });
      return running;
    }
    const unsubscribe = subscribeUserStream({ onRecovery: refresh, onEvent: event => {
      if (event.eventType !== "conversation.membership_changed" && event.eventType !== "conversation.deleted") return;
      const id = event.payload.conversation_id;
      if (typeof id !== "string") return;
      void client.cancelQueries({ queryKey: ["chat", "messages", id] });
      client.removeQueries({ queryKey: ["chat", "messages", id] });
      void refresh(true).catch(() => {});
    } });
    return () => { disposed = true; unsubscribe(); };
  }, [client]);
}
