import i18next from "i18next";
import { initReactI18next, useTranslation } from "react-i18next";

import enResources from "./en.json";
import zhResources from "./zh.json";

export const I18N_STORAGE_KEY = "im_lang";

export type Locale = "en" | "zh";
const SUPPORTED: Locale[] = ["en", "zh"];

function isSupported(value: string): value is Locale {
  return (SUPPORTED as string[]).includes(value);
}

function readPersistedLocale(): Locale {
  if (typeof window === "undefined") return "en";
  const raw = window.localStorage.getItem(I18N_STORAGE_KEY);
  if (raw && isSupported(raw)) return raw;
  return "en";
}

export const i18n = i18next.createInstance();

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: enResources },
    zh: { translation: zhResources }
  },
  lng: readPersistedLocale(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false
});

export function getCurrentLanguage(): Locale {
  const current = i18n.language;
  return isSupported(current) ? current : "en";
}

export function setLanguage(next: Locale) {
  if (!isSupported(next)) return;
  i18n.changeLanguage(next);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(I18N_STORAGE_KEY, next);
  }
}

export { useTranslation };
