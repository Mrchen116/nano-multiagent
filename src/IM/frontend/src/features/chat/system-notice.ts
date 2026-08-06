import type { TFunction } from "i18next";

import type { SystemNotice } from "./chat-types";

/** Format a recognized notice using browser locale; null keeps stored-text fallback. */
export function formatSystemNotice(
  t: TFunction,
  notice: SystemNotice | null | undefined,
  isDirectChat: boolean,
): string | null {
  if (
    notice?.kind !== "self_evolution_review" ||
    !notice.source_agent_id.trim() ||
    !notice.source_agent_display_name.trim() ||
    !Array.isArray(notice.updated_targets) ||
    notice.updated_targets.length < 1 ||
    notice.updated_targets.length > 2
  ) {
    return null;
  }
  const targets = new Set(notice.updated_targets);
  if (
    targets.size !== notice.updated_targets.length ||
    [...targets].some((target) => target !== "skills" && target !== "memory")
  ) {
    return null;
  }
  const variant = targets.size === 2
    ? "both"
    : targets.has("skills")
      ? "skills"
      : "memory";
  const chatKind = isDirectChat ? "direct" : "group";
  return t(`chat.messagePane.systemNotice.${chatKind}.${variant}`, {
    agent: notice.source_agent_display_name,
  });
}
