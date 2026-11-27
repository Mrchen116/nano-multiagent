import { authFetch } from "../../auth/auth-fetch";
import { readHttpError } from "../../auth/http-error";
import type { AgentChannel } from "./im-agent-config-api";

export type WeChatSetupState =
  | "waiting_scan"
  | "scanned"
  | "need_verify_code"
  | "confirmed"
  | "expired"
  | "cancelled"
  | "failed";

export type WeChatChannelSetupInput =
  | { action: "start"; editing_channel_id?: string; channel_revision?: number }
  | { action: "status"; setup_id: string }
  | { action: "verify_code"; setup_id: string; code: string }
  | { action: "cancel"; setup_id: string };

export interface WeChatChannelSetupResponse {
  setup_id: string;
  state: WeChatSetupState;
  qr_svg?: string;
  error_code?: string;
  message?: string;
  error_message?: string;
  channel?: AgentChannel;
}

function getApiBaseUrl(): string {
  return (import.meta.env.VITE_IM_API_BASE_URL ?? "").replace(/\/$/, "");
}

/**
 * Drive an interactive WeChat QR/PIN setup session via IM control-plane relay.
 *
 * The backend seals `bot_token` directly with the owning node's X25519 public key
 * and never echoes plaintext credentials to the browser.
 */
export async function setupWeChatChannel(
  agentId: string,
  input: WeChatChannelSetupInput,
): Promise<WeChatChannelSetupResponse> {
  const path = `/im/v1/agents/${encodeURIComponent(agentId)}/channels/wechat/setup`;
  const response = await authFetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const { detail, code } = await readHttpError(response);
    throw Object.assign(new Error(`POST ${path} failed: ${response.status} (${detail})`), {
      status: response.status,
      detail,
      code: code ?? null,
    });
  }
  return (await response.json()) as WeChatChannelSetupResponse;
}
