import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronDown, LoaderCircle, Settings, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { subscribeUserStream } from "../../../realtime/user-stream";
import { workBase, workRequest, type WorkActivity } from "../../settings/agents/agent-work-api";
import "./agent-activity-popover.css";

export interface AgentActivityAnchor {
  agentId: string;
  name: string;
  element: HTMLButtonElement;
}

export function AgentActivityPopover({anchor, canConfigure, onClose}: {
  anchor: AgentActivityAnchor;
  canConfigure: boolean;
  onClose(): void;
}) {
  const {t} = useTranslation();
  const card = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const path = `${workBase(anchor.agentId)}/activity`;
  const activity = useQuery({
    queryKey: ["chat-work-activity", anchor.agentId],
    queryFn: ({signal}) => workRequest<WorkActivity>(path, signal),
    refetchInterval: 15_000,
    retry: false,
  });
  const extra = useInfiniteQuery({
    queryKey: ["chat-work-activity-list", anchor.agentId, activity.data?.revision],
    enabled: false,
    initialPageParam: activity.data?.next_cursor ?? "",
    queryFn: ({signal, pageParam}) => workRequest<WorkActivity>(`${path}?after_session=${encodeURIComponent(pageParam)}`, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
    retry: false,
  });
  const refresh = activity.refetch;
  useEffect(() => {
    let timer: number | undefined;
    const schedule = () => {
      if (document.hidden || timer !== undefined) return;
      timer = window.setTimeout(() => { timer = undefined; void refresh({cancelRefetch: false}); }, 300);
    };
    const unsubscribe = subscribeUserStream({
      onEvent: event => {
        if ((event.eventType === "agent.work.updated" || event.eventType === "agent.status_changed") &&
          event.payload.agent_id === anchor.agentId) schedule();
      },
      onRecovery: schedule,
    });
    document.addEventListener("visibilitychange", schedule);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", schedule);
      unsubscribe();
    };
  }, [anchor.agentId, refresh]);
  useLayoutEffect(() => {
    const position = () => {
      const rect = anchor.element.getBoundingClientRect();
      const panel = card.current;
      if (!panel) return;
      const gap = 8;
      const rightSide = rect.right + gap + panel.offsetWidth <= window.innerWidth - gap;
      const leftSide = rect.left - panel.offsetWidth - gap >= gap;
      const side = rightSide || leftSide;
      const left = rightSide ? rect.right + gap : leftSide ? rect.left - panel.offsetWidth - gap : rect.left;
      const top = side ? rect.top : rect.bottom + gap;
      panel.style.left = `${Math.max(gap, Math.min(left, window.innerWidth - panel.offsetWidth - gap))}px`;
      panel.style.top = `${Math.max(gap, Math.min(top, window.innerHeight - panel.offsetHeight - gap))}px`;
    };
    const resize = new ResizeObserver(position);
    if (card.current) resize.observe(card.current);
    position();
    card.current?.focus({preventScroll: true});
    const dismissOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !card.current?.contains(event.target) && !anchor.element.contains(event.target)) onClose();
    };
    const dismissKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("pointerdown", dismissOutside);
    document.addEventListener("keydown", dismissKeyboard);
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      resize.disconnect();
      document.removeEventListener("pointerdown", dismissOutside);
      document.removeEventListener("keydown", dismissKeyboard);
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [anchor, onClose]);

  const data = activity.data;
  const online = data?.node_connection_state === "online";
  const syncing = activity.isPending || (online && data?.record_sync_state === "catching_up");
  const confirmed = online && data?.record_sync_state === "current";
  const countsKnown = confirmed && data.running_count !== null && data.waiting_permission_count !== null;
  const mainStatus = !online ? "offline" : confirmed ? data.main_execution : "unknown";
  const active = countsKnown && (data.running_count! > 0 || data.waiting_permission_count! > 0);
  const rows = expanded ? [...new Map([...(data?.sessions ?? []), ...(extra.data?.pages.flatMap(page => page.sessions) ?? [])]
    .map(session => [session.session_id, session])).values()] : [];
  const profile = `/settings/agents/${encodeURIComponent(anchor.agentId)}`;
  const label = (key: string) => t(`chat.agentActivity.${key}`);
  const spinner = <LoaderCircle className="chat-agent-activity-spinner" size={16} role="status" aria-label={label("loading")} />;

  return createPortal(
    <div ref={card} className="chat-agent-activity" role="dialog" aria-labelledby="chat-agent-activity-title" tabIndex={-1}>
      <header className="chat-agent-activity-header">
        <div>
          <h3 id="chat-agent-activity-title">{anchor.name}</h3>
          <span>{label("title")}</span>
        </div>
        {canConfigure && data && !activity.isError && <Link to={`${profile}?view=config`} className="chat-agent-activity-icon"
          aria-label={label("config")} title={label("config")}><Settings size={17} /></Link>}
        <button className="chat-agent-activity-icon" type="button" onClick={onClose}
          aria-label={label("close")}><X size={17} /></button>
      </header>
      {activity.isError ? <div className="chat-agent-activity-error" role="alert">
        {label("unavailable")} <button type="button" onClick={() => void refresh()}>{label("retry")}</button>
      </div> : <>
        <div className="chat-agent-activity-state">
          <div><span>{label("main")}</span>{syncing ? spinner : <strong>{label(mainStatus)}</strong>}</div>
          {confirmed && ["running", "waiting_permission"].includes(mainStatus) && data.latest_tool && <p className="chat-agent-activity-tool">
            <span>{label("latestTool")}</span> <code>{data.latest_tool.name}</code> {data.latest_tool.label}
            <small>{label(data.latest_tool.status || "unknown")}</small>
          </p>}
        </div>
        <div className="chat-agent-activity-children">
          {active ? <button type="button" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
            <span>{label("children")}</span>
            <strong>{t("chat.agentActivity.runningCount", {count: data.running_count!})}</strong>
            {data.waiting_permission_count! > 0 && <span>{t("chat.agentActivity.waitingCount", {count: data.waiting_permission_count!})}</span>}
            <ChevronDown size={15} aria-hidden="true" />
          </button> : <div><span>{label("children")}</span>
            {syncing ? spinner : countsKnown ? <strong>{t("chat.agentActivity.runningCount", {count: 0})}</strong> : <span>{label("unknown")}</span>}
          </div>}
          {expanded && active && <ul>{rows.map(session => <li key={session.session_id}>
            <Link to={`${profile}?view=work&work_session=${encodeURIComponent(session.session_id)}`}>{session.title || session.session_id}</Link>
            <small>{label(session.status)}</small>
          </li>)}</ul>}
          {expanded && active && (extra.data ? extra.hasNextPage : data.next_cursor) && <button type="button" className="chat-agent-activity-more"
            disabled={extra.isFetching} onClick={() => extra.data ? void extra.fetchNextPage() : void extra.refetch()}>{label("more")}</button>}
        </div>
      </>}
      {data && !activity.isError && <footer><Link to={`${profile}?view=work`}>{label("open")}<ArrowUpRight size={16} aria-hidden="true" /></Link></footer>}
    </div>,
    document.body,
  );
}
