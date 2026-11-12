import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { workRequest, type WorkTurn, type WorkTurnPage } from "./agent-work-api";

interface History {
  turns: WorkTurn[];
  older: Record<string, string | null>;
}

const empty: History = {turns: [], older: {}};

export const workHistoryTurnKey = (turn: WorkTurn, combined: boolean) => combined ? String(turn.seq) : turn.turn_id;

function merge(history: History, page: WorkTurnPage, combined: boolean, replace = true): History {
  const key = (turn: WorkTurn) => workHistoryTurnKey(turn, combined);
  const turns = new Map(history.turns.map(turn => [key(turn), turn]));
  const older = {...history.older};
  page.turns.forEach((turn, index) => {
    if (!replace && turns.has(key(turn))) return;
    turns.set(key(turn), turn);
    const next = page.turns[index + 1];
    older[key(turn)] = next ? key(next) : combined ? (page.next_turn_seq == null ? null : String(page.next_turn_seq)) : page.next_turn_id ?? null;
  });
  return {turns: [...turns.values()].sort((a, b) => b.seq - a.seq), older};
}

/** Remember the neighbors reported by each read, even after the head moves. */
export function useWorkHistory(agentId: string, sessionId: string | null | undefined, head: WorkTurnPage | undefined, path: string, combined = false) {
  const client = useQueryClient();
  const key = ["agent-work-history", agentId, sessionId, combined] as const;
  const history = useQuery<History>({queryKey: key, queryFn: () => empty, enabled: false}).data ?? empty;
  useEffect(() => {
    if (sessionId && head) client.setQueryData<History>(["agent-work-history", agentId, sessionId, combined], current => merge(current ?? empty, head, combined));
  }, [agentId, client, sessionId, head, combined]);
  const older = useMutation({
    mutationFn: async ({before, queryKey, base}: {before: string; queryKey: typeof key; base: string}) => {
      const page = await workRequest<WorkTurnPage>(queryKey[3]
        ? `${base}?view=summary&catalog=separate&timeline=combined&before_seq=${encodeURIComponent(before)}`
        : `${base}/turns?view=summary&catalog=separate&before_turn=${encodeURIComponent(before)}`);
      client.setQueryData<History>(queryKey, current => merge(current ?? empty, page, queryKey[3], false));
    },
  });
  const visible = useMemo(() => head ? merge(history, head, combined) : history, [head, history, combined]);
  return {
    history: visible,
    combined,
    loading: older.isPending && older.variables?.queryKey[2] === sessionId,
    error: older.variables?.queryKey[2] === sessionId ? older.error : null,
    load: (before: string) => older.mutate({before, queryKey: key, base: path}),
  };
}
