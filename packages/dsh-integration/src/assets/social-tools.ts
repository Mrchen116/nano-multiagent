/** Native declarations for the owner's four existing single-item social readers. */
import { spawn } from "node:child_process";
import { stat, realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import type { Context } from "@deepseek-ai/cordis";
import { load } from "js-yaml";

interface Config {
  opencli?: string;
  opencliCwd?: string;
  douyin?: string;
  douyinCwd?: string;
  downloadDir?: string;
}
class ReaderError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}
const fail = (code: string, message: string): never => {
  throw new ReaderError(code, message);
};
const text = (value: unknown, field: string, limit: number): string =>
  value == null
    ? ""
    : typeof value !== "string"
      ? fail("invalid_output", `Invalid ${field}`)
      : value.length > limit
        ? fail("output_too_large", `${field} is too large`)
        : value;
const object = (value: unknown): Record<string, any> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, any>)
    : fail("invalid_output", "Expected structured reader output");

/** Validate the original one-item URL contract before starting any subprocess. */
export function socialUrl(tool: string, args: unknown) {
  const input = object(args);
  const value = input.url;
  if (
    Object.keys(input).length !== 1 ||
    typeof value !== "string" ||
    value.length > 2048 ||
    /[\x00-\x20\x7f]/.test(value)
  )
    fail("invalid_input", "Exactly one canonical URL is required");
  let match: RegExpMatchArray | null;
  if (tool === "read_x_post") {
    match = value.match(
      /^https:\/\/x\.com\/([A-Za-z0-9_]{1,15})\/status\/([1-9][0-9]*)$/,
    );
    if (!match)
      fail("invalid_input", "Only https://x.com/<user>/status/<id> is allowed");
    return { url: value as string, id: match![2]!, author: match![1]! };
  }
  if (tool === "read_xiaohongshu_note") {
    match = value.match(
      /^https:\/\/www\.xiaohongshu\.com\/(?:explore|search_result|note)\/([0-9a-fA-F]{24})\?([^#]+)$/,
    );
    if (!match)
      fail(
        "invalid_input",
        "One complete signed Xiaohongshu note URL is required",
      );
    const pairs = [...new URL(value).searchParams];
    const tokens = pairs.filter(([key]) => key === "xsec_token");
    if (
      tokens.length !== 1 ||
      pairs.filter(([key]) => key === "xsec_source").length > 1 ||
      pairs.some(([key]) => !["xsec_token", "xsec_source"].includes(key)) ||
      !tokens[0]![1] ||
      tokens[0]![1].length > 512 ||
      /[\x00-\x20]/.test(tokens[0]![1])
    )
      fail("invalid_input", "Invalid Xiaohongshu signature parameters");
    return { url: value as string, id: match![1]!.toLowerCase() };
  }
  match = value.match(/^https:\/\/www\.douyin\.com\/video\/([1-9][0-9]*)$/);
  if (!match)
    fail("invalid_input", "Only https://www.douyin.com/video/<id> is allowed");
  return { url: value as string, id: match![1]! };
}

async function run(
  command: string,
  args: string[],
  cwd: string,
  timeout: number,
  signal: AbortSignal,
): Promise<string> {
  signal.throwIfAborted();
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, CI: "1" },
    stdio: ["ignore", "pipe", "pipe"],
    detached: process.platform !== "win32",
  });
  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  let bytes = 0;
  let failure: ReaderError | undefined;
  const kill = () => {
    if (!child.pid) return;
    try {
      if (process.platform === "win32") child.kill("SIGKILL");
      else process.kill(-child.pid, "SIGKILL");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
    }
  };
  const take = (target: Buffer[], chunk: Buffer) => {
    bytes += chunk.length;
    if (bytes > 64 * 1024) {
      failure = new ReaderError(
        "output_too_large",
        "The single-item reader returned too much data",
      );
      kill();
    } else target.push(chunk);
  };
  child.stdout.on("data", (chunk) => take(stdout, chunk));
  child.stderr.on("data", (chunk) => take(stderr, chunk));
  signal.addEventListener("abort", kill, { once: true });
  const timer = setTimeout(() => {
    failure = new ReaderError("timeout", "The single-item operation timed out");
    kill();
  }, timeout);
  try {
    const code = await new Promise<number | null>((accept, reject) => {
      child.once("error", () =>
        reject(
          new ReaderError(
            "unavailable",
            "The installed social reader is unavailable",
          ),
        ),
      );
      child.once("close", accept);
    });
    signal.throwIfAborted();
    if (failure) throw failure;
    if (code !== 0) {
      const message = Buffer.concat([...stdout, ...stderr])
        .toString()
        .toLowerCase();
      fail(
        /auth_required|captcha|rate limit|too many requests|risk control|verification required|http 429/.test(
          message,
        )
          ? "risk_control"
          : "upstream_failed",
        "The platform reader could not complete this single-item operation",
      );
    }
    return Buffer.concat(stdout).toString("utf8");
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", kill);
  }
}
const network = (value: any) => ({
  request_counts: Object.fromEntries(
    Object.entries(value?.counts ?? {}).filter(
      ([, n]) => Number.isInteger(n) && Number(n) >= 0 && Number(n) <= 10,
    ),
  ),
  http_statuses: Object.fromEntries(
    Object.entries(value?.statuses ?? {}).filter(
      ([, n]) => Number.isInteger(n) && Number(n) >= 100 && Number(n) <= 599,
    ),
  ),
  retries:
    Number.isInteger(value?.retries) &&
    value.retries >= 0 &&
    value.retries <= 10
      ? value.retries
      : 0,
});
const descriptions = {
  read_x_post:
    "Read exactly one canonical X post URL: author, text, ID and time. No search, timeline, replies, interaction or browser UI.",
  read_xiaohongshu_note:
    "Read exactly one complete signed Xiaohongshu note URL: ID, author, title and body. No search, feed, comments or interaction.",
  read_douyin_video:
    "Read metadata for exactly one canonical Douyin video URL without Cookie or downloading. No search, feed, comments or interaction.",
  download_douyin_video:
    "Download exactly one canonical Douyin video URL to the configured local Douyin directory, only when the user explicitly asks for that download. No search, batch or interaction.",
};
export const name = "nano-social-tools";
export const inject = ["tools"];

/** Opt-in owner/workspace plugin; it never changes or executes legacy Python tools. */
export function apply(ctx: Context, config: Config = {}) {
  const home = homedir();
  const paths = {
    opencli: config.opencli ?? join(home, ".local/bin/opencli"),
    opencliCwd: config.opencliCwd ?? join(home, ".agent-reach"),
    douyin: config.douyin ?? join(home, ".local/bin/parsehub-douyin-once"),
    douyinCwd:
      config.douyinCwd ?? join(home, ".local/share/parsehub-experiment"),
    downloadDir:
      config.downloadDir ?? join(home, ".nanoassistant/downloads/douyin"),
  };
  for (const [name, description] of Object.entries(descriptions))
    ctx.tools.register({
      name,
      description,
      parameters: {
        type: "object",
        properties: { url: { type: "string", minLength: 1, maxLength: 2048 } },
        required: ["url"],
        additionalProperties: false,
      },
      output: {
        schema: { type: "object" },
        render: (_args, value) => [
          { type: "text", text: JSON.stringify(value) },
        ],
      },
      timeoutMs: name === "download_douyin_video" ? 130_000 : 60_000,
      isConcurrencySafe: () => false,
      async execute(args, exec) {
        try {
          const target = socialUrl(name, args);
          if (name === "read_x_post") {
            const payload = load(
              await run(
                paths.opencli,
                ["twitter", "thread", target.url, "--limit", "1", "-f", "yaml"],
                paths.opencliCwd,
                45_000,
                exec.signal,
              ),
            );
            if (!Array.isArray(payload) || payload.length !== 1)
              fail(
                "invalid_output",
                "X reader did not return exactly one post",
              );
            const post = object((payload as unknown[])[0]);
            if (
              post.id !== target.id ||
              String(post.author).toLowerCase() !==
                target.author?.toLowerCase() ||
              post.url !== target.url
            )
              fail("item_mismatch", "X reader returned a different post");
            return {
              ok: true,
              post: {
                id: target.id,
                url: target.url,
                author: text(post.author, "author", 64),
                text: text(post.text, "text", 16_000),
                created_at: text(post.created_at, "time", 128),
                has_media: !!post.has_media,
              },
            };
          }
          if (name === "read_xiaohongshu_note") {
            const payload = load(
              await run(
                paths.opencli,
                ["xiaohongshu", "note", target.url, "-f", "yaml"],
                paths.opencliCwd,
                45_000,
                exec.signal,
              ),
            );
            if (
              !Array.isArray(payload) ||
              !payload.length ||
              payload.length > 20
            )
              fail("invalid_output", "Invalid note data");
            const fields: Record<string, unknown> = {};
            for (const item of payload as unknown[]) {
              const row = object(item);
              if (
                typeof row.field !== "string" ||
                Object.hasOwn(fields, row.field)
              )
                fail("invalid_output", "Invalid or duplicate note fields");
              fields[row.field] = row.value;
            }
            return {
              ok: true,
              note: {
                id: target.id,
                author: text(fields.author, "author", 256),
                title: text(fields.title, "title", 2000),
                content: text(fields.content, "content", 16000),
                tags: text(fields.tags, "tags", 2000),
                metrics: Object.fromEntries(
                  ["likes", "collects", "comments"].map((key) => [
                    key,
                    text(fields[key], key, 32),
                  ]),
                ),
              },
            };
          }
          const download = name === "download_douyin_video";
          const payload = object(
            JSON.parse(
              await run(
                paths.douyin,
                [download ? "download" : "read", target.url],
                paths.douyinCwd,
                download ? 120_000 : 50_000,
                exec.signal,
              ),
            ),
          );
          if (payload.ok !== true)
            fail(
              "upstream_failed",
              "The no-Cookie Douyin reader could not complete this operation",
            );
          if (download) {
            const file = object(payload.download);
            const expected = join(
              await realpath(paths.downloadDir),
              `${target.id}.mp4`,
            );
            if (
              typeof file.path !== "string" ||
              (await realpath(file.path)) !== expected
            )
              fail("invalid_output", "Unexpected download file path");
            const info = await stat(expected);
            if (
              !info.isFile() ||
              !Number.isInteger(file.size_bytes) ||
              file.size_bytes <= 0 ||
              file.size_bytes !== info.size ||
              !/^[0-9a-f]{64}$/.test(file.sha256)
            )
              fail("invalid_output", "Invalid download file evidence");
            return {
              ok: true,
              work_id: target.id,
              path: expected,
              size_bytes: info.size,
              content_type: "video/mp4",
              sha256: file.sha256,
              reused: file.reused === true,
              network: network(payload.network),
            };
          }
          const work = object(payload.work);
          const author = object(work.author);
          const media = object(work.media);
          if (
            String(work.id) !== target.id ||
            work.canonical_url !== target.url
          )
            fail("item_mismatch", "Douyin reader returned a different video");
          return {
            ok: true,
            video: {
              id: target.id,
              url: target.url,
              author: {
                nickname: text(author.nickname, "nickname", 256),
                unique_id: text(author.unique_id, "author id", 256),
              },
              text: text(work.text, "text", 16000),
              media: {
                type: "video",
                available: media.available === true,
                ext: text(media.ext, "extension", 16),
                width: Number.isInteger(media.width) ? media.width : null,
                height: Number.isInteger(media.height) ? media.height : null,
                duration_ms: Number.isInteger(media.duration_ms)
                  ? media.duration_ms
                  : null,
              },
            },
            network: network(payload.network),
          };
        } catch (error) {
          exec.signal.throwIfAborted();
          return {
            ok: false,
            error: {
              code:
                error instanceof ReaderError ? error.code : "operation_failed",
              message:
                error instanceof ReaderError
                  ? error.message
                  : "The single-item social operation failed",
            },
          };
        }
      },
    });
}
