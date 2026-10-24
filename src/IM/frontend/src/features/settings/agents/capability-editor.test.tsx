/// <reference types="node" />
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { changeCapability, type CapabilityAction, type CapabilityCatalog, type CapabilityDraft, type FeatureDependency, type CapabilityBlock } from "@nano/product-contracts/capabilities";
const fixtures = JSON.parse(readFileSync(resolve(process.cwd(), "../../../packages/product-contracts/tests/fixtures/capabilities.json"), "utf8")) as {
  definitions: FeatureDependency[];
  cases: { name: string; draft: CapabilityDraft; catalog: CapabilityCatalog; actions: CapabilityAction[]; expected: { draft: CapabilityDraft; blocks: CapabilityBlock[] } }[];
};
import { restoreBlockedCapabilities } from "./capability-editor";

describe("shared capability selection contract", () => {
  for (const item of fixtures.cases) {
    it(item.name, () => {
      let result = { draft: item.draft as CapabilityDraft, blocks: [] as unknown[] };
      for (const action of item.actions) result = changeCapability(result.draft, action as CapabilityAction, { features: fixtures.definitions, ...item.catalog } as CapabilityCatalog);
      expect(result).toEqual(item.expected);
    });
  }
  it("restores a rejected feature without replacing unrelated draft edits", () => {
    const draft = { description: "new description", custom_prompt: "new instructions", features: Object.fromEntries(fixtures.definitions.map(f => [f.key, false])), tool_allowlist: [], skills: [], skills_selection_mode: "explicit_denylist" };
    const caps = { features: fixtures.definitions, tools: fixtures.definitions.flatMap(f => f.requires.tools).map(name => ({ name, description: "" })), skills: [{name: "nano-interactive-ui", description: ""}], fixed_tools: [] };
    const result = restoreBlockedCapabilities(draft, [{code: "active_tasks", target: {kind: "feature", name: "task_graph"}}], caps as never);
    expect(result.description).toBe("new description");
    expect(result.custom_prompt).toBe("new instructions");
    expect(result.features.task_graph).toBe(true);
    expect(result.features.cron_scheduling).toBe(true);
  });
});
