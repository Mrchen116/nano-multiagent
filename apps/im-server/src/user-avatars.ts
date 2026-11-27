import { randomBytes, randomUUID } from "node:crypto";
import {
  createReadStream,
  existsSync,
  mkdirSync,
  readdirSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import type { Readable } from "node:stream";
import type { FastifyInstance } from "fastify";
import sharp from "sharp";
import { fail, one, params, type ImContext } from "./context.js";
import {
  broadcastUserProfileUpdated,
  canReadUserAvatar,
  isReservedRuntimeUsername,
} from "./human-avatar-projection.js";
import { formatAccountProfile } from "./identity-routes.js";

const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
const AVATAR_BODY_LIMIT = 6 * 1024 * 1024;
const MAX_AVATAR_DIMENSION = 4096;
const ALLOWED_AVATAR_MIMES = new Set(["image/png", "image/jpeg", "image/webp"]);

const avatarLocks = new Map<string, Promise<void>>();

async function withUserAvatarLock<T>(userId: string, fn: () => Promise<T>): Promise<T> {
  const prev = avatarLocks.get(userId) ?? Promise.resolve();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const tail = prev.then(() => gate);
  avatarLocks.set(userId, tail);
  await prev;
  try {
    return await fn();
  } finally {
    release();
    if (avatarLocks.get(userId) === tail) avatarLocks.delete(userId);
  }
}

function detectMagicImageMime(bytes: Buffer): string | null {
  if (bytes.length >= 8 && bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    return "image/png";
  }
  if (bytes.length >= 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) {
    return "image/jpeg";
  }
  if (bytes.length >= 6 && ["GIF87a", "GIF89a"].includes(bytes.subarray(0, 6).toString())) {
    return "image/gif";
  }
  if (bytes.length >= 12 && bytes.subarray(0, 4).toString() === "RIFF" && bytes.subarray(8, 12).toString() === "WEBP") {
    return "image/webp";
  }
  return null;
}

async function readBoundedPayload(bodyStream: unknown): Promise<Buffer> {
  if (Buffer.isBuffer(bodyStream)) {
    if (bodyStream.byteLength > MAX_AVATAR_BYTES) {
      fail(413, { code: "avatar_too_large", message: "Avatar image must be at most 5 MiB." });
    }
    return bodyStream;
  }
  if (!bodyStream || typeof (bodyStream as Readable)[Symbol.asyncIterator] !== "function") {
    return Buffer.alloc(0);
  }
  const stream = bodyStream as Readable;
  const chunks: Buffer[] = [];
  let total = 0;
  const timeout = setTimeout(() => {
    stream.destroy(new Error("avatar upload timed out"));
  }, 60_000);
  try {
    for await (const chunk of stream) {
      const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      total += buf.byteLength;
      if (total > MAX_AVATAR_BYTES) {
        stream.resume();
        fail(413, { code: "avatar_too_large", message: "Avatar image must be at most 5 MiB." });
      }
      chunks.push(buf);
    }
  } finally {
    clearTimeout(timeout);
  }
  return Buffer.concat(chunks, total);
}

async function normalizeUserAvatar(rawBytes: Buffer, declaredMime: string): Promise<Buffer> {
  const formatMap: Record<string, string> = {
    png: "image/png",
    jpeg: "image/jpeg",
    webp: "image/webp",
  };
  let metadata: Awaited<ReturnType<ReturnType<typeof sharp>["metadata"]>>;
  try {
    metadata = await sharp(rawBytes, {
      animated: true,
      limitInputPixels: MAX_AVATAR_DIMENSION * MAX_AVATAR_DIMENSION,
    }).metadata();
  } catch (error) {
    const msg = error instanceof Error ? error.message : "";
    if (/pixel limit/i.test(msg)) {
      fail(422, { code: "avatar_image_unsupported", message: "Avatar dimensions exceed 4096x4096 limit." });
    }
    fail(422, { code: "avatar_image_decode_failed", message: "Failed to decode avatar image." });
  }
  const actualMime = metadata.format ? formatMap[metadata.format] : undefined;
  if (
    !actualMime ||
    actualMime !== declaredMime ||
    (metadata.pages ?? 1) !== 1 ||
    !metadata.width ||
    !metadata.height ||
    metadata.width > MAX_AVATAR_DIMENSION ||
    metadata.height > MAX_AVATAR_DIMENSION
  ) {
    fail(422, {
      code: "avatar_image_unsupported",
      message: "Avatar must be a single-frame static PNG, JPEG, or WebP up to 4096x4096 pixels.",
    });
  }
  try {
    return await sharp(rawBytes, {
      animated: false,
      limitInputPixels: MAX_AVATAR_DIMENSION * MAX_AVATAR_DIMENSION,
    })
      .rotate()
      .resize(256, 256, { fit: "cover", position: "centre" })
      .webp({ quality: 86 })
      .toBuffer();
  } catch {
    fail(422, { code: "avatar_image_decode_failed", message: "Failed to decode avatar image." });
  }
}

/** Register protected human custom avatar upload, removal, and read routes. */
export async function registerUserAvatarRoutes(app: FastifyInstance, ctx: ImContext): Promise<void> {
  const directory = join(dirname(ctx.dbPath), "user-avatars");
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  for (const entry of readdirSync(directory)) {
    if (entry.startsWith(".") && entry.endsWith(".tmp")) {
      try {
        unlinkSync(join(directory, entry));
      } catch {
        // Ignore stale temp cleanup race.
      }
    }
  }

  await app.register(async (uploads) => {
    uploads.removeAllContentTypeParsers();
    uploads.addContentTypeParser("*", (_req, payload, done) => done(null, payload));

    uploads.put("/im/v1/me/avatar", { bodyLimit: AVATAR_BODY_LIMIT }, async (req) => {
      const user = ctx.identity.authenticateRequest(req);
      if (isReservedRuntimeUsername(user.username)) fail(403, "human account required");
      ctx.identity.rateLimit("avatar:write:" + user.id, 15, 60);

      const rawBytes = await readBoundedPayload(req.body);
      const declaredMime = (req.headers["content-type"] ?? "").split(";")[0]!.trim().toLowerCase();
      if (!ALLOWED_AVATAR_MIMES.has(declaredMime)) {
        fail(415, {
          code: "avatar_image_unsupported",
          message: "Unsupported avatar media type; upload static PNG, JPEG, or WebP.",
        });
      }
      if (!rawBytes.byteLength) {
        fail(400, { code: "empty_avatar", message: "Avatar image payload cannot be empty." });
      }
      const detectedMime = detectMagicImageMime(rawBytes);
      if (!detectedMime || detectedMime !== declaredMime || !ALLOWED_AVATAR_MIMES.has(detectedMime)) {
        fail(415, {
          code: "avatar_image_unsupported",
          message: "Image content does not match declared static PNG, JPEG, or WebP type.",
        });
      }

      return withUserAvatarLock(user.id, async () => {
        const normalized = await normalizeUserAvatar(rawBytes, declaredMime);
        const freshUser = ctx.identity.authenticateRequest(req);
        if (isReservedRuntimeUsername(freshUser.username)) fail(403, "human account required");

        const storage = randomUUID().replaceAll("-", "");
        const temporary = join(directory, `.${storage}.tmp`);
        const destination = join(directory, storage);
        let committed = false;
        let previousStorage: string | null = null;

        try {
          writeFileSync(temporary, normalized, { mode: 0o600 });
          renameSync(temporary, destination);
          ctx.identity.transaction(() => {
            const existing = one(
              ctx.db,
              "SELECT avatar_storage_name, avatar_version FROM users WHERE id=?",
              freshUser.id,
            );
            previousStorage = existing?.avatar_storage_name ?? null;
            let nextVersion = randomBytes(6).toString("hex");
            while (nextVersion === existing?.avatar_version) {
              nextVersion = randomBytes(6).toString("hex");
            }
            ctx.db
              .prepare("UPDATE users SET avatar_storage_name=?, avatar_version=?, avatar_content_type='image/webp' WHERE id=?")
              .run(storage, nextVersion, freshUser.id);
          });
          committed = true;
          if (previousStorage && previousStorage !== storage && existsSync(join(directory, previousStorage))) {
            try {
              unlinkSync(join(directory, previousStorage));
            } catch {
              // Best-effort old file removal after DB commit.
            }
          }
          const updated = ctx.identity.user(freshUser.id)!;
          broadcastUserProfileUpdated(ctx, updated);
          return formatAccountProfile(updated);
        } finally {
          if (!committed) {
            for (const candidate of [temporary, destination]) {
              if (existsSync(candidate)) {
                try {
                  unlinkSync(candidate);
                } catch {
                  // Ignore cleanup error on failed upload.
                }
              }
            }
          }
        }
      });
    });
  });

  app.delete("/im/v1/me/avatar", async (req) => {
    const user = ctx.identity.authenticateRequest(req);
    if (isReservedRuntimeUsername(user.username)) fail(403, "human account required");
    ctx.identity.rateLimit("avatar:write:" + user.id, 15, 60);

    return withUserAvatarLock(user.id, async () => {
      const freshUser = ctx.identity.authenticateRequest(req);
      if (isReservedRuntimeUsername(freshUser.username)) fail(403, "human account required");
      let previousStorage: string | null = null;
      ctx.identity.transaction(() => {
        const existing = one(ctx.db, "SELECT avatar_storage_name FROM users WHERE id=?", freshUser.id);
        previousStorage = existing?.avatar_storage_name ?? null;
        ctx.db
          .prepare("UPDATE users SET avatar_storage_name=NULL, avatar_version=NULL, avatar_content_type=NULL WHERE id=?")
          .run(freshUser.id);
      });
      if (previousStorage && existsSync(join(directory, previousStorage))) {
        try {
          unlinkSync(join(directory, previousStorage));
        } catch {
          // Best-effort disk removal after commit.
        }
      }
      const updated = ctx.identity.user(freshUser.id)!;
      broadcastUserProfileUpdated(ctx, updated);
      return formatAccountProfile(updated);
    });
  });

  app.get("/im/v1/users/:user_id/avatar", { config: { selfManagedAuth: true } }, (req, reply) => {
    const viewer = ctx.identity.authenticateRequest(req, false);
    if (isReservedRuntimeUsername(viewer.username)) fail(401, "human session required");
    const targetId = params(req).user_id;
    const target = one(ctx.db, "SELECT * FROM users WHERE id=?", targetId);
    if (!canReadUserAvatar(ctx.db, viewer, target)) fail(404, "avatar not found");
    const filePath = join(directory, target!.avatar_storage_name);
    if (!existsSync(filePath)) fail(404, "avatar not found");
    reply
      .header("Cache-Control", "private, no-store")
      .header("X-Content-Type-Options", "nosniff")
      .header("Content-Security-Policy", "default-src 'none'")
      .type(target!.avatar_content_type || "image/webp");
    return reply.send(createReadStream(filePath));
  });
}
