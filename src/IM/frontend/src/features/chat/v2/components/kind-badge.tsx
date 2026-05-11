import { useTranslation } from "../../../../i18n";
import type { ConversationKind } from "../chat-types";

const VARIANT: Record<ConversationKind, string> = {
  "direct-agent": "chat-kind-agent",
  "direct-user": "chat-kind-direct-user",
  group: "chat-kind-group",
  "agent-network": "chat-kind-network"
};

const LABEL_KEY: Record<ConversationKind, string> = {
  "direct-agent": "chat.kindBadge.agent",
  "direct-user": "chat.kindBadge.direct-user",
  group: "chat.kindBadge.group",
  "agent-network": "chat.kindBadge.network"
};

export function KindBadge({ kind }: { kind: ConversationKind }) {
  const { t } = useTranslation();
  return <span className={`chat-kind-badge ${VARIANT[kind]}`}>{t(LABEL_KEY[kind])}</span>;
}
