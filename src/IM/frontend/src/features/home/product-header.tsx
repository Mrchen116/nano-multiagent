import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Globe2, Menu, X } from 'lucide-react';
import { NanoBrand } from '../../app/shell/nano-brand';
import { getCurrentLanguage, setLanguage, useTranslation } from '../../i18n';
import './product-entry.css';

/** Separate product exploration from the focused account and setup journeys. */
export function ProductHeader({ page = 'home', accountName }: {
  page?: 'home' | 'login' | 'register' | 'setup' | 'membership';
  accountName?: string;
}) {
  const { t } = useTranslation();
  const zh = getCurrentLanguage() === 'zh';
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sections = [['how-it-works', 'how'], ['capabilities', 'capabilities'], ['getting-started', 'start']] as const;
  return <header className={`product-header product-header--${page}`} onKeyDown={event => {
    if (event.key === 'Escape' && menuOpen) { setMenuOpen(false); menuButton.current?.focus(); }
  }}>
    <Link to="/about" className="product-brand" aria-label={t('publicHome.home')}><NanoBrand /></Link>
    {page === 'home' && <nav className="product-nav" aria-label={t('publicHome.navigation')}>
      {sections.map(([id, key]) => <a key={id} href={`#${id}`}>{t(`crewdenStory.nav.${key}`)}</a>)}
    </nav>}
    <div className="product-header-actions">
      <label className="product-language-select">
        <Globe2 aria-hidden="true" />
        <select aria-label={t('auth.language.label')} value={zh ? 'zh' : 'en'} onChange={event => setLanguage(event.target.value === 'zh' ? 'zh' : 'en')}>
          <option value="en">English</option><option value="zh">简体中文</option>
        </select>
        <ChevronDown className="product-language-chevron" aria-hidden="true" />
      </label>
      {page === 'setup' ? <Link className="product-account" to="/settings/account">{accountName}</Link>
        : page === 'home' ? <>
          <Link className="product-signin" to="/login">{t('auth.login.submit')}</Link>
          <Link className="product-header-button" to="/register">{t('auth.register.submit')}</Link>
          <button ref={menuButton} className="product-menu-trigger" type="button" aria-label={t(menuOpen ? 'crewdenStory.nav.menuClose' : 'crewdenStory.nav.menu')} aria-expanded={menuOpen} aria-controls={menuOpen ? 'product-mobile-nav' : undefined} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
        </> : <Link className="product-back-home" to="/about">{t('crewdenStory.nav.home')}</Link>}
    </div>
    {page === 'home' && menuOpen && <nav id="product-mobile-nav" className="product-mobile-nav" aria-label={t('publicHome.navigation')} onClick={() => setMenuOpen(false)}>
      {sections.map(([id, key]) => <a key={id} href={`#${id}`}>{t(`crewdenStory.nav.${key}`)}</a>)}
      <Link to="/login">{t('auth.login.submit')}</Link>
      <Link className="product-mobile-register" to="/register">{t('auth.register.submit')}</Link>
    </nav>}
  </header>;
}
