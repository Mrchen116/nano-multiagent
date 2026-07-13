interface NodeChipProps {
  nodeName: string | null | undefined;
  status: "online" | "offline";
}

/**
 * Compact agent-node presence chip — green dot + node name when online, neutral
 * when offline. Backend node status lives on the agent config (M10 broadcasts
 * updates over WS); this component is purely presentational and gets fed by
 * the chat-workspace page.
 */
export function NodeChip({ nodeName, status }: NodeChipProps) {
  if (!nodeName) return null;
  const cls = status === "online" ? "chat-node-chip chat-node-chip--online" : "chat-node-chip";
  return (
    <span className={cls}>
      <span className="chat-node-chip-dot" aria-hidden="true" />
      <span className="chat-node-chip-name">{nodeName}</span>
    </span>
  );
}
