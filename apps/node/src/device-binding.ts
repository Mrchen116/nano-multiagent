import { readFile, rm, rename, mkdir, access } from "node:fs/promises";
import { dirname, join } from "node:path";
import { createHash, createHmac, randomUUID } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import {
  ChannelKey,
  type ChannelAad,
  type CredentialEnvelope,
} from "@nano/channels";
import { dump } from "js-yaml";
import { atomicPrivate } from "./lifecycle.js";
import { NodeConfiguration } from "./configuration.js";
interface Snapshot {
  agent_profiles: Record<string, unknown>[];
  channel_manifest_heads: { manifest_revision: number }[];
  agent_channels: (ChannelAad & Record<string, unknown>)[];
  agent_channel_removals: Record<string, unknown>[];
}
interface BindingState {
  state: string;
  target_name: string;
  target_user_id: string;
  target_owner: string;
  confirmation: object;
  snapshot: Snapshot;
}
interface BindingResult {
  node_id: string;
  owner_id: string;
  runtime_token: string;
  snapshot: Snapshot;
}
interface Operation {
  operation_id: string;
  operation_token: string;
  browser_token: string;
  challenge_response: string;
  bind_url: string;
  archive_path?: string;
}
const canonical = (value: object) =>
  JSON.stringify(
    Object.fromEntries(
      Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
    ),
  ).replace(
    /[\u007f-\uffff]/g,
    (char) => "\\u" + char.charCodeAt(0).toString(16).padStart(4, "0"),
  );
const exists = async (path: string) =>
  access(path).then(
    () => true,
    () => false,
  );
/** Persist a device proof before commit so a lost HTTP result can be recovered. */
export async function bindDevice(
  configuration: NodeConfiguration,
  options: {
    auto?: boolean;
    recover?: boolean;
    signal: AbortSignal;
    confirm(text: string): Promise<boolean>;
    open(url: string): void;
    report(text: string): void;
  },
) {
  const config = configuration.value;
  const directory = dirname(configuration.path);
  const path = join(directory, "device-binding-operation.json");
  const key = await ChannelKey.load(
    join(directory, "channel-credentials-v1.pem"),
  );
  const base = new URL(config.im_service.url);
  base.protocol =
    base.protocol === "wss:"
      ? "https:"
      : base.protocol === "ws:"
        ? "http:"
        : base.protocol;
  const post = async <T>(
    action: string,
    payload: unknown,
    browser = false,
  ): Promise<T> => {
    const response = await fetch(
      new URL("/im/v1/device-binding/" + action, base),
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(browser
            ? { authorization: "Bearer " + config.im_service.token }
            : {}),
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.any([options.signal, AbortSignal.timeout(15000)]),
      },
    );
    if (!response.ok)
      throw new Error(
        `Device binding ${action}: HTTP ${response.status} ${await response.text()}`,
      );
    return (await response.json()) as T;
  };
  if(options.auto&&!config.im_service.token&&config.im_service.username&&config.im_service.password){
    const response=await fetch(new URL('/im/v1/auth/login',base),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:config.im_service.username,password:config.im_service.password}),signal:AbortSignal.any([options.signal,AbortSignal.timeout(15000)])});
    if(!response.ok)throw new Error(`Device binding login: HTTP ${response.status}`);
    config.im_service.token=(await response.json() as {access_token:string}).access_token;
  }
  let operation: Operation;
  try {
    operation = JSON.parse(await readFile(path, "utf8")) as Operation;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    const created = await post<
      Operation & {
        challenge: CredentialEnvelope & { aad: { purpose: string } };
      }
    >("start", {
      node_id: config.node.node_id,
      node_name: config.node.node_id,
      public_key: key.registration.credential_public_key,
      key_id: key.registration.credential_key_id,
    });
    operation = {
      ...created,
      challenge_response: key.openBinding(created.challenge),
    };
    await atomicPrivate(path, operation);
  }
  const credential = {
    operation_id: operation.operation_id,
    operation_token: operation.operation_token,
  };
  await post("prove", {
    ...credential,
    challenge: operation.challenge_response,
  });
  if (options.recover) await post("recover-device", credential);
  let state = await post<BindingState>("prepare", credential);
  if (state.state === "awaiting_account") {
    if (options.auto)
      await post("accept", { browser_token: operation.browser_token }, true);
    else {
      options.report(
        "Open this link and accept with the receiving active account:\n" +
          operation.bind_url,
      );
      options.open(operation.bind_url);
    }
    while (state.state === "awaiting_account") {
      options.signal.throwIfAborted();
      await new Promise((resolve) => setTimeout(resolve, 1000));
      state = await post<BindingState>("prepare", credential);
    }
  }
  if (state.state !== "committed") {
    const agents = [
      ...new Set([
        ...state.snapshot.agent_profiles.map((row) => String(row.agent_id)),
        ...config.agents.map((agent) => agent.agent_id),
      ]),
    ];
    options.report(
      `Transfer this device to ${state.target_name} (${state.target_user_id})\nAgents: ${agents.join(", ")}`,
    );
    if (
      !options.auto &&
      !(await options.confirm(
        "Type yes to confirm the complete device transfer: ",
      ))
    ) {
      await post("cancel", credential);
      await rm(path);
      throw new Error(
        "Local confirmation cancelled; device ownership unchanged",
      );
    }
    const envelopes: Record<string, CredentialEnvelope> = {};
    for (const row of state.snapshot.agent_channels) {
      const aad: ChannelAad = {
        owner_id: row.owner_id,
        node_id: row.node_id,
        agent_id: row.agent_id,
        channel_id: row.channel_id,
        provider: row.provider,
        credential_revision: row.credential_revision,
      };
      const secret = key.open(
        JSON.parse(String(row.credential_envelope_json)),
        aad,
      );
      envelopes[row.channel_id] = key.seal(secret, {
        ...aad,
        owner_id: state.target_owner,
        credential_revision: row.credential_revision + 1,
      });
    }
    const proof = createHmac(
      "sha256",
      createHash("sha256").update(operation.challenge_response).digest(),
    )
      .update(canonical(state.confirmation))
      .digest("hex");
    await post("commit", { ...credential, proof, envelopes });
  }
  const result = await post<BindingResult>("recover", credential);
  const home = join(directory, ".dsh-runtime", config.node.node_id);
  if (config.node.user_id && config.node.user_id !== result.owner_id) {
    operation.archive_path ??= home + ".previous-owner-" + randomUUID();
    await atomicPrivate(path, operation);
    if (!(await exists(operation.archive_path)) && (await exists(home)))
      await rename(home, operation.archive_path);
  }
  await mkdir(home, { recursive: true });
  const snapshot = result.snapshot;
  const manifest = {
    request_id: randomUUID(),
    owner_id: result.owner_id,
    node_id: result.node_id,
    manifest_revision:
      snapshot.channel_manifest_heads[0]?.manifest_revision ?? 0,
    channels: snapshot.agent_channels.map((row) => ({
      ...row,
      enabled: !!row.enabled,
      config: JSON.parse(String(row.config_json)),
      provider_runtime: JSON.parse(String(row.provider_runtime_json)),
      credential_envelope: JSON.parse(String(row.credential_envelope_json)),
    })),
    removals: snapshot.agent_channel_removals.filter(
      (row) => row.apply_state !== "applied",
    ),
  };
  const db = new DatabaseSync(join(home, "channels.sqlite3"));
  try {
    db.exec(
      "CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT,type TEXT NOT NULL,payload TEXT NOT NULL);",
    );
    db.prepare(
      "INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
    ).run("manifest", JSON.stringify(manifest));
  } finally {
    db.close();
  }
  config.node.user_id = result.owner_id;
  config.im_service.token = result.runtime_token;
  const im = config.im_service as unknown as Record<string, unknown>;
  delete im.refresh_token;
  delete im.username;
  delete im.password;
  await atomicPrivate(
    configuration.path,
    dump(config, { lineWidth: 140, noRefs: true }),
  );
  await rm(path);
  return { nodeId: result.node_id, ownerId: result.owner_id };
}
