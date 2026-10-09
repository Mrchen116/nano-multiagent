import { afterEach, expect, it } from "vitest";
import { spawn, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import {
  createHash,
  createHmac,
  createDecipheriv,
  createPublicKey,
  diffieHellman,
  generateKeyPairSync,
  hkdfSync,
} from "node:crypto";
import WebSocket from "ws";
import { openDatabase } from "../../src/db.js";
import { canonical } from "../../src/identity.js";
const hash = "$2b$12$EF/L52c0/DOIAIzztg.vLeo3btIdIuVbW5/M3UBiyztqi7ZLIfTUW";
export const cleanups: (() => Promise<unknown> | unknown)[] = [];
afterEach(async () => {
  for (const c of cleanups.splice(0).reverse()) await c();
});
export class Frames {
  queue: any[] = [];
  waiters: {
    match: (p: any) => boolean;
    resolve: (p: any) => void;
    reject: (e: Error) => void;
    timer: NodeJS.Timeout;
  }[] = [];
  constructor(readonly ws: WebSocket) {
    ws.on("message", (raw) => {
      const p = JSON.parse(raw.toString()),
        i = this.waiters.findIndex((w) => w.match(p));
      if (i < 0) this.queue.push(p);
      else {
        const w = this.waiters.splice(i, 1)[0]!;
        clearTimeout(w.timer);
        w.resolve(p);
      }
    });
  }
  next(match: (p: any) => boolean = () => true): Promise<any> {
    const i = this.queue.findIndex(match);
    if (i >= 0) return Promise.resolve(this.queue.splice(i, 1)[0]);
    return new Promise((resolve, reject) => {
      const w = {
        match,
        resolve,
        reject,
        timer: setTimeout(
          () => reject(Error("frame timeout; queued=" + JSON.stringify(this.queue))),
          5000,
        ),
      };
      this.waiters.push(w);
    });
  }
  send(type: string, payload: any) {
    this.ws.send(JSON.stringify({ type, payload }));
    return this.next(
      (p) =>
        p.type === "error" ||
        p.payload?.message_type === type ||
        (p.payload?.request_id === payload.request_id && p.type.endsWith(".result")) ||
        (type === "agent.work.append" && p.type === "agent.work.ack"),
    );
  }
}
export async function start(existingDbPath?: string) {
  const dir = mkdtempSync(join(tmpdir(), "im-process-"));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const dbPath = existingDbPath ?? join(dir, "im.sqlite3"),
    db = openDatabase(dbPath);
  for (const id of ["alice", "bob", "outsider"])
    db.prepare(
      "INSERT OR IGNORE INTO users(id,username,display_name,owner_id,password_hash,membership_status,is_company_admin,created_at) VALUES(?,?,?,?,?,'active',?,?)",
    ).run(id, id, id, id, hash, id === "alice" ? 1 : 0, new Date().toISOString());
  db.close();
  let stderr = "";
  const child = spawn(
    process.execPath,
    ["--import", "tsx", "apps/im-server/src/main.ts", "serve", "--port", "0"],
    {
      cwd: resolve("."),
      env: {
        ...process.env,
        IM_DB_PATH: dbPath,
        IM_PUBLIC_URL: "http://127.0.0.1:8011",
        IM_JWT_SECRET: "isolated-real-process-secret-at-least-32",
        IM_PUBLIC_MODE: "0",
        WEB_CONCURRENCY: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  child.stderr!.on("data", (d) => (stderr += d));
  const port = await new Promise<number>((resolve, reject) => {
    const timeout = setTimeout(() => reject(Error(stderr)), 10000);
    child.stdout!.on("data", (d) => {
      const m = String(d).match(/IM listening on (\d+)/);
      if (m) {
        clearTimeout(timeout);
        resolve(Number(m[1]));
      }
    });
    child.once("exit", () => {
      clearTimeout(timeout);
      reject(Error(stderr));
    });
  });
  cleanups.push(async () => {
    if (child.exitCode === null) {
      child.kill("SIGTERM");
      await once(child, "exit");
    }
  });
  const base = `http://127.0.0.1:${port}`;
  const http = async (
    method: string,
    path: string,
    body?: any,
    token?: string,
    headers: Record<string, string> = {},
  ) => {
    const response = await fetch(base + path, {
      method,
      headers: {
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(body !== undefined ? { "content-type": "application/json" } : {}),
        ...headers,
      },
      body:
        body === undefined
          ? undefined
          : typeof body === "string" || body instanceof Uint8Array
            ? body
            : JSON.stringify(body),
    });
    const text = await response.text();
    return {
      status: response.status,
      headers: response.headers,
      body: text
        ? (() => {
            try {
              return JSON.parse(text);
            } catch {
              return text;
            }
          })()
        : null,
    };
  };
  const tokens: Record<string, string> = {};
  for (const id of ["alice", "bob", "outsider"]) {
    const result = await http("POST", "/im/v1/auth/login", {
      username: id,
      password: "old-password",
    });
    expect(result.status, result.body).toBe(200);
    tokens[id] = result.body.access_token;
  }
  return { dir, dbPath, child, base, http, tokens };
}
export async function bind(f: Awaited<ReturnType<typeof start>>, node = "node-a", configurations: Record<string, unknown> = {}) {
  const pair = generateKeyPairSync("x25519"),
    publicKey = Buffer.from(pair.publicKey.export({ format: "jwk" }).x!, "base64url");
  const post = (action: string, b: any, token?: string) =>
    f.http("POST", "/im/v1/device-binding/" + action, b, token);
  const started = await post("start", {
    node_id: node,
    node_name: node,
    public_key: publicKey.toString("base64"),
    key_id: "sha256:" + createHash("sha256").update(publicKey).digest("hex"),
  });
  expect(started.status, started.body).toBe(200);
  const operation = started.body,
    c = operation.challenge,
    remote = createPublicKey({
      key: {
        kty: "OKP",
        crv: "X25519",
        x: Buffer.from(c.ephemeral_public_key, "base64").toString("base64url"),
      },
      format: "jwk",
    }),
    key = Buffer.from(
      hkdfSync(
        "sha256",
        diffieHellman({ privateKey: pair.privateKey, publicKey: remote }),
        Buffer.from(c.salt, "base64"),
        "nano-multiagent/device-binding-v1",
        32,
      ),
    ),
    ciphertext = Buffer.from(c.ciphertext, "base64"),
    decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(c.nonce, "base64"));
  decipher.setAAD(Buffer.from(canonical(c.aad)));
  decipher.setAuthTag(ciphertext.subarray(-16));
  const challenge = Buffer.concat([
    decipher.update(ciphertext.subarray(0, -16)),
    decipher.final(),
  ]).toString();
  const auth = {
    operation_id: operation.operation_id,
    operation_token: operation.operation_token,
  };
  expect((await post("prove", { ...auth, challenge })).status).toBe(200);
  expect(
    (await post("accept", { browser_token: operation.browser_token }, f.tokens.alice)).status,
  ).toBe(200);
  const prepare = await post("prepare", auth);
  const proof = createHmac("sha256", createHash("sha256").update(challenge).digest())
    .update(canonical(prepare.body.confirmation))
    .digest("hex");
  expect((await post("commit", { ...auth, proof, envelopes: {} })).status).toBe(200);
  const recovery = await post("recover", auth);
  expect(recovery.status, recovery.body).toBe(200);
  return connect(f, node, recovery.body.runtime_token, configurations);
}
export async function connect(f: Awaited<ReturnType<typeof start>>, node: string, runtime: string, configurations: Record<string, unknown> = {}) {
  const socket = new WebSocket(f.base.replace("http:", "ws:") + "/im/ws/gateway", {
      headers: { Authorization: `Bearer ${runtime}` },
    }),
    frames = new Frames(socket);
  await once(socket, "open");
  cleanups.push(() => socket.terminate());
  const ack = await frames.send("node.register", {
    node_id: node,
    agents: ["assistant", "global"],
    agent_configurations: configurations,
    agent_work_modes: { assistant: "single_thread", global: "global" },
    agent_workspaces: { assistant: "/tmp/assistant", global: "/tmp/global" },
    agent_tool_allowlist: { assistant: ["task_graph"], global: ["task_graph"] },
  });
  expect(ack.type, ack).toBe("ack");
  return {
    socket,
    frames,
    node,
    token: ack.payload.gateway_access_token,
    runtime,
  };
}
