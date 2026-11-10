import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { workCatalogPath, workRequest, type WorkCatalogPage, type WorkSession } from "./agent-work-api";
import { tr } from "./agent-work-text";

export function LegacyWorkLinks({ agentId, filter, onChild, label }: {
  agentId: string;
  filter: Record<string, string>;
  onChild(id: string): void;
  label: string;
}) {
  const [opened, setOpened] = useState(false);
  const matches = useInfiniteQuery({
    queryKey: ["work-link-matches", agentId, filter], enabled: opened, staleTime: Infinity, initialPageParam: "",
    queryFn: ({pageParam, signal}) => workRequest<WorkCatalogPage>(workCatalogPath(agentId, {
      ...filter, ...(pageParam ? {after_session: pageParam} : {}),
    }), signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
  const candidates = matches.data?.pages.flatMap(page => page.sessions) ?? [];
  const find = async () => {
    setOpened(true);
    const result = await matches.refetch();
    const first = result.data?.pages[0];
    if (first?.match_mode === "exact" && first.sessions.length === 1 && !first.next_cursor) onChild(first.sessions[0].session_id);
  };
  return <>
    {!opened && <button type="button" className="im-work-child-link" onClick={() => void find()}>{tr(label)}</button>}
    {opened && matches.isFetching && !candidates.length && <small role="status">{tr("正在加载工作记录…")}</small>}
    {opened && candidates.map(session => <WorkLink key={session.session_id} session={session} id={session.session_id} label={label} distinguish onChild={onChild} />)}
    {opened && matches.hasNextPage && <button type="button" disabled={matches.isFetching} onClick={() => void matches.fetchNextPage()}>{tr("加载更多")}</button>}
    {opened && !matches.isFetching && (matches.isError || !candidates.length) && <span>{tr("关联执行不可访问 ")}<button type="button" onClick={() => void find()}>{tr("重试")}</button></span>}
  </>;
}

export function WorkLink({ session, id, label, onChild, distinguish = false }: {
  session?: WorkSession; id: string; label: string; onChild(id: string): void; distinguish?: boolean;
}) {
  const description = session?.description || session?.child_agent_id || session?.title;
  const visible = description && distinguish ? description + " · " + id.slice(-8) : description || id;
  return <button id={`work-child-${id}`} type="button" className="im-work-child-link" onClick={() => onChild(id)}>
    {tr(label)}{session && ` · ${visible}`}
  </button>;
}
