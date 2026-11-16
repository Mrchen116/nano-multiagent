import { PropsWithChildren, ReactNode } from "react";
import { Link } from 'react-router-dom';

import { ProductHeader } from "../home/product-header";
import { useTranslation } from "../../i18n";

type AuthPageFrameProps = PropsWithChildren<{
  intent?: 'login' | 'register' | 'membership';
  kicker: string;
  title: string;
  subtitle: string;
  footer: ReactNode;
}>;

/** Present authentication as the next step in the public product journey. */
export function AuthPageFrame({ kicker, title, subtitle, footer, children, intent = 'membership' }: AuthPageFrameProps) {
  const { t } = useTranslation();
  return <div className="im-auth-screen product-entry">
    <ProductHeader page={intent} />
    <main className="im-auth-main">
      <section className="im-auth-context" aria-labelledby="auth-context-title">
        <p className="im-auth-eyebrow"><span />{t('publicHome.eyebrow')}</p>
        <h2 id="auth-context-title">{t('publicHome.titleBefore')}<em>{t('publicHome.titleAccent')}</em>{t('publicHome.titleAfter')}</h2>
        <p className="im-auth-context-copy">{t(`auth.context.${intent === 'login' ? 'returning' : 'body'}`)}</p>
        <ol className="im-auth-story">{['human', 'personal', 'specialist'].map((key, i) => <li key={key}>
          <span aria-hidden="true">0{i + 1}</span><div><strong>{t(`publicHome.concepts.${key}.title`)}</strong><p>{t(`auth.context.${key}`)}</p></div>
        </li>)}</ol>
        <Link className="im-auth-product-link" to="/about">← {t('auth.context.back')}</Link>
      </section>
      <section className="im-auth-card" aria-labelledby="auth-form-title">
        <header className="im-auth-header">
          <div className="im-auth-kicker">{kicker}</div>
          <h1 id="auth-form-title">{title}</h1>
          <p>{subtitle}</p>
        </header>
        {children}
        <footer className="im-auth-footer">{footer}</footer>
        {intent === 'register' && <p className="im-auth-requirements">{t('auth.context.requirements')}</p>}
      </section>
    </main>
    <footer className="im-auth-bottom"><span>{t('publicHome.footer')}</span><Link to="/about#getting-started">{t('publicHome.nav.start')} ↗</Link></footer>
  </div>;
}

export function AuthAlert({ children, id }: PropsWithChildren<{ id?: string }>) {
  return <p id={id} role="alert" className="im-auth-alert">{children}</p>;
}

export function SubmitArrow() {
  return (
    <LineIcon>
      <path d="M5 12h14m-5-5 5 5-5 5" />
    </LineIcon>
  );
}

function LineIcon({ children }: PropsWithChildren) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}
