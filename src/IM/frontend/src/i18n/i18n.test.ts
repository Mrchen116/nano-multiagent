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
    expect(i18n.t("auth.login.submit")).toBe("Sign in");
  });

  it("switches to zh and restores the preference after reinitialization", async () => {
    const { I18N_STORAGE_KEY, getCurrentLanguage, i18n, setLanguage } = await import("./index");
    setLanguage("zh");
    expect(getCurrentLanguage()).toBe("zh");
    expect(i18n.t("auth.login.submit")).toBe("登录");
    expect(i18n.t("shell.tabs.agents")).toBe("智能体");
    expect(localStorage.getItem(I18N_STORAGE_KEY)).toBe("zh");
    vi.resetModules();
    const restored = await import("./index");
    expect(restored.getCurrentLanguage()).toBe("zh");
    expect(restored.i18n.t("auth.login.submit")).toBe("登录");
  });

  it("keeps zh.json and en.json feature and tasks key trees strictly symmetric including proactive planning and 9 task statuses", async () => {
    const [zhModule, enModule] = await Promise.all([import("./zh.json"), import("./en.json")]);
    const collectKeys = (obj: Record<string, unknown>, prefix = ""): string[] =>
      Object.keys(obj)
        .sort()
        .flatMap(key => {
          const path = prefix ? `${prefix}.${key}` : key;
          const value = obj[key];
          if (value && typeof value === "object" && !Array.isArray(value)) {
            return collectKeys(value as Record<string, unknown>, path);
          }
          return [path];
        });

    const zh = zhModule.default as Record<string, Record<string, unknown>>;
    const en = enModule.default as Record<string, Record<string, unknown>>;
    expect(collectKeys(zh.feature, "feature")).toEqual(collectKeys(en.feature, "feature"));
    expect(collectKeys(zh.tasks, "tasks")).toEqual(collectKeys(en.tasks, "tasks"));

    const { i18n, setLanguage } = await import("./index");
    setLanguage("zh");
    expect(i18n.t("feature.proactive_planning.label")).toBe("主动筹划");
    expect(i18n.t("feature.proactive_planning.help")).toContain("03:00");
    for (const status of ["proposed", "todo", "doing", "waiting", "in_review", "done", "paused", "backlog", "closed"]) {
      expect(i18n.t(`tasks.status.${status}`)).not.toBe(`tasks.status.${status}`);
    }

    setLanguage("en");
    expect(i18n.t("feature.proactive_planning.label")).toBe("Proactive planning");
    expect(i18n.t("feature.proactive_planning.help")).toContain("03:00");
  });
});
