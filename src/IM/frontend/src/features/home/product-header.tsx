import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { NanoBrand } from '../../app/shell/nano-brand';
import { useTranslation } from '../../i18n';
import { LanguageSelect } from '../../app/shell/language-select';
import { accountEnabled, useAuthStore } from '../auth/auth-store';
import './product-entry.css';

/** Separate product exploration from the focused account and setup journeys. */
export function ProductHeader({ page = 'home', accountName }: {
  page?: 'home' | 'login' | 'register' | 'setup' | 'membership';
  accountName?: string;
}) {
  const { t } = useTranslation();
  const user = useAuthStore(s => s.user);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sections = [['download', 'download'], ['teamwork', 'team'], ['how-it-works', 'how'], ['getting-started', 'start']] as const;
  const workspacePath = user && accountEnabled(user) ? '/chat' : '/membership';
  return <header className={`product-header product-header--${page}`} onKeyDown={event => {
    if (event.key === 'Escape' && menuOpen) { setMenuOpen(false); menuButton.current?.focus(); }
  }}>
    <Link to="/about" className="product-brand" aria-label={t('publicHome.home')}><NanoBrand /></Link>
    {page === 'home' && <nav className="product-nav" aria-label={t('publicHome.navigation')}>
      {sections.map(([id, key]) => <a key={id} href={`#${id}`}>{t(`crewdenStory.nav.${key}`)}</a>)}
    </nav>}
    <div className="product-header-actions">
      <LanguageSelect />
      {page === 'setup' ? <Link className="product-account" to="/settings/account">{accountName}</Link>
        : page === 'home' ? <>
          {user ? <Link className="product-header-button" to={workspacePath}>{t('crewdenDownload.openWorkspace')}</Link> : <>
            <Link className="product-signin" to="/login">{t('auth.login.submit')}</Link>
            <Link className="product-header-button" to="/register">{t('auth.register.submit')}</Link>
          </>}
          <button ref={menuButton} className="product-menu-trigger" type="button" aria-label={t(menuOpen ? 'crewdenStory.nav.menuClose' : 'crewdenStory.nav.menu')} aria-expanded={menuOpen} aria-controls={menuOpen ? 'product-mobile-nav' : undefined} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
        </> : null}
    </div>
    {page === 'home' && menuOpen && <nav id="product-mobile-nav" className="product-mobile-nav" aria-label={t('publicHome.navigation')} onClick={() => setMenuOpen(false)}>
      {sections.map(([id, key]) => <a key={id} href={`#${id}`}>{t(`crewdenStory.nav.${key}`)}</a>)}
      {user ? <Link className="product-mobile-register" to={workspacePath}>{t('crewdenDownload.openWorkspace')}</Link> : <>
        <Link to="/login">{t('auth.login.submit')}</Link>
        <Link className="product-mobile-register" to="/register">{t('auth.register.submit')}</Link>
      </>}
    </nav>}
  </header>;
}
