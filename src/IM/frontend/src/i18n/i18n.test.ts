import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("i18n", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("defaults to EN on a fresh initialization without a stored preference", async () => {
    const { getCurrentLanguage, i18n } = await import("./index");
    expect(getCurrentLanguage()).toBe("en");
    expect(i18n.t("auth.login.title")).toBe("Sign in");
  });

  it("switches to zh and restores the preference after reinitialization", async () => {
    const { I18N_STORAGE_KEY, getCurrentLanguage, i18n, setLanguage } = await import("./index");
    setLanguage("zh");
    expect(getCurrentLanguage()).toBe("zh");
    expect(i18n.t("auth.login.title")).toBe("登录");
    expect(i18n.t("shell.tabs.agents")).toBe("智能体");
    expect(localStorage.getItem(I18N_STORAGE_KEY)).toBe("zh");
    vi.resetModules();
    const restored = await import("./index");
    expect(restored.getCurrentLanguage()).toBe("zh");
    expect(restored.i18n.t("auth.login.title")).toBe("登录");
  });
});
