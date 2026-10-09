import { createHash, randomUUID } from "node:crypto";
import {
  createReadStream,
  createWriteStream,
  mkdirSync,
  existsSync,
  unlinkSync,
  renameSync,
} from "node:fs";
import { basename, dirname, join } from "node:path";
import { once } from "node:events";
import type { Readable } from "node:stream";
import type { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import { all, one, fail, params, query, body, type Row, type ImContext } from "./context.js";
const MAX_BYTES = 10 * 1024 * 1024,
  OWNER_LIMIT = 1024 ** 3,
  SERVICE_LIMIT = 10 * 1024 ** 3;
const IMAGES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
const ALLOWED = new Set([
  ...IMAGES,
  "application/pdf",
  "text/plain",
  "text/markdown",
  "application/json",
]);
function imageType(bytes: Buffer) {
  if (bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])))
    return "image/png";
  if (bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return "image/jpeg";
  if (["GIF87a", "GIF89a"].includes(bytes.subarray(0, 6).toString())) return "image/gif";
  if (bytes.subarray(0, 4).toString() === "RIFF" && bytes.subarray(8, 12).toString() === "WEBP")
    return "image/webp";
  return null;
}
export async function registerMediaRoutes(app: FastifyInstance, ctx: ImContext) {
  const db = ctx.db,
    directory = join(dirname(ctx.dbPath), "message-images");
  mkdirSync(directory, { recursive: true });
  const slots = new Map<string, number>();
  // Interrupted reservations never become committed resources after a process restart.
  for (const r of all(db, "SELECT storage_name FROM attachment_storage WHERE state='reserved'")) {
    for (const path of [join(directory, r.storage_name), join(directory, `.${r.storage_name}.tmp`)])
      if (existsSync(path)) unlinkSync(path);
  }
  db.prepare("DELETE FROM attachment_storage WHERE state='reserved'").run();
  const read = (req: FastifyRequest, reply: FastifyReply) => {
    const p = ctx.messaging.principal(req),
      r = params(req);
    ctx.messaging.access(p, r.conversation_id, query(req).agent_id);
    const resource = one(
      db,
      "SELECT * FROM message_images WHERE conversation_id=? AND image_id=?",
      r.conversation_id,
      r.image_id ?? r.resource_id,
    );
    if (!resource || !existsSync(join(directory, resource.storage_name)))
      fail(404, "attachment not found");
    reply.header("Cache-Control", "private, no-store").type(resource.content_type);
    if (!IMAGES.has(resource.content_type))
      reply.header(
        "Content-Disposition",
        `attachment; filename*=UTF-8''${encodeURIComponent(resource.file_name)}`,
      );
    return reply.send(createReadStream(join(directory, resource.storage_name)));
  };
  app.get("/im/v1/conversations/:conversation_id/images/:image_id", read);
  app.get("/im/v1/conversations/:conversation_id/attachments/:resource_id", read);
  app.get("/im/v1/attachments/capacity", (req) => {
    const p = ctx.identity.authenticateRequest(req);
    if (!p.is_company_admin) fail(403, "company administrator required");
    const service: Row = {
        used_bytes: 0,
        reserved_bytes: 0,
        limit_bytes: SERVICE_LIMIT,
      },
      owners = new Map<string, Row>();
    for (const r of all(
      db,
      "SELECT a.owner_id,a.state,SUM(a.byte_size) size,u.username,u.display_name FROM attachment_storage a LEFT JOIN users u ON u.id=a.owner_id GROUP BY a.owner_id,a.state",
    )) {
      const key = r.state === "stored" ? "used_bytes" : "reserved_bytes";
      service[key] += r.size;
      if (r.owner_id) {
        const owner = owners.get(r.owner_id) ?? {
          owner_id: r.owner_id,
          username: r.username,
          display_name: r.display_name,
          used_bytes: 0,
          reserved_bytes: 0,
          limit_bytes: OWNER_LIMIT,
        };
        owner[key] += r.size;
        owners.set(r.owner_id, owner);
      }
    }
    for (const item of [service, ...owners.values()])
      item.full = item.used_bytes + item.reserved_bytes >= item.limit_bytes;
    return { service, owners: [...owners.values()] };
  });
  app.post("/im/v1/image-delivery/target", (req) => {
    const p = ctx.messaging.principal(req),
      b = body(req);
    if (p.kind !== "gateway") fail(401, "gateway credential required");
    const a = one(
      db,
      "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND owner_id=? AND is_stale=0",
      b.agent_id,
      p.node_id,
      p.owner_id,
    );
    if (!a) fail(404, "target not accessible");
    return {
      conversation_id: ctx.messaging.resolveTarget(b.agent_id, b.target),
    };
  });
  await app.register(async (uploads) => {
    uploads.removeAllContentTypeParsers();
    uploads.addContentTypeParser("*", (req, payload, done) => done(null, payload));
    const upload = async (req: FastifyRequest, reply: FastifyReply) => {
      const p = ctx.messaging.principal(req),
        q = query(req),
        cId = params(req)?.conversation_id ?? q.conversation_id,
        isImage = req.url.split("?")[0]!.endsWith("/images");
      ctx.messaging.access(p, cId, q.agent_id);
      const fileName = basename(String(q.file_name ?? "").trim()),
        key = isImage
          ? String(req.headers["idempotency-key"] ?? "").trim()
          : `upload:${randomUUID()}`;
      if (!fileName || !key) fail(400, "file_name and Idempotency-Key required");
      const mime = (req.headers["content-type"] ?? "application/octet-stream")
        .split(";")[0]!
        .trim()
        .toLowerCase();
      if (!(isImage ? IMAGES : ALLOWED).has(mime)) fail(415, "unsupported content_type");
      const owner = p.kind === "gateway" ? p.owner_id : p.id;
      ctx.identity.rateLimit(`upload:${owner}`, 30, 60);
      if ((slots.get(owner) ?? 0) >= 2) fail(429, "too many concurrent uploads");
      slots.set(owner, (slots.get(owner) ?? 0) + 1);
      const storage = randomUUID().replaceAll("-", ""),
        temporary = join(directory, `.${storage}.tmp`),
        destination = join(directory, storage);
      let size = 0,
        head = Buffer.alloc(0),
        committed = false;
      const hash = createHash("sha256");
      db.prepare(
        "INSERT INTO attachment_storage(storage_name,owner_id,byte_size,state) VALUES(?,?,0,'reserved')",
      ).run(storage, owner);
      const output = createWriteStream(temporary, { flags: "wx", mode: 0o600 });
      try {
        const timeout = setTimeout(() => {
          (req.body as Readable).destroy(new Error("upload timed out"));
        }, 60000);
        try {
          for await (const chunk of req.body as Readable) {
            const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
            size += bytes.length;
            if (size > MAX_BYTES) fail(413, "attachment too large");
            const used = one(db, "SELECT COALESCE(SUM(byte_size),0) n FROM attachment_storage")!.n,
              ownerUsed = one(
                db,
                "SELECT COALESCE(SUM(byte_size),0) n FROM attachment_storage WHERE owner_id=?",
                owner,
              )!.n;
            if (used + bytes.length > SERVICE_LIMIT || ownerUsed + bytes.length > OWNER_LIMIT)
              fail(507, "attachment storage unavailable");
            db.prepare("UPDATE attachment_storage SET byte_size=? WHERE storage_name=?").run(
              size,
              storage,
            );
            if (head.length < 12) head = Buffer.concat([head, bytes]).subarray(0, 12);
            hash.update(bytes);
            if (!output.write(bytes)) await once(output, "drain");
          }
        } finally {
          clearTimeout(timeout);
        }
        output.end();
        await once(output, "finish");
        if (!size) fail(400, "empty attachment");
        if (IMAGES.has(mime) && imageType(head) !== mime)
          fail(415, "image content does not match content type");
        const fresh = ctx.messaging.principal(req);
        ctx.messaging.access(fresh, cId, q.agent_id);
        const digest = hash.digest("hex"),
          old = one(
            db,
            "SELECT * FROM message_images WHERE conversation_id=? AND source_key=?",
            cId,
            key,
          );
        if (old) {
          if (old.sha256 !== digest || old.content_type !== mime)
            fail(409, "idempotency key conflicts with existing image");
          reply.code(200);
          return {
            url: `/im/v1/conversations/${cId}/${isImage ? "images" : "attachments"}/${old.image_id}`,
            content_type: old.content_type,
            file_name: old.file_name,
          };
        }
        const id = randomUUID().replaceAll("-", "");
        renameSync(temporary, destination);
        db.prepare("INSERT INTO message_images VALUES(?,?,?,?,?,?,?,?)").run(
          id,
          cId,
          key,
          digest,
          mime,
          fileName,
          size,
          storage,
        );
        db.prepare("UPDATE attachment_storage SET state='stored' WHERE storage_name=?").run(
          storage,
        );
        committed = true;
        reply.code(201);
        return {
          url: `/im/v1/conversations/${cId}/${isImage ? "images" : "attachments"}/${id}`,
          content_type: mime,
          file_name: fileName,
        };
      } finally {
        slots.set(owner, (slots.get(owner) ?? 1) - 1);
        if (!committed) {
          output.destroy();
          for (const path of [temporary, destination]) if (existsSync(path)) unlinkSync(path);
          db.prepare("DELETE FROM attachment_storage WHERE storage_name=?").run(storage);
        }
      }
    };
    uploads.post("/im/v1/uploads", upload);
    uploads.post("/im/v1/conversations/:conversation_id/images", upload);
  });
}
