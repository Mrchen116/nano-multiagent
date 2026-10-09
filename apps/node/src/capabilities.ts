import type { AgentConfiguration } from "@nano/product-contracts";
import type { NodeConfigurationFile } from "./configuration.js";

interface Catalog {
  workflows?: { name: string; description: string }[];
  tools: { name: string; description: string }[];
  skills: {
    name: string;
    description: string;
    path?: string;
    source?: string;
  }[];
}
const features = [
  { key: "task_graph", requires_tool: "task_graph", default_on: true },
  { key: "memory_curation", requires_tool: "memory", default_on: true },
  { key: "skill_creation", requires_tool: "skill_manage", default_on: true },
  {
    key: "cron_scheduling",
    requires_tool: "schedule_create",
    default_on: false,
  },
  { key: "heartbeat", requires_tool: null, default_on: false },
];
/** Existing IM capability payload, populated from native names and node-owned models. */
export function projectCapabilities(
  catalog: Catalog,
  node: NodeConfigurationFile,
  agent?: AgentConfiguration,
) {
  const workflowEnabled =
    catalog.tools.some((tool) => tool.name === "workflow") &&
    (!agent ||
      agent.toolAllowlist === undefined ||
      agent.toolAllowlist.includes("workflow"));
  const model = node.llm.providers
    .flatMap((provider) => provider.models)
    .find((model) => model.name === (agent?.model ?? node.llm.default_model));
  const levels =
    typeof model?.reasoning === "object" ? (model.reasoning.levels ?? []) : [];
  return {
    relay: true,
    send_message: true,
    config_sync: true,
    channel_bootstrap: true,
    platform_default_model: node.llm.default_model,
    models: node.llm.providers.flatMap((provider) =>
      provider.models.map((model) => ({
        name: model.name,
        provider: provider.name,
        ...(typeof model.reasoning === "object"
          ? { reasoning: { kind: "selectable", ...model.reasoning } }
          : model.reasoning
            ? { reasoning: { kind: "fixed" } }
            : {}),
      })),
    ),
    tools: catalog.tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      default_on: !["send_message", "run_code"].includes(tool.name),
    })),
    skills: catalog.skills.map((skill) => ({
      name: skill.name,
      description: skill.description,
      location: skill.path,
      source_group: skill.source === "compat" ? "compatibility" : skill.source,
      default_on: skill.source === "global",
    })),
    features: features.map((feature) => ({
      ...feature,
      label_i18n: `feature.${feature.key}.label`,
      help_i18n: `feature.${feature.key}.help`,
      available:
        !agent ||
        agent.toolAllowlist === undefined ||
        !feature.requires_tool ||
        agent.toolAllowlist.includes(feature.requires_tool),
    })),
    commands: [
      { name: "new", description: "Start a new conversation context" },
      { name: "stop", description: "Stop the active response" },
      {
        name: "compact",
        description: "Compact earlier context with optional focus",
      },
      ...(levels.length
        ? [
            {
              name: "effort",
              description: `Reasoning effort: ${[...levels, ...(workflowEnabled && levels.includes("xhigh") ? ["ultracode"] : [])].join(", ")}`,
            },
          ]
        : []),
      ...(workflowEnabled
        ? [
            {
              name: "workflows",
              description: "Inspect and control background workflows",
            },
            {name: "config", description: "Set workflowSizeGuideline: unrestricted, small, medium, large"},
            ...(catalog.workflows ?? []),
          ]
        : []),
    ],
  };
}
