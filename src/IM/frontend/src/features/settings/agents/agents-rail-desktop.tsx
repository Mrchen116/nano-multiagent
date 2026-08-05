import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { colorForAgent } from "../../chat/components/avatar";
import { listAgentSummaries } from "./im-agent-config-api";

function initialsOf(displayName: string): string {
  const trimmed = displayName.trim();
  if (!trimmed) return "AG";
  return trimmed.slice(0, 2).toUpperCase();
}

interface AgentsRailDesktopProps {
  activeId?: string;
  isCreatePage?: boolean;
  onSelectAgent?: (agentId: string) => void;
}

// Shared by agent detail and create pages so their wide-screen navigation stays identical.
export function AgentsRailDesktop({ activeId, isCreatePage = false, onSelectAgent }: AgentsRailDesktopProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["settings", "agents"], queryFn: listAgentSummaries, staleTime: 30_000 });
  const agents = query.data ?? [];

  function selectAgent(agentId: string) {
    if (onSelectAgent) {
      onSelectAgent(agentId);
      return;
    }
    navigate(`/settings/agents/${agentId}`);
  }

  return (
    <aside
      data-testid="agents-rail-desktop"
      className="hidden lg:flex lg:w-[240px] lg:flex-col lg:border-r lg:border-[oklch(0.29_0.010_240)]"
      style={{ background: "oklch(0.24 0.012 240)" }}
      aria-label={t("agents.title")}
    >
      <div className="flex items-center justify-between px-3 py-[10px] border-b border-[oklch(0.29_0.010_240)]">
        <span className="text-[11px] font-bold tracking-[0.08em] uppercase text-[oklch(0.55_0.01_240)]">
          {t("agents.title")}
        </span>
        {isCreatePage ? (
          <button
            className="inline-flex h-9 items-center rounded-lg border-0 px-3 text-[13px] font-semibold text-white"
            style={{ background: "oklch(0.30 0.012 240)", cursor: "default" }}
            type="button"
            disabled
            aria-current="page"
          >
            {t("agents.newButton")}
          </button>
        ) : (
          <Link
            to="/settings/agents/new"
            className="inline-flex h-9 items-center rounded-lg px-3 text-[13px] font-semibold text-white"
            style={{ background: "oklch(0.30 0.012 240)" }}
          >
            {t("agents.newButton")}
          </Link>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-[6px]" aria-label={t("agents.title")}>
        {agents.map((agent) => {
          const active = agent.agent_id === activeId;
          const online = agent.node_status === "online";
          return (
            <button
              key={agent.agent_id}
              type="button"
              onClick={() => selectAgent(agent.agent_id)}
              className={`flex w-full items-center gap-3 rounded-xl border-none text-left font-inherit mb-1 min-h-[52px] px-[10px] py-[9px] transition-colors ${
                active ? "outline outline-1 outline-[oklch(0.40_0.08_180)]" : "outline-none"
              }`}
              style={{
                background: active ? "oklch(0.31 0.015 240)" : "transparent",
                cursor: "pointer"
              }}
              onMouseEnter={(event) => {
                if (!active) event.currentTarget.style.background = "oklch(0.28 0.012 240)";
              }}
              onMouseLeave={(event) => {
                if (!active) event.currentTarget.style.background = "transparent";
              }}
              aria-current={active ? "page" : undefined}
            >
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] font-bold text-white"
                style={{ background: colorForAgent(agent) }}
                aria-hidden="true"
              >
                {initialsOf(agent.display_name)}
              </span>
              <div className="min-w-0 flex-1">
                <p className={`m-0 text-[13px] font-semibold truncate ${active ? "text-white" : "text-[oklch(0.18_0.01_240)]"}`}>
                  {agent.display_name}
                </p>
                <p className="m-0 mt-[2px] font-mono text-[11px] text-[oklch(0.50_0.01_240)] truncate">
                  {agent.agent_id}
                </p>
              </div>
              <span
                className="inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ background: online ? "oklch(0.55 0.18 145)" : "oklch(0.45 0.01 240)" }}
                aria-label={online ? "online" : "offline"}
              />
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
