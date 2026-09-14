import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "../../../i18n";

/** A single creation entry keeps both chat actions reachable on narrow screens. */
export function NewConversationMenu({ onNewChat, onNewGroup }: {
  onNewChat?(): void;
  onNewGroup(): void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);

  function menuKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      trigger.current?.focus();
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const items = Array.from(menu.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
      const index = items.indexOf(document.activeElement as HTMLButtonElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
        : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items[next]?.focus();
    }
  }

  function select(action: () => void) {
    setOpen(false);
    trigger.current?.focus();
    action();
  }

  return <div ref={root} className="chat-sidebar-create">
    <button ref={trigger} type="button" className="chat-sidebar-create-trigger"
      aria-label={t("chat.list.createConversation")} title={t("chat.list.createConversation")}
      aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
        strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
    </button>
    {open && <div ref={menu} role="menu" aria-label={t("chat.list.createConversation")}
      className="chat-conversation-menu-items" onKeyDown={menuKeyDown}
      onBlur={event => { if (!root.current?.contains(event.relatedTarget as Node)) setOpen(false); }}>
      {onNewChat && <button type="button" role="menuitem" onClick={() => select(onNewChat)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z" />
        </svg>
        {t("chat.contacts.title")}
      </button>}
      <button type="button" role="menuitem" onClick={() => select(onNewGroup)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="9" cy="8" r="4" /><path d="M2 21v-2a7 7 0 0 1 14 0v2m1-17a4 4 0 0 1 0 8m5 9v-2a7 7 0 0 0-4-6" />
        </svg>
        {t("chat.list.newGroup")}
      </button>
    </div>}
  </div>;
}
