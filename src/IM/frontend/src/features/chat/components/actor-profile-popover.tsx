import { ArrowUpRight, X } from "lucide-react";
import { useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Link, useInRouterContext } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import { Avatar, colorForAgent, colorForAgentSeed, initialsOf } from "./avatar";
import "./agent-activity-popover.css";

export interface ActorProfileAnchor {
  type: "user" | "agent";
  id: string;
  userId?: string | null;
  name: string;
  role?: "personal";
  avatarVariant?: number | null;
  isSelf?: boolean;
  canConfigure?: boolean;
  element: HTMLElement;
}

export function ActorProfilePopover({
  anchor,
  onClose,
}: {
  anchor: ActorProfileAnchor;
  onClose(): void;
}) {
  const { t } = useTranslation();
  const inRouter = useInRouterContext();
  const card = useRef<HTMLDivElement>(null);

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
    const resize = typeof ResizeObserver !== "undefined" ? new ResizeObserver(position) : null;
    if (resize && card.current) resize.observe(card.current);
    position();
    card.current?.focus({ preventScroll: true });
    const dismissOutside = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !card.current?.contains(event.target) &&
        !anchor.element.contains(event.target)
      ) {
        onClose();
      }
    };
    const dismissKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        anchor.element.focus({ preventScroll: true });
      }
    };
    document.addEventListener("pointerdown", dismissOutside);
    document.addEventListener("keydown", dismissKeyboard, true);
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      resize?.disconnect();
      document.removeEventListener("pointerdown", dismissOutside);
      document.removeEventListener("keydown", dismissKeyboard, true);
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [anchor, onClose]);

  const isAgent = anchor.type === "agent";
  const isPersonal = isAgent && (anchor.role === "personal" || anchor.id.startsWith("pa_"));
  const roleLabel = isAgent
    ? isPersonal
      ? t("pa.label")
      : t("chat.actorCard.agent")
    : t("chat.actorCard.member");
  const footerHref =
    inRouter && isAgent && anchor.canConfigure
      ? `/settings/agents/${encodeURIComponent(anchor.id)}`
      : inRouter && !isAgent && anchor.isSelf
        ? "/settings/account"
        : null;
  const footerLabel = isAgent ? t("chat.agentActivity.config") : t("chat.actorCard.openAccount");

  return createPortal(
    <div
      ref={card}
      className="chat-agent-activity chat-actor-card"
      role="dialog"
      aria-labelledby="chat-actor-card-title"
      tabIndex={-1}
    >
      <header className="chat-agent-activity-header chat-actor-card-header">
        <Avatar
          size={36}
          personal={isPersonal}
          agentId={isAgent ? anchor.id : undefined}
          avatarVariant={anchor.avatarVariant}
          initials={initialsOf(anchor.name)}
          color={
            isAgent
              ? colorForAgent({ display_name: anchor.name, agent_id: anchor.id })
              : colorForAgentSeed(anchor.name)
          }
        />
        <div>
          <div className="chat-actor-card-title-row">
            <h3 id="chat-actor-card-title">{anchor.name}</h3>
            {anchor.isSelf && <em className="chat-actor-card-self">{t("chat.groupSettings.self")}</em>}
          </div>
          <span>{roleLabel}</span>
        </div>
        <button
          className="chat-agent-activity-icon"
          type="button"
          onClick={() => {
            onClose();
            anchor.element.focus({ preventScroll: true });
          }}
          aria-label={t("chat.agentActivity.close")}
        >
          <X size={17} />
        </button>
      </header>
      <dl className="chat-agent-activity-computer chat-actor-card-id">
        <dt>{t("chat.actorCard.idLabel")}</dt>
        <dd>
          <code>{anchor.id}</code>
        </dd>
      </dl>
      {footerHref && (
        <footer>
          <Link to={footerHref} onClick={onClose}>
            {footerLabel}
            <ArrowUpRight size={16} aria-hidden="true" />
          </Link>
        </footer>
      )}
    </div>,
    document.body,
  );
}
