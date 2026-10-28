import { expect, it } from "vitest";
import { projectCapabilities } from "../src/capabilities.js";
import type { NodeConfigurationFile } from "../src/configuration.js";
it("exposes selectable effort and native Workflow commands without a duplicate slash", () => {
  const catalog = {
    tools: [{ name: "workflow", description: "workflow" }, {name: "expense_summary", description: "Expenses", source_group: "workspace" as const, enabled: true}],
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
  const capabilities = projectCapabilities(catalog, node, agent);
  expect(capabilities.tools.find(tool => tool.name === "expense_summary")).toMatchObject({source_group: "workspace", enabled: true, default_on: false});
  expect(capabilities.features.find(feature => feature.key === "intelligent_ui")).toMatchObject({default_on: true, requires: {features: [], tools: ["send_message", "skill"], skills: ["nano-interactive-ui"]}, available: false});
  const commands = capabilities.commands;
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

it("lists Goal tools as individually selectable defaults without a feature", () => {
  const tools = ['create_goal', 'get_goal', 'update_goal'];
  const node = {llm: {default_model: 'test', providers: []}} as unknown as NodeConfigurationFile;
  const capabilities = projectCapabilities({tools: tools.map(name => ({name, description: name})), skills: []}, node,
    {agentId: 'a', revision: '1', provider: 'test', model: 'test', toolAllowlist: tools});
  expect(capabilities.features.some(feature => feature.key === 'dsh_goal')).toBe(false);
  expect(capabilities.tools.map(tool => tool.name)).toEqual(tools);
  expect(capabilities.tools.every(tool => tool.default_on === false)).toBe(true);
});


it('reports dependency resources independently from the selected allowlist', () => {
  const node = {llm: {default_model: 'test', providers: []}} as unknown as NodeConfigurationFile;
  const available = projectCapabilities({tools: ['send_message', 'skill'].map(name => ({name, description: name})), skills: [{name: 'nano-interactive-ui', description: 'UI'}]}, node,
    {agentId: 'a', revision: '1', provider: 'test', model: 'test', mode: 'global', toolAllowlist: []});
  expect(available.features.find(feature => feature.key === 'intelligent_ui')).toMatchObject({available: true});
  expect(available.features.find(feature => feature.key === 'task_graph')).toMatchObject({available: false});
  expect(available.fixed_tools).toContain('subagent');
});

it('hides retired memory controls without changing stored legacy tool choices', () => {
  const node = {llm:{default_model:'test',providers:[]}} as unknown as NodeConfigurationFile;
  const agent = {agentId:'a',revision:'1',provider:'test',model:'test',toolAllowlist:['memory','read']};
  const catalog = {tools:['memory','read','memory_maintenance'].map(name=>({name,description:name})),skills:[]};
  expect(projectCapabilities(catalog,node,agent).tools.map(tool=>tool.name)).toEqual(['read','memory_maintenance']);
  expect(agent.toolAllowlist).toEqual(['memory','read']);
});
