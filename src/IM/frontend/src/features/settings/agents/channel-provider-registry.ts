import type {
  AgentChannel,
  AgentChannelRemoval,
  ChannelCredentialsInput,
} from "./im-agent-config-api";

export interface ChannelText {
  default: string;
  key?: string;
}

export interface ChannelProviderField {
  name: string;
  wireKey: string;
  source: "config" | "credentials";
  label: ChannelText;
  validation: ChannelText;
  help?: ChannelText;
  inputType?: "text" | "password";
  required?: boolean;
  resetsCredentials?: boolean;
}

export interface ChannelProviderDescriptor {
  id: string;
  icon: string;
  label: ChannelText;
  description: ChannelText;
  guide?: {
    text: ChannelText;
    href: string;
    linkLabel: ChannelText;
  };
  fields: readonly ChannelProviderField[];
  summary: { field: string; label: string; mask: boolean };
  removalSummary: { displayKey: string; label: string };
  diagnostics?: {
    href: string;
    linkLabel: ChannelText;
    scopeLabel: ChannelText;
    effectOverrides: Readonly<Record<string, ChannelText>>;
  };
  connectingDetail: ChannelText;
}

export type CredentialMode = "keep" | "replace";

export interface ChannelProviderFormState {
  values: Record<string, string>;
  credentialMode: CredentialMode;
}

export interface SerializedChannelProviderForm {
  config: Record<string, string>;
  credentials: ChannelCredentialsInput;
}

export const FEISHU_OPEN_PLATFORM_URL =
  "https://open.feishu.cn/page/launcher?from=backend_oneclick";

export const CHANNEL_PROVIDERS: readonly ChannelProviderDescriptor[] = [{
  id: "feishu",
  icon: "飞",
  label: { default: "Feishu", key: "agents.channels.feishu.label" },
  description: {
    default: "Connect a Feishu application bot",
    key: "agents.channels.feishu.description",
  },
  guide: {
    text: {
      default: "Create a Feishu application and enable long connections.",
      key: "agents.channels.feishu.guide",
    },
    href: FEISHU_OPEN_PLATFORM_URL,
    linkLabel: {
      default: "Open Feishu Open Platform",
      key: "agents.channels.feishu.openPlatform",
    },
  },
  fields: [
    {
      name: "appId",
      wireKey: "app_id",
      source: "config",
      label: { default: "App ID" },
      validation: {
        default: "Enter an App ID",
        key: "agents.channels.validation.appId",
      },
      resetsCredentials: true,
    },
    {
      name: "appSecret",
      wireKey: "app_secret",
      source: "credentials",
      label: { default: "App Secret" },
      validation: {
        default: "Enter an App Secret",
        key: "agents.channels.validation.appSecret",
      },
      help: {
        default: "The secret is stored securely and is not shown again.",
        key: "agents.channels.credentials.secretHelp",
      },
      inputType: "password",
    },
  ],
  summary: { field: "appId", label: "App ID", mask: true },
  removalSummary: { displayKey: "app_id_suffix", label: "App ID" },
  diagnostics: {
    href: FEISHU_OPEN_PLATFORM_URL,
    linkLabel: {
      default: "Check Open Platform",
      key: "agents.channels.diagnostics.openPlatform",
    },
    scopeLabel: {
      default: "Feishu permission scopes",
      key: "agents.channels.diagnostics.rawScopes",
    },
    effectOverrides: {
      "feishu.receive_group_message": {
        default: "Messages without an @Bot mention do not enter Agent context.",
        key: "agents.channels.diagnostics.groupBackgroundEffect",
      },
    },
  },
  connectingDetail: {
    default: "Establishing the Feishu long connection",
    key: "agents.channels.status.connectingDetail",
  },
}];

export function textKey(text: ChannelText): string {
  return text.key ?? text.default;
}

export function providerById(
  providers: readonly ChannelProviderDescriptor[],
  providerId: string,
): ChannelProviderDescriptor | undefined {
  return providers.find((provider) => provider.id === providerId);
}

export function initialProviderForm(
  provider: ChannelProviderDescriptor,
  editing: AgentChannel | null,
): ChannelProviderFormState {
  return {
    values: Object.fromEntries(provider.fields.map((field) => {
      if (field.source !== "config" || editing === null) return [field.name, ""];
      const value = editing.config[field.wireKey];
      return [field.name, typeof value === "string" ? value : ""];
    })),
    credentialMode: editing ? "keep" : "replace",
  };
}

export function validateProviderForm(
  provider: ChannelProviderDescriptor,
  form: ChannelProviderFormState,
  editing: AgentChannel | null,
): Record<string, ChannelText> {
  const errors: Record<string, ChannelText> = {};
  for (const field of provider.fields) {
    const secretRequired = field.source !== "credentials"
      || editing === null
      || form.credentialMode === "replace";
    if (field.required !== false && secretRequired && !form.values[field.name]?.trim()) {
      errors[field.name] = field.validation;
    }
  }
  return errors;
}

export function serializeProviderForm(
  provider: ChannelProviderDescriptor,
  form: ChannelProviderFormState,
): SerializedChannelProviderForm {
  const config: Record<string, string> = {};
  const credentials: ChannelCredentialsInput = { mode: form.credentialMode };
  for (const field of provider.fields) {
    if (field.source === "config") {
      config[field.wireKey] = form.values[field.name]?.trim() ?? "";
    } else if (form.credentialMode === "replace") {
      credentials[field.wireKey] = form.values[field.name]?.trim() ?? "";
    }
  }
  return { config, credentials };
}

export function providerSummary(
  provider: ChannelProviderDescriptor,
  channel: AgentChannel,
): string {
  const field = provider.fields.find((candidate) => (
    candidate.name === provider.summary.field && candidate.source === "config"
  ));
  const raw = field ? channel.config[field.wireKey] : "";
  const value = typeof raw === "string" ? raw : "";
  return provider.summary.mask ? maskIdentity(value) : value;
}

export function providerRemovalSummary(
  provider: ChannelProviderDescriptor,
  removal: AgentChannelRemoval,
): string {
  const raw = removal.display_config[provider.removalSummary.displayKey];
  return typeof raw === "string" ? raw : "—";
}

function maskIdentity(value: string): string {
  if (value.length <= 8) return value;
  return `${value.slice(0, 6)}••••${value.slice(-4)}`;
}
