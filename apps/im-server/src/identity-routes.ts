import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import { isIP } from "node:net";
import type { ImContext } from "./context.js";
import { body, params, query } from "./context.js";
import { IdentityError, bearer, type User } from "./identity.js";

type Row = Record<string, any>;
function string(input: Row, key: string, minimum = 0, maximum = Infinity): string {
  const value = input[key];
  if (typeof value !== "string" || [...value].length < minimum || [...value].length > maximum)
    throw new IdentityError(422, `${key} has invalid length or type`);
  return value;
}
const browser = (request: FastifyRequest) => request.headers["x-im-session"] === "browser";
function account(user: User) {
  return Object.fromEntries(
    [
      "id",
      "username",
      "display_name",
      "owner_id",
      "owned_node_ids",
      "default_entry_node_id",
      "locale",
      "created_at",
    ]
      .map((key) => [key, user[key]])
      .concat([["user_id", user.id]]),
  );
}
/** Register identity routes with the existing JSON and browser Cookie transports. */
export function registerIdentityRoutes(app: FastifyInstance, ctx: ImContext) {
  const identity = ctx.identity;
  const cookie = (value: string, age: number) =>
    `im_refresh=${value}; Max-Age=${age}; Path=/; HttpOnly; SameSite=Strict${new URL(ctx.publicUrl).protocol === "https:" ? "; Secure" : ""}`;
  const respond = (pair: Row, request: FastifyRequest, reply: FastifyReply) => {
    reply.header("Cache-Control", "no-store");
    if (!browser(request)) return pair;
    reply.header("Set-Cookie", cookie(pair.refresh_token, identity.refreshTtl));
    return { access_token: pair.access_token, user: pair.user };
  };
  const credential = (request: FastifyRequest): string | undefined => {
    const payload = body(request);
    if (browser(request)) {
      if (payload.refresh_token != null)
        throw new IdentityError(422, "browser session uses Cookie only");
      return request.headers.cookie
        ?.split(";")
        .map((v) => v.trim())
        .find((v) => v.startsWith("im_refresh="))
        ?.slice("im_refresh=".length);
    }
    return string(payload, "refresh_token", 1);
  };
  const admin = (request: FastifyRequest): User => {
    const user = identity.authenticateRequest(request);
    if (!user.is_company_admin) throw new IdentityError(403, "company administrator required");
    return user;
  };
  const source = (request: FastifyRequest) => {
    const peer = request.raw.socket.remoteAddress ?? request.ip;
    const forwarded = request.headers["cf-connecting-ip"];
    return process.env.IM_TRUSTED_PROXY === peer && typeof forwarded === "string" && isIP(forwarded)
      ? forwarded
      : peer;
  };
  app.addHook("preHandler", async (request) => {
    const path = request.url.split("?")[0]!;
    if (path === "/im/v1/auth/register") {
      identity.rateLimit("register:source:" + source(request), 5, 900);
      identity.rateLimit("register:service", 100, 3600);
    } else if (path === "/im/v1/auth/login")
      identity.rateLimit("login:source:" + source(request), 30, 300);
    else if (path === "/im/v1/auth/refresh")
      identity.rateLimit("refresh:source:" + source(request), 60, 60);
    else if (path.startsWith("/im/v1/device-binding/"))
      identity.rateLimit("bind:source:" + source(request), 60, 60);
    if (
      browser(request) &&
      [
        "/im/v1/auth/register",
        "/im/v1/auth/login",
        "/im/v1/auth/refresh",
        "/im/v1/auth/logout",
      ].includes(path)
    ) {
      const allowed = [
        new URL(ctx.publicUrl).origin,
        ...(process.env.IM_BROWSER_ORIGINS ?? "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      ];
      if (typeof request.headers.origin !== "string" || !allowed.includes(request.headers.origin))
        throw new IdentityError(403, "browser origin not allowed");
    }
  });
  app.post("/im/v1/auth/register", async (request, reply) => {
    const payload = body(request);
    const pair = await identity.register(
      string(payload, "username", 1, 64),
      string(payload, "password", 1, 256),
      string(payload, "display_name", 1, 128),
      payload.locale === undefined ? "en" : string(payload, "locale", 0, 8),
    );
    reply.code(201);
    return respond(pair, request, reply);
  });
  app.post("/im/v1/auth/login", async (request, reply) => {
    const payload = body(request),
      username = string(payload, "username", 1, 64),
      password = string(payload, "password", 1, 256);
    const accountName = username.trim().toLowerCase(),
      failureKey = "login:failure:" + source(request) + ":" + accountName;
    identity.rateLimit(failureKey, 10, 900, false);
    identity.rateLimit("login:target:" + accountName, 1, 1);
    let pair;
    try {
      pair = await identity.login(username, password);
    } catch (error) {
      if (error instanceof IdentityError && error.statusCode === 401)
        identity.rateLimit(failureKey, 10, 900);
      throw error;
    }
    identity.clearLimit(failureKey);
    return respond(pair, request, reply);
  });
  app.post("/im/v1/auth/refresh", async (request, reply) => {
    const token = credential(request);
    if (!token) throw new IdentityError(401, "missing refresh cookie");
    identity.rateLimit("refresh:credential:" + token, 20, 60);
    return respond(identity.refresh(token), request, reply);
  });
  app.post("/im/v1/auth/logout", async (request, reply) => {
    const token = credential(request);
    try {
      if (token) await ctx.gateway.closeSession(identity.logout(token));
    } catch (error) {
      if (!(error instanceof IdentityError) || !browser(request)) throw error;
    }
    reply.header("Cache-Control", "no-store");
    if (browser(request)) reply.header("Set-Cookie", cookie("", 0));
    return { ok: true };
  });
  app.get("/im/v1/auth/me", async (request) =>
    identity.publicUser(identity.authenticateRequest(request, false)),
  );
  app.post("/im/v1/auth/ws-ticket", async (request) => {
    identity.authenticateRequest(request);
    const session = identity.accessSession(bearer(request));
    identity.rateLimit("ws-ticket:" + session.sid, 10, 60);
    return { ticket: identity.issueTicket(session.sid), expires_in: 30 };
  });
  app.get("/im/v1/me", async (request) => account(identity.authenticateRequest(request)));
  app.patch("/im/v1/me", async (request) => {
    const user = identity.authenticateRequest(request),
      payload = body(request),
      displayName = string(payload, "display_name", 1);
    if (!displayName.trim()) throw new IdentityError(400, "display_name must be non-empty");
    const defaultNode =
      payload.default_entry_node_id == null
        ? null
        : string(payload, "default_entry_node_id").trim() || null;
    if (defaultNode && !user.owned_node_ids.includes(defaultNode))
      throw new IdentityError(400, "default_entry_node_id not owned by user");
    const locale =
      payload.locale == null ? user.locale : string(payload, "locale", 0, 8).trim() || user.locale;
    identity.run(
      "UPDATE users SET display_name=?,default_entry_node_id=?,locale=? WHERE id=?",
      displayName,
      defaultNode,
      locale,
      user.id,
    );
    return account(identity.user(user.id)!);
  });
  app.post("/im/v1/bind", async (request) => {
    identity.authenticateRequest(request);
    const payload = body(request);
    if (!["start", "confirm"].includes(payload.action))
      throw new IdentityError(422, "invalid bind action");
    if (payload.action === "start" && !payload.node_id)
      throw new IdentityError(400, "node_id is required for start");
    if (payload.action === "confirm" && !payload.bind_id && !payload.bind_token)
      throw new IdentityError(400, "bind_id or bind_token is required for confirm");
    throw new IdentityError(400, "device proof required; use local Gateway binding");
  });
  app.get("/im/v1/company/members", async (request) => {
    admin(request);
    const cursor = query(request).cursor ?? "";
    if (typeof cursor !== "string" || cursor.length > 128)
      throw new IdentityError(422, "invalid cursor");
    const rows = identity.all(
      "SELECT u.id,u.username,u.display_name,u.membership_status,u.is_company_admin,(SELECT count(*) FROM nodes n WHERE n.owner_id=u.id) AS node_count,(SELECT count(*) FROM agent_profiles a WHERE a.owner_id=u.id AND a.is_stale=0) AS agent_count FROM users u WHERE u.password_hash IS NOT NULL AND u.password_hash!='' AND u.id>? ORDER BY u.id LIMIT 51",
      cursor,
    );
    return {
      members: rows.slice(0, 50).map((row) => ({
        ...row,
        is_company_admin: Boolean(row.is_company_admin),
      })),
      next_cursor: rows.length > 50 ? rows[49]!.id : null,
    };
  });
  app.post("/im/v1/company/members/:user_id/:action", async (request) => {
    const actor = admin(request),
      { user_id, action } = params(request);
    const user = identity.transition(actor.id, user_id, action);
    if (action === "suspend") {
      await ctx.gateway.closeUser(user_id);
      await ctx.gateway.revokeOwner(user_id);
    }
    return identity.publicUser(user);
  });
  app.post("/im/v1/device-binding/start", async (request) => {
    const payload = body(request);
    const result = identity.deviceStart({
      node_id: string(payload, "node_id", 1, 128),
      node_name: string(payload, "node_name", 1, 256),
      public_key: string(payload, "public_key", 0, 128),
      key_id: string(payload, "key_id", 0, 128),
    });
    return {
      ...result,
      bind_url: ctx.publicUrl.replace(/\/$/, "") + "/bind/confirm#token=" + result.browser_token,
    };
  });
  for (const action of ["inspect", "accept", "decline"] as const)
    app.post("/im/v1/device-binding/" + action, async (request) =>
      identity.deviceBrowser(
        action,
        string(body(request), "browser_token", 0, 128),
        identity.authenticateRequest(request).id,
      ),
    );
  for (const action of [
    "prove",
    "prepare",
    "commit",
    "recover",
    "recover-device",
    "cancel",
  ] as const)
    app.post("/im/v1/device-binding/" + action, async (request) => {
      const payload = body(request),
        id = string(payload, "operation_id", 0, 128),
        token = string(payload, "operation_token", 0, 128);
      if (action === "prove")
        return identity.deviceProve(id, token, string(payload, "challenge", 0, 128));
      if (action === "prepare") return identity.devicePrepare(id, token);
      if (action === "recover") return identity.deviceRecover(id, token);
      if (action === "cancel") return identity.deviceCancel(id, token);
      const envelopes = payload.envelopes ?? {};
      if (typeof envelopes !== "object" || Array.isArray(envelopes))
        throw new IdentityError(422, "envelopes must be an object");
      const result =
        action === "commit"
          ? identity.deviceCommit(id, token, string(payload, "proof", 0, 128), envelopes)
          : identity.deviceRecoverDevice(id, token);
      await ctx.gateway.revokeNode(identity.deviceRecover(id, token).node_id);
      return result;
    });
}
