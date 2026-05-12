import { Link, useNavigate } from "react-router-dom";

import { getCurrentLanguage, setLanguage, useTranslation, type Locale } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { ensureNotificationPermission } from "../notifications/notification-api";
import { useNotificationPreference } from "../notifications/notification-preference";

// M19/R11-1: Mobile Me 页按 prototype `im-mypage.jsx::AggregatedMePage` 重写。
// 旧版用未定义的 im-me-* CSS 类导致渲染裸文字粘连 ("视觉 0");改用 Tailwind utility
// 直接落 prototype 的 oklch 数值与几何 (identity 卡白底 + 大 62px avatar / 灰底分组卡 /
// 14px 间距 / 中间分隔线 / chevron ›/ danger 红).

const PAGE_BG = "bg-[oklch(0.95_0.005_240)]";
const CARD_BG = "bg-white";
const CARD_BORDER = "border-y border-[oklch(0.91_0.005_240)]";
const ROW_DIVIDER = "border-b border-[oklch(0.93_0.005_240)]";
const ROW_BASE =
  "flex w-full items-center gap-[14px] px-[18px] py-[14px] min-h-[60px] text-left bg-transparent hover:bg-[oklch(0.96_0.005_240)] transition-colors";
const ICON_BASE =
  "flex w-[28px] h-[28px] shrink-0 items-center justify-center rounded-[7px] text-[15px]";
const LABEL = "flex-1 min-w-0 m-0 text-[15px] font-medium text-[oklch(0.14_0.01_240)]";
const LABEL_DANGER = "flex-1 min-w-0 m-0 text-[15px] font-medium text-red-600 text-[oklch(0.50_0.15_25)]";
const CHEVRON = "shrink-0 text-[18px] font-light text-[oklch(0.70_0.01_240)]";

export function MePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const lang = getCurrentLanguage();
  const [notificationsEnabled, setNotificationsEnabled] = useNotificationPreference();

  const handleSignOut = () => {
    useAuthStore.getState().clear();
    navigate("/login", { replace: true });
  };

  const handleLanguageChange = (next: Locale) => {
    setLanguage(next);
  };

  const initials = (user?.display_name || user?.username || "U").slice(0, 2).toUpperCase();

  return (
    <section className={`im-me-page ${PAGE_BG} flex-1 overflow-y-auto pb-6`} data-testid="me-page">
      <header className="sr-only">
        <h1>{t("me.title")}</h1>
      </header>

      <Link
        to="/settings/account"
        className={`${CARD_BG} flex w-full items-center gap-4 px-[18px] pt-[26px] pb-[24px] border-b border-[oklch(0.91_0.005_240)]`}
        data-testid="me-identity-card"
      >
        <span
          className="flex w-[62px] h-[62px] shrink-0 items-center justify-center rounded-full bg-[oklch(0.52_0.14_270)] text-white text-[22px] font-bold"
          aria-hidden="true"
          data-testid="me-identity-avatar"
        >
          {initials}
        </span>
        <div className="flex-1 min-w-0">
          <p className="m-0 text-[20px] font-extrabold tracking-tight text-[oklch(0.14_0.01_240)] truncate">
            {user?.display_name ?? user?.username ?? ""}
          </p>
          <p
            className="mt-[5px] text-[13px] font-mono text-[oklch(0.55_0.01_240)] truncate"
            data-testid="me-identity-user-id"
          >
            {user?.id ?? ""}
          </p>
        </div>
        <span className={CHEVRON} aria-hidden="true" data-testid="me-identity-chevron">›</span>
      </Link>

      <div
        className={`${CARD_BG} ${CARD_BORDER} mt-[14px] rounded-none`}
        data-testid="me-card-nodes"
      >
        <Link to="/settings/nodes" className={ROW_BASE} data-testid="me-row-nodes">
          <span
            className={`${ICON_BASE} bg-[oklch(0.95_0.006_240)]`}
            aria-hidden="true"
          >🖥</span>
          <p className={LABEL}>{t("me.sections.nodes")}</p>
          <span className={CHEVRON} aria-hidden="true" data-testid="me-row-chevron">›</span>
        </Link>
      </div>

      <div
        className={`${CARD_BG} ${CARD_BORDER} mt-[14px] rounded-none`}
        data-testid="me-card-account"
      >
        <Link to="/settings/account" className={ROW_BASE} data-testid="me-row-account">
          <span
            className={`${ICON_BASE} bg-[oklch(0.95_0.006_240)]`}
            aria-hidden="true"
          >👤</span>
          <p className={LABEL}>{t("me.sections.account")}</p>
          <span className={CHEVRON} aria-hidden="true" data-testid="me-row-chevron">›</span>
        </Link>
      </div>

      <div
        className={`${CARD_BG} ${CARD_BORDER} mt-[14px] rounded-none`}
        data-testid="me-card-language"
      >
        <div
          className="flex items-center gap-[14px] px-[18px] py-[14px] min-h-[60px]"
          data-testid="me-row-language"
        >
          <span
            className={`${ICON_BASE} bg-[oklch(0.95_0.006_240)] text-[13px] font-bold text-[oklch(0.30_0.01_240)]`}
            aria-hidden="true"
          >文</span>
          <p className={LABEL}>{t("me.sections.language")}</p>
          <div
            className="inline-flex items-center gap-1 rounded-full bg-[oklch(0.94_0.005_240)] p-[3px]"
            role="group"
            aria-label={t("me.sections.language")}
          >
            <button
              type="button"
              aria-pressed={lang === "en"}
              onClick={() => handleLanguageChange("en")}
              className={`px-[13px] py-[5px] rounded-full text-[12.5px] font-bold transition-all ${
                lang === "en"
                  ? "bg-white text-[oklch(0.14_0.01_240)] shadow-sm"
                  : "bg-transparent text-[oklch(0.55_0.01_240)]"
              }`}
            >
              EN
            </button>
            <button
              type="button"
              aria-pressed={lang === "zh"}
              onClick={() => handleLanguageChange("zh")}
              className={`px-[13px] py-[5px] rounded-full text-[12.5px] font-bold transition-all ${
                lang === "zh"
                  ? "bg-white text-[oklch(0.14_0.01_240)] shadow-sm"
                  : "bg-transparent text-[oklch(0.55_0.01_240)]"
              }`}
            >
              中
            </button>
          </div>
        </div>
      </div>

      <div
        className={`${CARD_BG} ${CARD_BORDER} mt-[14px] rounded-none`}
        data-testid="me-card-notifications"
      >
        <label
          className={`${ROW_BASE} cursor-pointer`}
          data-testid="me-row-notifications"
        >
          <span
            className={`${ICON_BASE} bg-[oklch(0.95_0.006_240)]`}
            aria-hidden="true"
          >🔔</span>
          <p className={LABEL}>{t("me.notifications.toggle")}</p>
          <input
            type="checkbox"
            checked={notificationsEnabled}
            onChange={(event) => {
              const next = event.target.checked;
              setNotificationsEnabled(next);
              if (next) {
                void ensureNotificationPermission();
              }
            }}
          />
        </label>
      </div>

      <div
        className={`${CARD_BG} ${CARD_BORDER} mt-[14px] rounded-none`}
        data-testid="me-card-signout"
      >
        <button
          type="button"
          onClick={handleSignOut}
          className={`${ROW_BASE} text-red-600`}
          data-testid="me-row-signout"
        >
          <span
            className={`${ICON_BASE} bg-[oklch(0.96_0.04_25)]`}
            aria-hidden="true"
          >↗</span>
          <p className={LABEL_DANGER}>{t("me.sections.signOut")}</p>
        </button>
      </div>
    </section>
  );
}
