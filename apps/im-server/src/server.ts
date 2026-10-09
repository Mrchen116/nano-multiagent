import Fastify from "fastify";
import websocket from "@fastify/websocket";
import { randomBytes, randomUUID } from "node:crypto";
import { existsSync, createReadStream, mkdirSync } from "node:fs";
import { resolve, dirname, join, extname } from "node:path";
import { openDatabase } from "./db.js";
import { createIdentity } from "./identity.js";
import { registerIdentityRoutes } from "./identity-routes.js";
import { Gateway, registerSockets } from "./gateway.js";
import { Messaging, registerMessagingRoutes } from "./messaging.js";
import { registerConversationActions } from "./conversation-actions.js";
import { registerWorkRoutes } from "./work.js";
import { registerMediaRoutes } from "./media.js";
import { registerControlRoutes } from "./control.js";
import { ChannelService, registerChannelRoutes } from "./channels.js";
import { fail, one, all, type Row, type ImContext } from "./context.js";
export interface ServerOptions {
  dbPath?: string;
  publicUrl?: string;
  jwtSecret?: string;
  uploadDir?: string;
  frontendDistDir?: string;
  frontendDevBaseUrl?: string;
}
export function resolveSecret() {
  const secret = process.env.IM_JWT_SECRET?.trim();
  if (process.env.IM_PUBLIC_MODE === "1" && (!secret || secret.length < 32))
    throw Error("public mode requires IM_JWT_SECRET with at least 32 characters");
  return secret || randomBytes(32).toString("base64url");
}
/** Build the standalone center. No Agent runtime or Python process is loaded. */
export async function createServer(options: ServerOptions = {}) {
  const publicUrl = options.publicUrl ?? process.env.IM_PUBLIC_URL;
  let parsed: URL;
  try {
    parsed = new URL(publicUrl!);
  } catch {
    throw Error("IM_PUBLIC_URL is required and must be an HTTP(S) absolute URL");
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  )
    throw Error("invalid IM_PUBLIC_URL");
  if (
    process.env.IM_PUBLIC_MODE === "1" &&
    process.env.WEB_CONCURRENCY &&
    process.env.WEB_CONCURRENCY !== "1"
  )
    throw Error("public mode supports exactly one IM worker");
  const dbPath = resolve(options.dbPath ?? process.env.IM_DB_PATH ?? "data/im_service.sqlite3"),
    uploadDir = resolve(
      options.uploadDir ?? process.env.IM_UPLOAD_DIR ?? join(dirname(dbPath), "uploads"),
    ),
    secret = options.jwtSecret ?? resolveSecret();
  mkdirSync(uploadDir, { recursive: true });
  const db = openDatabase(dbPath);
  const app = Fastify({
    logger: false,
    bodyLimit: 2 * 1024 * 1024,
    requestTimeout: 15000,
    connectionTimeout: 15000,
    keepAliveTimeout: 5000,
    trustProxy: false,
  });
  const ctx = {
    db,
    dbPath,
    uploadDir,
    publicUrl: publicUrl!,
    jwtSecret: secret,
    identity: createIdentity(db, secret),
  } as ImContext;
  ctx.messaging = new Messaging(ctx);
  ctx.gateway = new Gateway(ctx);
  app.decorate("im", ctx);
  const allowed = [
    parsed.origin,
    ...(process.env.IM_BROWSER_ORIGINS ?? "")
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean),
  ];
  const publicIdentity = new Set([
    "/im/v1/auth/register",
    "/im/v1/auth/login",
    "/im/v1/auth/refresh",
    "/im/v1/auth/logout",
    "/im/v1/auth/me",
  ]);
  app.addHook("preHandler", async (req, reply) => {
    if (req.method === "OPTIONS") return reply.code(204).send();
    const path = req.url.split("?")[0]!;
    if (
      path.startsWith("/im/v1/") &&
      !publicIdentity.has(path) &&
      !path.startsWith("/im/v1/device-binding/")
    )
      ctx.messaging.principal(req);
  });
  app.addHook("onSend", async (req, reply, payload) => {
    reply
      .header("X-Frame-Options", "DENY")
      .header("X-Content-Type-Options", "nosniff")
      .header("Referrer-Policy", "strict-origin-when-cross-origin");
    if (parsed.protocol === "https:") reply.header("Strict-Transport-Security", "max-age=86400");
    if (allowed.includes(req.headers.origin ?? ""))
      reply
        .header("Access-Control-Allow-Origin", req.headers.origin!)
        .header("Access-Control-Allow-Credentials", "true")
        .header(
          "Access-Control-Allow-Headers",
          "Authorization,Content-Type,Idempotency-Key,X-IM-Session",
        )
        .header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
    const path = req.url.split("?")[0]!;
    if (path.startsWith("/im/v1/auth/")) reply.header("Cache-Control", "no-store");
    if (String(reply.getHeader("content-type")).startsWith("text/html"))
      reply.header(
        "Content-Security-Policy",
        `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; connect-src 'self' ${parsed.protocol === "https:" ? "wss" : "ws"}://${parsed.host}; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`,
      );
    if (
      reply.statusCode < 400 &&
      req.method !== "OPTIONS" &&
      path.startsWith("/im/v1/") &&
      !publicIdentity.has(path) &&
      !path.startsWith("/im/v1/device-binding/")
    )
      ctx.messaging.principal(req);
    return payload;
  });
  app.setErrorHandler((error, req, reply) => {
    const e = error as any;
    const status = e.statusCode ?? 500;
    if (e.retry_after) reply.header("Retry-After", String(e.retry_after));
    if (status === 401) reply.header("WWW-Authenticate", "Bearer");
    reply.code(status).send({
      detail: e.detail ?? (status < 500 ? e.message : "internal server error"),
      ...(e.retry_after ? { retry_after: e.retry_after } : {}),
    });
  });
  await app.register(websocket, { options: { maxPayload: 2 * 1024 * 1024 } });
  registerIdentityRoutes(app, ctx);
  registerMessagingRoutes(app, ctx);
  registerConversationActions(app, ctx);
  registerControlRoutes(app, ctx);
  registerWorkRoutes(app, ctx);
  await registerMediaRoutes(app, ctx);
  registerSockets(app, ctx);
  app.get("/im/v1/gateway/identity", (req) => {
    const p = ctx.gateway.authenticate(
      (req.headers.authorization ?? "").replace(/^Bearer\s+/i, ""),
    );
    if (!p) fail(401, "gateway credential required");
    return {
      owner_id: p.owner_id,
      node_id: p.node_id,
      node_epoch: p.node_epoch,
      agents: all(
        db,
        "SELECT agent_id FROM agent_profiles WHERE node_id=? AND owner_id=? AND is_stale=0",
        p.node_id,
        p.owner_id,
      ).map((a) => a.agent_id),
    };
  });
  const channels = new ChannelService(db);
  ctx.gateway.channelInitialize = (node) => {
    if (!one(db, "SELECT 1 FROM node_credential_keys WHERE node_id=?", node)) return;
    const init = channels.initialize(node);
    ctx.gateway.send(
      node,
      init.manifest
        ? {
            type: "channel.reconcile",
            payload: { ...init.manifest, request_id: randomUUID() },
          }
        : {
            type: "channels.bootstrap.request",
            payload: {
              request_id: randomUUID(),
              node_id: node,
              owner_id: one(db, "SELECT owner_id FROM nodes WHERE node_id=?", node)?.owner_id,
            },
          },
    );
  };
  ctx.gateway.channelHandler = (type, p) => {
    if (type === "channels.bootstrap") {
      const result = channels.bootstrap(p.node_id, p.items);
      return {
        type: "channels.bootstrap.result",
        payload: {
          request_id: p.request_id,
          outcome: result.state,
          manifest: { ...result.manifest, request_id: randomUUID() },
        },
      };
    }
    if (type === "channel.status") {
      const result = channels.recordStatus(p);
      if (result.outcome === "accepted")
        ctx.gateway.broadcast([result.owner_id], {
          op: "event",
          event_type: "agent.channel.status_changed",
          data: { agent_id: result.agent_id, channel_id: result.channel_id },
        });
      return {
        type: "channel.status.result",
        payload: { request_id: p.request_id, outcome: result.outcome },
      };
    }
    if (type === "channel.runtime_metadata")
      return {
        type: "channel.runtime_metadata.result",
        payload: {
          request_id: p.request_id,
          outcome: channels.recordProviderMetadata(p),
        },
      };
    if (type === "channel.reconcile.result") {
      const result = channels.recordReconcile(p);
      return {
        type: "channels.reconcile.result.ack",
        payload: {
          request_id: p.request_id,
          manifest_revision: p.manifest_revision,
          ...result,
        },
      };
    }
    fail(400, "unsupported channel message");
  };

  app.get("/health", () => ({ status: "ok" }));
  app.get("/healthz", () => ({ status: "ok" }));
  app.options("/*", (_req, reply) => reply.code(204).send());
  const dist = resolve(
      options.frontendDistDir ?? process.env.IM_FRONTEND_DIST_DIR ?? "src/IM/frontend/dist",
    ),
    dev =
      options.frontendDevBaseUrl ?? process.env.IM_FRONTEND_DEV_BASE_URL ?? "http://127.0.0.1:4173";
  const mime: Row = {
    ".js": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".woff2": "font/woff2",
  };
  app.setNotFoundHandler((req, reply) => {
    const path = req.url.split("?")[0]!;
    if (req.method !== "GET" || path.startsWith("/im/"))
      return reply.code(404).send({ detail: "not found" });
    const file = resolve(dist, "." + path);
    if (file.startsWith(dist + "/") && existsSync(file) && extname(file))
      return reply
        .type(mime[extname(file)] ?? "application/octet-stream")
        .send(createReadStream(file));
    if (
      path === "/" ||
      /^\/(chat|tasks|settings|bind\/confirm|login|register|membership|me)(\/|$)/.test(path)
    ) {
      const index = join(dist, "index.html");
      if (existsSync(index)) return reply.type("text/html").send(createReadStream(index));
      return reply.redirect(dev.replace(/\/$/, "") + req.url);
    }
    return reply.code(404).send({ detail: "not found" });
  });
  const watchdog = setInterval(
    () => {
      const cutoff = new Date(
        Date.now() - Number(process.env.IM_RELAY_WATCHDOG_TIMEOUT_SECONDS ?? 120) * 1000,
      ).toISOString();
      for (const m of all(
        db,
        "SELECT m.id,m.conversation_id FROM messages m LEFT JOIN (SELECT message_id,MAX(created_at) last_evt FROM conversation_events GROUP BY message_id) e ON e.message_id=m.id WHERE m.delivery_status='running' AND COALESCE(e.last_evt,m.created_at)<?",
        cutoff,
      )) {
        const detail = `relay idle for ${process.env.IM_RELAY_WATCHDOG_TIMEOUT_SECONDS ?? 120}s with no new event`;
        db.prepare(
          "UPDATE messages SET delivery_status='failed',content=CASE WHEN content='' THEN ? ELSE content||char(10)||char(10)||? END WHERE id=?",
        ).run(detail, detail, m.id);
        ctx.messaging.event(
          m.conversation_id,
          m.id,
          "relay.failed",
          {
            progress_state: "failed",
            semantic: "relay_watchdog_timeout",
            detail,
            reason: "stalled",
          },
          "failed",
        );
      }
      channels.pruneAppliedRemovals();
    },
    Number(process.env.IM_RELAY_WATCHDOG_INTERVAL_SECONDS ?? 30) * 1000,
  );
  watchdog.unref();
  const guard = setInterval(() => {
    for (const c of ctx.gateway.nodes.values())
      if (Date.now() - c.lastSeen > 90000) ctx.gateway.revokeNode(c.node_id);
    for (const b of ctx.gateway.browsers) if (!ctx.gateway.browserValid(b)) b.socket.close(1008);
  }, 5000);
  guard.unref();
  app.addHook("preClose", async () => {
    ctx.gateway.shutdown();
  });
  app.addHook("onClose", async () => {
    clearInterval(guard);
    clearInterval(watchdog);
    db.close();
  });
  await app.ready();
  return Object.assign(app, { im: ctx });
}
