import { Link } from 'react-router-dom';
import { useTranslation } from '../../../i18n';
import type { NodeUpdateView } from '../../settings/im-settings-api';
import { nodeUpdateLabel } from '../../settings/nodes/node-update-panel';

interface NodeChipProps {
  nodeName: string | null | undefined;
  status: "online" | "offline";
  nodeId?: string | null;
  update?: NodeUpdateView;
}

/**
 * Compact agent-node presence chip — green dot + node name when online, neutral
 * when offline. Backend node status lives on the agent config (M10 broadcasts
 * updates over WS); this component is purely presentational and gets fed by
 * the chat-workspace page.
 */
export function NodeChip({ nodeName, status, nodeId, update }: NodeChipProps) {
  const {t}=useTranslation();
  if (!nodeName) return null;
  const cls = status === "online" ? "chat-node-chip chat-node-chip--online" : "chat-node-chip";
  const label=nodeUpdateLabel(update);
  const content=(<><span className="chat-node-chip-dot" aria-hidden="true" /><span className="chat-node-chip-name">{nodeName}</span>{label && <span className="shrink-0 text-[11px]">{t(`nodeUpdate.${label}`)} ↗</span>}</>);
  return nodeId && label ? <Link className={cls} to={`/settings/nodes#node-${encodeURIComponent(nodeId)}`}>{content}</Link> : (
    <span className={cls}>
      {content}
    </span>
  );
}
