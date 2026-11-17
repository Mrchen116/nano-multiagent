import { PropsWithChildren, ReactNode } from 'react';
import { ProductHeader } from '../home/product-header';
import { AuthScene } from './auth-scene';
import './auth-page.css';

type AuthPageFrameProps = PropsWithChildren<{
  intent?: 'login' | 'register' | 'membership';
  title: string;
  subtitle: string;
  footer: ReactNode;
}>;

/** Keep account actions focused, with the same identity and clear route back to the product. */
export function AuthPageFrame({ title, subtitle, footer, children, intent = 'membership' }: AuthPageFrameProps) {
  return <div className={`crew-account crew-account--${intent} product-entry`}>
    <ProductHeader page={intent} />
    <main className="crew-account-main">
      <div className="crew-account-shell">
        <AuthScene />
        <div className="crew-account-form-region">
          <section className="crew-account-panel" aria-labelledby="auth-form-title">
            <header className="crew-account-heading">
              <h1 id="auth-form-title">{title}</h1>
              <p>{subtitle}</p>
            </header>
            {children}
            {footer && <footer className="im-auth-footer">{footer}</footer>}
          </section>
        </div>
      </div>
    </main>
  </div>;
}

export function AuthAlert({ children, id }: PropsWithChildren<{ id?: string }>) {
  return <p id={id} role="alert" className="im-auth-alert">{children}</p>;
}
