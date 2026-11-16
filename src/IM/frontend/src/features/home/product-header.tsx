import { Link } from 'react-router-dom';
import { NanoBrand } from '../../app/shell/nano-brand';
import { getCurrentLanguage, setLanguage, useTranslation } from '../../i18n';
import './product-entry.css';

/** Keep the product identity and navigation continuous through first use. */
export function ProductHeader({ page = 'home', accountName }: {
  page?: 'home' | 'login' | 'register' | 'setup' | 'membership';
  accountName?: string;
}) {
  const { t } = useTranslation();
  const zh = getCurrentLanguage() === 'zh';
  return <header className={`product-header product-header--${page}`}>
    <Link to="/about" className="product-brand" aria-label={t('publicHome.home')}><NanoBrand /></Link>
    {page !== 'setup' && page !== 'membership' && <nav className="product-nav" aria-label={t('publicHome.navigation')}>
      <a href="/about#how-it-works">{t('publicHome.nav.how')}</a>
      <a href="/about#your-space">{t('publicHome.nav.space')}</a>
      <a href="/about#getting-started">{t('publicHome.nav.start')}</a>
    </nav>}
    <div className="product-header-actions">
      <div className="product-language" role="group" aria-label={t('auth.language.label')}>
        <button type="button" role="radio" aria-checked={zh} onClick={() => setLanguage('zh')}>中</button>
        <span aria-hidden="true">/</span>
        <button type="button" role="radio" aria-checked={!zh} onClick={() => setLanguage('en')}>EN</button>
      </div>
      {page === 'setup' ? <Link className="product-account" to="/settings/account">{accountName}</Link>
        : page !== 'membership' && <>
          {page === 'home' && <Link className="product-signin" to="/login">{t('publicHome.signIn')}</Link>}
          <Link className="product-header-button" to={page === 'register' ? '/login' : '/register'}>
            {t(page === 'register' ? 'publicHome.signIn' : page === 'login' ? 'auth.login.registerLink' : 'publicHome.start')}
          </Link>
        </>}
    </div>
  </header>;
}
