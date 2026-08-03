import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { I18N_STORAGE_KEY, getCurrentLanguage, i18n, setLanguage } from "./index";

describe("i18n", () => {
  beforeEach(() => {
    localStorage.clear();
    // reset to en on every test
    setLanguage("en");
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("defaults to EN", () => {
    expect(getCurrentLanguage()).toBe("en");
    expect(i18n.t("auth.login.title")).toBe("Sign in");
  });

  it("switches to zh via setLanguage and persists", () => {
    setLanguage("zh");
    expect(getCurrentLanguage()).toBe("zh");
    expect(i18n.t("auth.login.title")).toBe("登录");
    expect(i18n.t("shell.tabs.agents")).toBe("智能体");
    expect(localStorage.getItem(I18N_STORAGE_KEY)).toBe("zh");
  });
});
