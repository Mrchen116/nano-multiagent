import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getCurrentLanguage, setLanguage, useTranslation, type Locale } from "../../i18n";
import { useAuthStore } from "../../features/auth/auth-store";
import { listNodes } from "../../features/settings/im-settings-api";
import { Avatar, colorForAgentSeed, initialsOf } from "../../features/chat/components/avatar";
import { UserMenuIcon } from "./user-menu-icons";

/** Keep account and workspace preferences in one place beside desktop navigation. */
export function UserMenu() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [languageOpen, setLanguageOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const lang = getCurrentLanguage();
  const nodesQuery = useQuery({ queryKey: ["settings", "nodes"], queryFn: listNodes, staleTime: 30_000 });
  const ownedNodes = (nodesQuery.data ?? []).filter((n) => user?.owned_node_ids?.includes(n.node_id));
  const onlineCount = ownedNodes.filter((n) => n.status === "online").length;

  useEffect(() => {
    if (!open) return;
    const onDocClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setOpen(false); triggerRef.current?.focus(); }
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;
  const name = user.display_name || user.username;
  const avatar = <Avatar initials={initialsOf(name)} color={colorForAgentSeed(name)} size={36} />;
  const handleLanguage = (next: Locale) => { setLanguage(next); setOpen(false); triggerRef.current?.focus(); };
  const close = () => setOpen(false);

  return <div ref={containerRef} className="im-user-menu">
    <button ref={triggerRef} type="button" aria-label={name} title={name} aria-haspopup="menu" aria-expanded={open}
      onClick={() => { setLanguageOpen(false); setOpen(previous => !previous); }} className="im-user-menu-trigger">
      {avatar}
    </button>
    {open && <div role="menu" aria-label={name} className="im-user-menu-popover">
      <div className="im-user-menu-identity" role="none">
        {avatar}
        <div><strong>{name}</strong><span>@{user.username}</span></div>
      </div>
      <Link role="menuitem" to="/settings/account" onClick={close} className="im-user-menu-item">
        <UserMenuIcon kind="account" /><span>{t('shell.userMenu.account')}</span><span aria-hidden>›</span>
      </Link>
      <div className="im-user-menu-section" role="group" aria-label={t('shell.userMenu.nodes')}>
        <Link role="menuitem" to="/settings/nodes" onClick={close} className="im-user-menu-item">
          <UserMenuIcon kind="nodes" /><span>{t('shell.userMenu.nodes')}</span>
          {!nodesQuery.isPending && !nodesQuery.isError && <small>{onlineCount} {t('common.online')}</small>}
        </Link>
        <Link role="menuitem" to="/settings/models" onClick={close} className="im-user-menu-item">
          <UserMenuIcon kind="models" /><span>{lang === 'zh' ? '模型服务' : 'Model services'}</span><span aria-hidden>›</span>
        </Link>
      </div>
      {user.membership_status === 'active' && <div className="im-user-menu-section" role="group" aria-label={t('shell.userMenu.policies')}>
        <Link role="menuitem" to="/settings/policies" onClick={close} className="im-user-menu-item">
          <UserMenuIcon kind="policies" /><span>{t('shell.userMenu.policies')}</span><span aria-hidden>›</span>
        </Link>
        {user.is_company_admin && <Link role="menuitem" to="/settings/company" onClick={close} className="im-user-menu-item">
          <UserMenuIcon kind="members" /><span>{t('company.title')}</span><span aria-hidden>›</span>
        </Link>}
      </div>}
      <div className="im-user-menu-language">
        <button type="button" role="menuitem" className="im-user-menu-item" aria-expanded={languageOpen} aria-controls="account-languages" onClick={() => setLanguageOpen(previous => !previous)}>
          <UserMenuIcon kind="language" /><span>{t('shell.userMenu.language')}</span>
          <small>{lang === 'zh' ? '简体中文' : 'English'}</small><span aria-hidden>{languageOpen ? '⌄' : '›'}</span>
        </button>
        {languageOpen && <div id="account-languages" role="group" aria-label={t('shell.userMenu.language')} className="im-user-menu-lang-options">
          <button type="button" role="menuitemradio" aria-checked={lang === 'en'} onClick={() => handleLanguage('en')}>English<span aria-hidden>{lang === 'en' ? '✓' : ''}</span></button>
          <button type="button" role="menuitemradio" aria-checked={lang === 'zh'} onClick={() => handleLanguage('zh')}>简体中文<span aria-hidden>{lang === 'zh' ? '✓' : ''}</span></button>
        </div>}
      </div>
      <button role="menuitem" type="button" onClick={() => {
        // Let dirty forms confirm navigation before LoginPage clears the session.
        navigate('/login', { replace: true, state: { signOut: true } });
      }} className="im-user-menu-item im-user-menu-signout"><UserMenuIcon kind="logout" /><span>{t('shell.userMenu.signOut')}</span></button>
    </div>}
  </div>;
}
