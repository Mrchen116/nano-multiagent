import { describe, expect, it } from "vitest";

import { i18n } from "../../i18n";
import type { SystemNotice } from "./chat-types";
import { formatSystemNotice } from "./system-notice";

const base: SystemNotice = {
  kind: "self_evolution_review",
  source_agent_id: "product",
  source_agent_display_name: "SpecLab Product",
  updated_targets: ["memory"],
};

describe("formatSystemNotice", () => {
  it("localizes complete direct and group variants", async () => {
    await i18n.changeLanguage("zh");
    expect(formatSystemNotice(i18n.t, base, false)).toBe(
      "· SpecLab Product · 后台自进化：记忆已更新",
    );
    expect(formatSystemNotice(i18n.t, base, true)).toBe(
      "· 后台自进化：记忆已更新",
    );
    expect(
      formatSystemNotice(
        i18n.t,
        { ...base, updated_targets: ["memory", "skills"] },
        false,
      ),
    ).toBe("· SpecLab Product · 后台自进化：技能与记忆已更新");

    await i18n.changeLanguage("en");
    expect(formatSystemNotice(i18n.t, base, false)).toBe(
      "· SpecLab Product · Background self-evolution: memory updated",
    );
    expect(formatSystemNotice(i18n.t, base, true)).toBe(
      "· Background self-evolution: memory updated",
    );
  });

  it("returns null for unknown or malformed sidecars", () => {
    expect(
      formatSystemNotice(
        i18n.t,
        { ...base, kind: "future_notice" },
        false,
      ),
    ).toBeNull();
    expect(
      formatSystemNotice(
        i18n.t,
        { ...base, source_agent_display_name: "", updated_targets: [] },
        false,
      ),
    ).toBeNull();
  });
});
