import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "../../../i18n";

type Props = {
  title: string;
  onRename(title: string): Promise<unknown>;
  onOpenConfig?(): void;
};

export function DirectConversationMenu({ title, onRename, onOpenConfig }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(title);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      await onRename(draft.trim());
      setRenaming(false);
    } catch {
      setError(t("chat.conversationMenu.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="chat-conversation-menu" ref={root}>
      <button
        ref={trigger}
        type="button"
        className="chat-pane-config chat-pane-config-icon"
        aria-label={t("chat.conversationMenu.label")}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" />
        </svg>
      </button>
      {open && (
        <div ref={menu} role="menu" aria-label={t("chat.conversationMenu.label")}
          className="chat-conversation-menu-items" onKeyDown={menuKeyDown}
          onBlur={(event) => {
            if (!root.current?.contains(event.relatedTarget as Node)) setOpen(false);
          }}>
          <button type="button" role="menuitem" onClick={() => {
            setDraft(title); setError(null); setOpen(false); setRenaming(true);
          }}>{t("chat.conversationMenu.rename")}</button>
          {onOpenConfig && <button type="button" role="menuitem" onClick={() => {
            setOpen(false); onOpenConfig();
          }}>{t("chat.conversationMenu.agentConfig")}</button>}
        </div>
      )}
      <Dialog.Root open={renaming} onOpenChange={(next) => { if (!saving) setRenaming(next); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="chat-modal-backdrop" />
          <Dialog.Content className="chat-modal chat-rename-dialog" aria-describedby={undefined}
            onCloseAutoFocus={(event) => { event.preventDefault(); trigger.current?.focus(); }}>
            <form onSubmit={save}>
              <div className="chat-modal-header">
                <Dialog.Title>{t("chat.conversationMenu.renameTitle")}</Dialog.Title>
              </div>
              <div className="chat-modal-body">
                <label htmlFor="conversation-title">{t("chat.conversationMenu.name")}</label>
                <input id="conversation-title" className="group-settings-rename-input" value={draft}
                  disabled={saving} onChange={(event) => setDraft(event.target.value)} />
                {error && <p role="alert" className="group-settings-rename-hint">{error}</p>}
              </div>
              <div className="chat-modal-footer">
                <button type="button" className="chat-modal-btn-ghost" disabled={saving}
                  onClick={() => setRenaming(false)}>{t("chat.groupSettings.cancel")}</button>
                <button type="submit" className="chat-modal-btn-primary" disabled={!draft.trim() || saving}>
                  {saving ? t("chat.conversationMenu.saving") : t("chat.groupSettings.save")}
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
