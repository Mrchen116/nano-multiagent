import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { workBase, workRequest } from "./agent-work-api";
import { tr } from "./agent-work-text";

type Original = {revision: number; type: string; observed_at: string | null; total_bytes: number; state: "complete" | "pending" | "local"};

export function WorkOriginals({agentId, sessionId, turnId}: {agentId: string; sessionId: string; turnId?: string}) {
  const [open, setOpen] = useState(false);
  const path = `${workBase(agentId)}/sessions/${encodeURIComponent(sessionId)}/originals`;
  const originals = useInfiniteQuery({
    queryKey: ["agent-work", agentId, "originals", sessionId, turnId],
    enabled: open,
    initialPageParam: 0,
    queryFn: ({pageParam, signal}) => {
      const query = new URLSearchParams({after_revision: String(pageParam)});
      if (turnId !== undefined) query.set("turn_id", turnId);
      return workRequest<{items: Original[]; next_cursor: number | null}>(`${path}?${query}`, signal);
    },
    getNextPageParam: page => page.next_cursor ?? undefined,
    retry: false,
  });
  const entries = originals.data?.pages.flatMap(page => page.items) ?? [];
  return <details className="im-work-originals" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{tr("大型原文")}</summary>
    {open && <>
      {originals.isLoading && <p role="status">{tr("正在加载工作记录…")}</p>}
      {originals.isError ? <p role="alert">{originals.error.message} <button type="button" onClick={() => void originals.refetch()}>{tr("重试")}</button></p>
        : originals.isSuccess && (entries.length ? <ul>{entries.map(entry => <li key={entry.revision}>
          <span>{entry.type} · {entry.observed_at && `${new Date(entry.observed_at).toLocaleString()} · `}{(entry.total_bytes / 1048576).toFixed(1)} MiB</span>{" "}
          {entry.state === "complete" ? <a href={`${path}/${entry.revision}`} target="_blank" rel="noopener" download>{tr("下载原文")}</a>
            : <span>{tr(entry.state === "pending" ? "原文待补齐，可在原生轨迹中查看" : "原文仅在节点，可在原生轨迹中查看")}</span>}
        </li>)}</ul> : <p>{tr("没有大型原文")}</p>)}
      {originals.hasNextPage && <button type="button" disabled={originals.isFetchingNextPage} onClick={() => void originals.fetchNextPage()}>{tr("加载更多原文")}</button>}
    </>}
  </details>;
}
