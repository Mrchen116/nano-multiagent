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
  it.each([
    ["zh", false, ["skills"], "· SpecLab Product · 后台自进化：技能已更新"],
    ["zh", false, ["memory"], "· SpecLab Product · 后台自进化：记忆已更新"],
    ["zh", false, ["memory", "skills"], "· SpecLab Product · 后台自进化：技能与记忆已更新"],
    ["zh", true, ["skills"], "· 后台自进化：技能已更新"],
    ["zh", true, ["memory"], "· 后台自进化：记忆已更新"],
    ["zh", true, ["skills", "memory"], "· 后台自进化：技能与记忆已更新"],
    ["en", false, ["skills"], "· SpecLab Product · Background self-evolution: skills updated"],
    ["en", false, ["memory"], "· SpecLab Product · Background self-evolution: memory updated"],
    ["en", false, ["skills", "memory"], "· SpecLab Product · Background self-evolution: skills and memory updated"],
    ["en", true, ["skills"], "· Background self-evolution: skills updated"],
    ["en", true, ["memory"], "· Background self-evolution: memory updated"],
    ["en", true, ["memory", "skills"], "· Background self-evolution: skills and memory updated"],
  ] as const)(
    "localizes %s direct=%s targets=%j",
    async (language, isDirectChat, updatedTargets, expected) => {
      await i18n.changeLanguage(language);
      expect(
        formatSystemNotice(
          i18n.t,
          { ...base, updated_targets: [...updatedTargets] },
          isDirectChat,
        ),
      ).toBe(expected);
    },
  );

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
    expect(() =>
      formatSystemNotice(
        i18n.t,
        {
          ...base,
          source_agent_id: null,
          source_agent_display_name: 123,
        } as unknown as SystemNotice,
        false,
      )
    ).not.toThrow();
    expect(
      formatSystemNotice(
        i18n.t,
        { ...base, source_agent_display_name: 123 } as unknown as SystemNotice,
        false,
      ),
    ).toBeNull();
  });
});
