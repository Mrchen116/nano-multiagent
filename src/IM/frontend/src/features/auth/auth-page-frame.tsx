import { PropsWithChildren, ReactNode } from "react";

import { NanoBrand } from "../../app/shell/nano-brand";
import { getCurrentLanguage, setLanguage, useTranslation } from "../../i18n";

type AuthPageFrameProps = PropsWithChildren<{
  kicker: string;
  title: string;
  subtitle: string;
  footer: ReactNode;
}>;

export function AuthPageFrame({ kicker, title, subtitle, footer, children }: AuthPageFrameProps) {
  const { t } = useTranslation();
  const language = getCurrentLanguage();
  return (
    <div className="im-auth-screen">
      <header className="im-auth-topbar">
        <NanoBrand className="im-auth-brand" />
        <div className="im-auth-language" role="group" aria-label={t("auth.language.label")}>
          <button
            type="button"
            role="radio"
            aria-checked={language === "en"}
            onClick={() => setLanguage("en")}
          >
            EN
          </button>
          <span aria-hidden="true">|</span>
          <button
            type="button"
            role="radio"
            aria-checked={language === "zh"}
            onClick={() => setLanguage("zh")}
          >
            中
          </button>
        </div>
      </header>
      <main className="im-auth-main">
        <section className="im-auth-context" aria-labelledby="auth-context-title">
          <p className="im-auth-eyebrow">{t("auth.context.eyebrow")}</p>
          <h1 id="auth-context-title">{t("auth.context.title")}</h1>
          <p className="im-auth-context-copy">{t("auth.context.body")}</p>
          <div className="im-auth-capabilities">
            <Capability icon="people" label={t("auth.context.people")} />
            <Capability icon="agents" label={t("auth.context.agents")} />
            <Capability icon="devices" label={t("auth.context.devices")} />
          </div>
        </section>
        <section className="im-auth-card" aria-labelledby="auth-form-title">
          <header className="im-auth-header">
            <div className="im-auth-kicker">
              <EnterIcon />
              <span>{kicker}</span>
            </div>
            <h2 id="auth-form-title">{title}</h2>
            <p>{subtitle}</p>
          </header>
          {children}
          <footer className="im-auth-footer">{footer}</footer>
        </section>
      </main>
    </div>
  );
}

function Capability({ icon, label }: { icon: "people" | "agents" | "devices"; label: string }) {
  return (
    <div className="im-auth-capability">
      <CapabilityIcon name={icon} />
      <span>{label}</span>
    </div>
  );
}

function CapabilityIcon({ name }: { name: "people" | "agents" | "devices" }) {
  if (name === "people") {
    return (
      <LineIcon>
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
      </LineIcon>
    );
  }
  if (name === "agents") {
    return (
      <LineIcon>
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <path d="m8 12 2.5 2.5L16 9" />
      </LineIcon>
    );
  }
  return (
    <LineIcon>
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8m-4-4v4" />
    </LineIcon>
  );
}

function EnterIcon() {
  return (
    <LineIcon>
      <path d="M12 5v14m-6-6 6 6 6-6" />
    </LineIcon>
  );
}

export function AuthAlert({ children }: PropsWithChildren) {
  return (
    <div role="alert" className="im-auth-alert">
      <LineIcon>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v5m0 3h.01" />
      </LineIcon>
      <span>{children}</span>
    </div>
  );
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
