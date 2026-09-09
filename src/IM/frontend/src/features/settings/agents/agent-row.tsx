import { Avatar, colorForAgent, initialsOf } from "../../chat/components/avatar";
import type { AgentSummary, NodeSummary } from "./im-agent-config-api";

/** Online when the agent's owning node reports online, via the agent's own
 *  node_status first and the nodes table as fallback. */
export function statusOf(agent: AgentSummary, nodes: NodeSummary[]): "online" | "offline" {
  if (agent.node_status === "online") return "online";
  if (agent.node_status === "offline") return "offline";
  if (!agent.node_id) return "offline";
  const node = nodes.find((n) => n.node_id === agent.node_id);
  return node?.status === "online" ? "online" : "offline";
}

/** Device label shown at the row's trailing edge. Same precedence as the
 *  Account page (alias || node_name) so both pages name a node identically;
 *  falls back to node_id when the nodes table lacks the node, and to null
 *  (nothing rendered) when the agent has no owning node. */
export function nodeLabelOf(agent: AgentSummary, nodes: NodeSummary[]): string | null {
  if (!agent.node_id) return null;
  const node = nodes.find((n) => n.node_id === agent.node_id);
  return node ? node.alias || node.node_name : agent.node_id;
}

export interface AgentRowProps {
  agent: AgentSummary;
  /** Nodes table for the device label join and status fallback; may be empty
   *  when the nodes query failed (label falls back to node_id). */
  nodes: NodeSummary[];
  /** While the nodes query is still pending the label slot stays empty —
   *  showing the node_id fallback first would flash before the real name
   *  arrives. */
  nodesPending?: boolean;
  isActive: boolean;
  isMobile: boolean;
  onSelect: (agentId: string) => void;
}

/**
 * Shared agent list row used by every settings agents list (index sidebar and
 * detail/create rail). Single implementation keeps the three lists visually
 * identical; the right edge carries the owning-device label instead of a
 * standalone status dot — presence lives on the avatar badge only.
 */
export function AgentRow({ agent, nodes, nodesPending = false, isActive, isMobile, onSelect }: AgentRowProps) {
  const status = statusOf(agent, nodes);
  const deviceLabel = nodesPending ? null : nodeLabelOf(agent, nodes);

  return (
    <button
      type="button"
      onClick={() => onSelect(agent.agent_id)}
      className={`flex w-full items-center gap-3 rounded-xl border-none text-left font-inherit mb-1 min-h-[52px] transition-colors ${
        isActive ? "outline outline-1" : "outline-none"
      } ${isMobile ? "px-[10px] py-[12px]" : "px-[10px] py-[9px]"} ${
        isActive
          ? ""
          : isMobile
            ? "hover:bg-[var(--im-hover)]"
            : "hover:bg-[var(--im-hover)] focus-visible:bg-[var(--im-hover)]"
      }`}
      style={{
        background: isActive
          ? "var(--im-accent-soft)"
          : undefined,
        outlineColor: isActive
          ? "var(--im-accent-border)"
          : "transparent",
        cursor: "pointer",
      }}
      aria-label={agent.display_name}
      aria-current={isActive ? "page" : undefined}
    >
      <Avatar
        initials={initialsOf(agent.display_name)}
        color={colorForAgent(agent)}
        size={isMobile ? 38 : 32}
        status={status}
      />
      <div className="min-w-0 flex-1">
        <p
          className={`m-0 font-semibold truncate text-im-text ${isMobile ? "text-[15px]" : "text-[13px]"}`}
        >
          {agent.display_name}
        </p>
        <p
          className={`m-0 mt-[2px] truncate text-im-text-muted ${isMobile ? "text-[12.5px]" : "font-mono text-[11px]"}`}
        >
          {isMobile ? agent.description || agent.agent_id : agent.agent_id}
        </p>
      </div>
      {isMobile ? (
        <div className="flex flex-col items-end gap-[3px] shrink-0">
          {deviceLabel ? (
            <span className="text-[12px] text-im-text-muted truncate max-w-[110px]">
              {deviceLabel}
            </span>
          ) : null}
          <span className="text-[11px] text-im-text-muted">›</span>
        </div>
      ) : deviceLabel ? (
        <span
          className="shrink-0 self-end pb-[1px] text-[11px] text-right truncate max-w-[92px] text-im-text-muted"
        >
          {deviceLabel}
        </span>
      ) : null}
    </button>
  );
}
