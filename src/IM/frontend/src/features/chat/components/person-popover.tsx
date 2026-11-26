import { ArrowUpRight, MessageSquare, X } from "lucide-react";
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";

import { useTranslation } from "../../../i18n";
import type { Contact } from "../contacts-api";
import { Avatar } from "./avatar";
import "./person-popover.css";

export interface PersonPopoverAnchor {
  userId: string;
  element: HTMLElement;
}

export interface PersonPopoverProps {
  anchor: PersonPopoverAnchor;
  contact: Contact;
  contacts: Contact[];
  canMention?: boolean;
  onMessage(contact: Contact): Promise<void> | void;
  onMention?(contact: Contact): void;
  onClose(): void;
}

/**
 * Contextual colleague card mirroring AgentActivityPopover so clicking a human
 * avatar, @mention chip, or group member row reveals identity, linked PA /
 * specialist Agents, and 1-click direct chat without leaving the conversation.
 */
export function PersonPopover({
  anchor,
  contact,
  contacts,
  canMention = false,
  onMessage,
  onMention,
  onClose
}: PersonPopoverProps) {
  const { t } = useTranslation();
  const card = useRef<HTMLDivElement>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState(false);

  const { publicPa, specialistAgents } = useMemo(() => {
    const owned = contacts.filter(
      (c) => c.kind === "agent" && (c.owner_user_id ?? c.owner_id) === contact.user_id
    );
    return {
      publicPa: owned.find((c) => c.role === "personal"),
      specialistAgents: owned.filter((c) => c.role !== "personal" && Boolean(c.agent_id))
    };
  }, [contacts, contact.user_id]);

  useLayoutEffect(() => {
    const position = () => {
      if (!anchor.element.isConnected) return;
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
    if (card.current && resize) resize.observe(card.current);
    position();
    card.current?.focus({ preventScroll: true });

    const dismissOutside = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (card.current?.contains(target) || anchor.element.contains(target)) return;
      // Swallow a backdrop/scrim click that only meant to dismiss this popover
      // so GroupSettings drawer stays open underneath.
      if (target instanceof HTMLElement && (target.classList.contains("group-settings-scrim") || target.classList.contains("chat-modal-backdrop"))) {
        const swallowClick = (clickEvent: MouseEvent) => {
          clickEvent.stopPropagation();
          clickEvent.preventDefault();
          document.removeEventListener("click", swallowClick, true);
        };
        document.addEventListener("click", swallowClick, true);
        window.setTimeout(() => document.removeEventListener("click", swallowClick, true), 250);
      }
      onClose();
    };
    const dismissKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
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

  async function handleStartChat(target: Contact) {
    if (busyId) return;
    setBusyId(target.user_id);
    setError(false);
    try {
      await onMessage(target);
      onClose();
    } catch {
      setError(true);
    } finally {
      setBusyId(null);
    }
  }

  return createPortal(
    <div
      ref={card}
      className="chat-person-popover"
      role="dialog"
      aria-labelledby="chat-person-popover-title"
      tabIndex={-1}
      onClick={(e) => e.stopPropagation()}
    >
      <header className="chat-person-popover-header">
        <Avatar id={contact.user_id} size={38} />
        <div className="chat-person-popover-identity">
          <h3 id="chat-person-popover-title">{contact.display_name}</h3>
          <span>{contact.username ? `@${contact.username}` : t("chat.personPopover.colleague")}</span>
        </div>
        <button
          type="button"
          className="chat-person-popover-close"
          onClick={onClose}
          aria-label={t("chat.personPopover.close")}
        >
          <X size={16} />
        </button>
      </header>

      {publicPa && (
        <div className="chat-person-popover-section">
          <span className="chat-person-popover-label">{t("chat.personPopover.personalAssistant")}</span>
          <button
            type="button"
            className="chat-person-popover-agent"
            disabled={busyId !== null}
            onClick={() => void handleStartChat(publicPa)}
          >
            <Avatar id={publicPa.user_id} size={24} status={publicPa.status} />
            <span className="chat-person-popover-agent-name">{publicPa.display_name}</span>
            <span className="chat-person-popover-agent-action">
              <MessageSquare size={13} aria-hidden="true" />
              {t("chat.personPopover.message")}
            </span>
          </button>
        </div>
      )}

      {specialistAgents.length > 0 && (
        <div className="chat-person-popover-section">
          <span className="chat-person-popover-label">{t("chat.personPopover.managedAgents")}</span>
          <ul className="chat-person-popover-agents">
            {specialistAgents.map((agent) => (
              <li key={agent.user_id}>
                <Link
                  to={`/settings/agents/${encodeURIComponent(agent.agent_id!)}`}
                  className="chat-person-popover-agent"
                  onClick={onClose}
                >
                  <Avatar id={agent.user_id} size={24} status={agent.status} />
                  <span className="chat-person-popover-agent-name">{agent.display_name}</span>
                  <span className="chat-person-popover-agent-action">
                    <ArrowUpRight size={14} aria-hidden="true" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <p className="chat-person-popover-error" role="alert">
          {t("chat.personPopover.failed")}
        </p>
      )}

      <footer className="chat-person-popover-actions">
        <button
          type="button"
          className="chat-person-popover-btn chat-person-popover-btn--primary"
          disabled={busyId !== null}
          onClick={() => void handleStartChat(contact)}
        >
          <MessageSquare size={14} aria-hidden="true" />
          {t("chat.personPopover.message")}
        </button>
        {canMention && onMention && (
          <button
            type="button"
            className="chat-person-popover-btn"
            disabled={busyId !== null}
            onClick={() => {
              onMention(contact);
              onClose();
            }}
          >
            {t("chat.personPopover.mention")}
          </button>
        )}
      </footer>
    </div>,
    document.body
  );
}
