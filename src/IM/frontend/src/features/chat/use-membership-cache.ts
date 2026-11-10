import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { subscribeUserStream } from "../../realtime/user-stream";
import { listConversations } from "./chat-api";
import { composerStoreFor, forgetComposerConversation, restoreComposerMembership } from "./components/composer-draft-store";
import { useAuthStore } from "../auth/auth-store";
import type { Conversation } from "./chat-types";
import { retireChatReadCache } from "./chat-read-cache";
import { forgetInteractionBackground } from "./interaction-background";

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
          for (const chat of previous) {
            if (visible.has(chat.id)) continue;
            retireChatReadCache(client, chat.id);
            forgetComposerConversation(composerStoreFor(userId ?? null), chat.id);
            if (userId) void forgetInteractionBackground(userId, chat.id).catch(() => {});
          }
          for (const chat of conversations) retireChatReadCache(client, chat.id, chat.execution_cleanup_revision ?? 0);
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
    const unsubscribe = subscribeUserStream({ onRecovery: snapshot => {
      for (const [id, revision] of Object.entries(snapshot?.executionCleanupRevisions ?? {})) retireChatReadCache(client, id, revision);
      return refresh();
    }, onEvent: event => {
      if (event.eventType === "conversation.execution_cleanup") {
        const { conversation_id: id, execution_cleanup_revision: revision } = event.payload;
        if (typeof id === "string" && typeof revision === "number") retireChatReadCache(client, id, revision);
        return;
      }
      if (event.eventType === "message.reconciled") {
        const { conversation_id: id, message_id: messageId } = event.payload;
        if (typeof id === "string" && typeof messageId === "string") {
          void client.invalidateQueries({ queryKey: ["chat", "message-process", id], predicate: query => query.queryKey[5] === messageId });
        }
        return;
      }
      if (event.eventType !== "conversation.membership_changed" && event.eventType !== "conversation.deleted") return;
      const id = event.payload.conversation_id;
      if (typeof id !== "string") return;
      retireChatReadCache(client, id);
      void refresh(true).catch(() => {});
    } });
    return () => { disposed = true; unsubscribe(); };
  }, [client]);
}
