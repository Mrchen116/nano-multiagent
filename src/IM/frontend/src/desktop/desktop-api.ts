import type {
  DesktopBrowserActionInput,
  DesktopBrowserActionResponse,
  DesktopLocalConfigInput,
  DesktopLocalInspectResponse,
  DesktopLocalOwnership,
  DesktopUpdaterDismissInput,
  DesktopUpdaterPreferencesInput,
  DesktopUpdaterSnapshot,
  DesktopWorkerProbeItem,
} from "@nano/product-contracts/desktop-local";
import { authFetch } from "../features/auth/auth-fetch";
import { useAuthStore } from "../features/auth/auth-store";
import { readHttpError } from "../features/auth/http-error";
import type { DesktopPlatformId, PendingServerSwitch } from "./desktop-context";

export interface DesktopHostContextResponse {
  im_origin: string;
  context_epoch: number;
  platform: DesktopPlatformId;
  seed_ready?: boolean;
  seed_error?: string | null;
  host_log_path?: string;
  pending_server_switch?: PendingServerSwitch | null;
  deep_link_error?: string | null;
}

export interface DesktopConnectResponse {
  ok: true;
  node_id: string;
  node_name: string;
  ready: boolean;
  ownership: DesktopLocalOwnership;
}

export type DesktopTrajectoryPrepareResponse =
  | { mode: "local"; ticket: string }
  | { mode: "remote" };

export class DesktopTransferRequiredError extends Error {
  readonly nodeName?: string;
  constructor(message: string, nodeName?: string) {
    super(message);
    this.name = "DesktopTransferRequiredError";
    this.nodeName = nodeName;
  }
}

export class DesktopApiError extends Error {
  readonly status: number;
  readonly code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "DesktopApiError";
    this.status = status;
    this.code = code;
  }
}

async function hostFetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    const err = await readHttpError(res);
    throw new DesktopApiError(res.status, err.detail || `Request failed (${res.status})`, err.code);
  }
  return (await res.json()) as T;
}

async function authedDesktopJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const err = await readHttpError(res);
    if (res.status === 409 && (err.code === "transfer_confirmation_required" || err.detail.includes("transfer_confirmation_required"))) {
      throw new DesktopTransferRequiredError(err.detail || "Transfer confirmation required");
    }
    throw new DesktopApiError(res.status, err.detail || `Request failed (${res.status})`, err.code);
  }
  return (await res.json()) as T;
}

/** Read current loopback host context (`im_origin`, `context_epoch`, `platform`). */
export function getDesktopContext(): Promise<DesktopHostContextResponse> {
  return hostFetchJson<DesktopHostContextResponse>("/desktop/v1/context");
}

/** Switch active IM server origin on the Desktop host and increment `context_epoch`. */
export function switchDesktopServer(imOrigin: string): Promise<DesktopHostContextResponse> {
  return hostFetchJson<DesktopHostContextResponse>("/desktop/v1/server", {
    method: "PUT",
    body: JSON.stringify({ im_origin: imOrigin.trim() }),
  });
}

/** Dismiss a pending deep-link server switch or blocked deep-link error notice without switching servers. */
export function dismissPendingDesktopServerSwitch(): Promise<{ ok: boolean }> {
  return hostFetchJson<{ ok: boolean }>("/desktop/v1/server/pending/dismiss", {
    method: "POST",
  });
}

/** Open an external `http(s)://` URL in the OS default browser without IM credentials. */
export async function openDesktopExternal(url: string): Promise<void> {
  await hostFetchJson<{ ok: boolean }>("/desktop/v1/open-external", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

/** Inspect local node ownership, live status, proxy/env config, workers, and logs. */
export function inspectDesktopLocalNode(logQuery?: string): Promise<DesktopLocalInspectResponse> {
  const suffix = logQuery?.trim() ? `?log_query=${encodeURIComponent(logQuery.trim())}` : "";
  return authedDesktopJson<DesktopLocalInspectResponse>(`/desktop/v1/local-node/inspect${suffix}`);
}

/** Probe DSH / Codex CLI / Claude Code availability against candidate `PATH`. */
export function probeDesktopWorkers(extraPath?: string): Promise<{ workers: DesktopWorkerProbeItem[] }> {
  return authedDesktopJson<{ workers: DesktopWorkerProbeItem[] }>("/desktop/v1/local-node/probe-workers", {
    method: "POST",
    body: JSON.stringify({ extra_path: extraPath }),
  });
}

/** Inspect, open guided setup tabs, pair, or disconnect the local daily Chrome extension. */
export function manageDesktopLocalBrowser(input: DesktopBrowserActionInput): Promise<DesktopBrowserActionResponse> {
  return authedDesktopJson<DesktopBrowserActionResponse>("/desktop/v1/local-node/browser", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Bind a fresh computer, smoothly take over a same-owner node, or confirm full-machine transfer. */
export function connectDesktopLocalNode(input?: {
  confirmTransfer?: boolean;
  nodeName?: string;
}): Promise<DesktopConnectResponse> {
  return authedDesktopJson<DesktopConnectResponse>("/desktop/v1/local-node/connect", {
    method: "POST",
    body: JSON.stringify({
      confirm_transfer: Boolean(input?.confirmTransfer),
      ...(input?.nodeName ? { node_name: input.nodeName } : {}),
    }),
  });
}

/** Run serialized local node lifecycle actions or non-interrupting login autostart toggle. */
export function controlDesktopLocalNode(input: {
  action: "start" | "stop" | "restart" | "autostart";
  enabled?: boolean;
}): Promise<DesktopLocalInspectResponse> {
  return authedDesktopJson<DesktopLocalInspectResponse>("/desktop/v1/local-node/lifecycle", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Validate, atomically persist, and restart (with automatic rollback on failure) local node config. */
export function saveDesktopLocalNodeConfig(input: DesktopLocalConfigInput): Promise<DesktopLocalInspectResponse> {
  return authedDesktopJson<DesktopLocalInspectResponse>("/desktop/v1/local-node/config", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

/** Open or reveal a verified workspace path in Finder / Explorer. */
export function openDesktopWorkspacePath(input: {
  agent_id: string;
  path: string;
  action: "open" | "reveal";
}): Promise<{ ok: true; resolved_path: string }> {
  return authedDesktopJson<{ ok: true; resolved_path: string }>("/desktop/v1/workspace/open", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Attempt local direct trajectory preparation; returns `{ mode: "remote" }` when not local. */
export function prepareDesktopLocalTrajectory(input: {
  agent_id: string;
  session_id: string;
}): Promise<DesktopTrajectoryPrepareResponse> {
  return authedDesktopJson<DesktopTrajectoryPrepareResponse>("/desktop/v1/trajectory/prepare", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

async function optionalAuthDesktopJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (useAuthStore.getState().accessToken) {
    const res = await authFetch(path, init);
    if (!res.ok) {
      const err = await readHttpError(res);
      throw new DesktopApiError(res.status, err.detail || `Request failed (${res.status})`, err.code);
    }
    return (await res.json()) as T;
  }
  return hostFetchJson<T>(path, init);
}

/** Report active route and unsaved form dirty state to the Desktop loopback host. */
export function reportDesktopAttention(input: {
  current_route: string;
  has_unsaved_form: boolean;
}): Promise<{ ok: boolean; route: string; navigate_to?: string | null }> {
  return hostFetchJson("/desktop/v1/attention", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Read current Crewden Desktop updater state, preferences, and active bundle metadata. */
export function getDesktopUpdaterSnapshot(): Promise<DesktopUpdaterSnapshot> {
  return hostFetchJson<DesktopUpdaterSnapshot>("/desktop/v1/updater", { cache: "no-store" });
}

/** Trigger an immediate manual or post-switch Desktop update check against `im_origin`. */
export function checkDesktopUpdates(manual = true): Promise<DesktopUpdaterSnapshot> {
  return hostFetchJson<DesktopUpdaterSnapshot>("/desktop/v1/updater/check", {
    method: "POST",
    body: JSON.stringify({ manual }),
  });
}

/** Update persistent `auto_update` ("自动保持最新") preference on the Desktop host. */
export function setDesktopAutoUpdatePreference(
  input: DesktopUpdaterPreferencesInput,
): Promise<DesktopUpdaterSnapshot> {
  return hostFetchJson<DesktopUpdaterSnapshot>("/desktop/v1/updater/preferences", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

/** Apply a ready hot bundle switch (or begin downloading a native client installer). */
export function applyDesktopUpdate(): Promise<DesktopUpdaterSnapshot> {
  return optionalAuthDesktopJson<DesktopUpdaterSnapshot>("/desktop/v1/updater/apply", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

/** Cancel an active download or cancel a pending task-draining node switch. */
export function cancelDesktopUpdate(): Promise<DesktopUpdaterSnapshot> {
  return optionalAuthDesktopJson<DesktopUpdaterSnapshot>("/desktop/v1/updater/cancel", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

/** Re-verify SHA-256 and open/launch a downloaded Desktop platform installer (`.dmg` or `.exe`). */
export function openDesktopUpdaterInstaller(): Promise<DesktopUpdaterSnapshot> {
  return hostFetchJson<DesktopUpdaterSnapshot>("/desktop/v1/updater/open-installer", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

/** Dismiss the post-switch confirmation pill or collapse the floating capsule for the current target version. */
export function dismissDesktopUpdaterNotice(
  input: DesktopUpdaterDismissInput,
): Promise<DesktopUpdaterSnapshot> {
  return hostFetchJson<DesktopUpdaterSnapshot>("/desktop/v1/updater/dismiss", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
