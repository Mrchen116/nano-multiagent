import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { workRequest, type WorkTurn, type WorkTurnPage } from "./agent-work-api";

interface History {
  turns: WorkTurn[];
  older: Record<string, string | null>;
}

const empty: History = {turns: [], older: {}};

function merge(history: History, page: WorkTurnPage, replace = true): History {
  const turns = new Map(history.turns.map(turn => [turn.turn_id, turn]));
  const older = {...history.older};
  page.turns.forEach((turn, index) => {
    if (!replace && turns.has(turn.turn_id)) return;
    turns.set(turn.turn_id, turn);
    older[turn.turn_id] = page.turns[index + 1]?.turn_id ?? page.next_turn_id ?? null;
  });
  return {turns: [...turns.values()].sort((a, b) => b.seq - a.seq), older};
}

/** Remember the neighbors reported by each read, even after the head moves. */
export function useWorkHistory(agentId: string, sessionId: string | null | undefined, head: WorkTurnPage | undefined, path: string) {
  const client = useQueryClient();
  const key = ["agent-work-history", agentId, sessionId] as const;
  const history = useQuery<History>({queryKey: key, enabled: false}).data ?? empty;
  useEffect(() => {
    if (sessionId && head) client.setQueryData<History>(["agent-work-history", agentId, sessionId], current => merge(current ?? empty, head));
  }, [agentId, client, sessionId, head]);
  const older = useMutation({
    mutationFn: async ({before, queryKey, base}: {before: string; queryKey: typeof key; base: string}) => {
      const page = await workRequest<WorkTurnPage>(`${base}/turns?view=summary&catalog=separate&before_turn=${encodeURIComponent(before)}`);
      client.setQueryData<History>(queryKey, current => merge(current ?? empty, page, false));
    },
  });
  const visible = useMemo(() => head ? merge(history, head) : history, [head, history]);
  return {
    history: visible,
    loading: older.isPending && older.variables?.queryKey[2] === sessionId,
    error: older.variables?.queryKey[2] === sessionId ? older.error : null,
    load: (before: string) => older.mutate({before, queryKey: key, base: path}),
  };
}
