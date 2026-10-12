import type { NodeConfigurationFile } from "./configuration.js";
type Model =
  NodeConfigurationFile["llm"]["providers"][number]["models"][number];

/** Select an explicit native effort for the existing static adaptive request. */
export function defaultReasoning(model: Model): string | undefined {
  return typeof model.reasoning === "object"
    ? model.reasoning.default
    : model.extra_request_body?.thinking &&
        (model.extra_request_body.thinking as { type?: string }).type ===
          "adaptive"
      ? "high"
      : undefined;
}

function nativeModel(model: Model, anthropic: boolean) {
  const extra = model.extra_request_body;
  if (
    extra &&
    Object.keys(extra).length &&
    (!anthropic ||
      Object.keys(extra).length !== 1 ||
      JSON.stringify(extra.thinking) !== JSON.stringify({ type: "adaptive" }))
  ) {
    throw new Error(
      `Model ${model.name} has unsupported extra_request_body; map it to native pi-ai configuration before migration`,
    );
  }
  const levels =
    typeof model.reasoning === "object"
      ? model.reasoning.levels
      : extra?.thinking
        ? ["high"]
        : undefined;
  return {
    id: model.name,
    contextWindow: model.context_window,
    ...(levels?.length
      ? {
          reasoningEfforts: Object.fromEntries(
            levels.map((level) => [
              level === "none" ? "off" : level,
              level === "none" ? null : level,
            ]),
          ),
          ...(anthropic ? { compat: { forceAdaptiveThinking: true } } : {}),
        }
      : {}),
  };
}

/** Map the node's existing proxy routes into the native pi-ai provider catalog. */
export function providerProfiles(config: NodeConfigurationFile["llm"]) {
  const providers: Record<string, unknown> = {};
  const env: NodeJS.ProcessEnv = {};
  for (const [index, provider] of config.providers.entries()) {
    const credential = `NANO_PROVIDER_${index}_KEY`;
    if (provider.api_key) env[credential] = provider.api_key;
    else if (
      ["127.0.0.1", "localhost", "[::1]"].includes(
        new URL(provider.base_url).hostname,
      )
    )
      env[credential] = "nano-local-proxy";
    providers[provider.name] = {
      api:
        provider.name === "anthropic"
          ? "anthropic-messages"
          : "openai-completions",
      baseURL: provider.base_url,
      defaultInput: ["text", "image"],
      ...(env[credential] ? { apiKeyEnv: credential } : {}),
      models: provider.models.map((model) =>
        nativeModel(model, provider.name === "anthropic"),
      ),
    };
  }
  return { providers, env };
}
