import type { QueryClient, QueryFilters } from "@tanstack/react-query";
import type { Conversation } from "./chat-types";

/** Retire all reads after access changes, or only reads preceding a cleanup revision. */
export function retireChatReadCache(client: QueryClient, conversationId: string, beforeRevision?: number) {
  if (beforeRevision === 0) return;
  for (const resource of ["conversation-detail", "messages", "message-process"]) {
    const filter: QueryFilters = {
      queryKey: ["chat", resource, conversationId],
      predicate: beforeRevision === undefined ? undefined : query => {
        const revision = resource === "conversation-detail"
          ? (query.state.data as Conversation | undefined)?.execution_cleanup_revision
          : Number(query.queryKey[3]);
        return (revision || 0) < beforeRevision;
      }
    };
    client.removeQueries(filter);
  }
}
