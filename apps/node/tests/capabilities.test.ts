import { expect, it } from "vitest";
import { projectCapabilities } from "../src/capabilities.js";
import type { NodeConfigurationFile } from "../src/configuration.js";
it("exposes selectable effort and native Workflow commands without a duplicate slash", () => {
  const catalog = {
    tools: [{ name: "workflow", description: "workflow" }],
    skills: [],
    workflows: [{ name: "saved", description: "Saved workflow" }],
  };
  const node = {
    llm: {
      default_model: "test",
      providers: [
        {
          name: "fixture",
          models: [{ name: "test", reasoning: { levels: ["low", "xhigh"] } }],
        },
      ],
    },
  } as NodeConfigurationFile;
  const agent = {
    agentId: "a",
    revision: "1",
    provider: "fixture",
    model: "test",
    toolAllowlist: ["workflow"],
  };
  const commands = projectCapabilities(catalog, node, agent).commands;
  expect(commands.map((command) => command.name)).toEqual([
    "new",
    "stop",
    "compact",
    "effort",
    "workflows",
    "config",
    "saved",
  ]);
  expect(
    commands.find((command) => command.name === "effort")?.description,
  ).toContain("ultracode");
  const disabled = projectCapabilities(catalog, node, {
    ...agent,
    toolAllowlist: [],
  }).commands;
  expect(disabled.map((command) => command.name)).toEqual([
    "new",
    "stop",
    "compact",
    "effort",
  ]);
  expect(
    disabled.find((command) => command.name === "effort")?.description,
  ).not.toContain("ultracode");
});
