import { afterEach, expect, it, vi } from "vitest";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Context } from "@deepseek-ai/cordis";
import type { Session } from "@deepseek-ai/dsh-session";

const io = vi.hoisted(() => ({
  bytes: 0,
  fail: undefined as undefined | ((operation: string, path: string, body?: string) => Promise<void>),
}));
vi.mock("node:fs/promises", async importOriginal => {
  const fs = await importOriginal<typeof import("node:fs/promises")>();
  return {
    ...fs,
    writeFile: async (path: string, body: string) => {
      await io.fail?.("write", path, body);
      io.bytes += Buffer.byteLength(body);
      return fs.writeFile(path, body);
    },
  };
});
import { NativeHistory } from "../src/history.js";

const homes: string[] = [];
afterEach(async () => {
  io.fail = undefined;
  io.bytes = 0;
  await Promise.all(homes.splice(0).map(home => rm(home, { recursive: true, force: true })));
});

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>(done => { resolve = done; });
  return { promise, resolve };
}

async function fixture() {
  const home = await mkdtemp(join(tmpdir(), "nano-export-"));
  homes.push(home);
  const sessions = new Map<string, Session>();
  let listener: (session: Session, event: { type: string }) => void = () => {};
  const flush = vi.fn(async (_session: Session) => true);
  const observeSession = vi.fn();
  const ctx = {
    storageDomain: { open: async () => ({ close: async () => {} }) },
    on: (_name: string, callback: typeof listener) => { listener = callback; },
    effect: () => {},
    sessions: { get: (id: string) => sessions.get(id), flush },
    sessionQuery: { observeSession },
    logger: () => ({ warn: () => {} }),
  } as unknown as Context;
  const history = new NativeHistory(ctx, home);
  const create = (id = "source") => {
    const events: any[] = [];
    const session = {
      id, header: { id, agentPreset: "nano:a:1", cwd: home },
      get seq() { return events.length; },
      snapshotEvents: (from = 0, to = events.length) => events.slice(from, to),
    } as unknown as Session;
    sessions.set(id, session);
    const add = (type: string, data: unknown) => {
      events.push({ seq: events.length, type, time: 1_700_000_000_000, data });
    };
    const message = (text: string) => add("user/message", {
      role: "user", source: { kind: "user" }, content: [{ type: "text", text }],
    });
    const end = () => { add("turn/end", {}); listener(session, { type: "turn/end" }); };
    const readable = join(home, ".nanoassistant", "chat_history", `${id}.jsonl`);
    const raw = join(home, "exports", `${Buffer.from(id).toString("base64url")}.jsonl`);
    return { session, events, add, message, end, readable, raw };
  };
  return { home, history, create, flush, sessions, observeSession };
}

const lines = async (path: string) => (await readFile(path, "utf8")).trim().split("\n").filter(Boolean).map(line => JSON.parse(line));

it("does not generate workspace copies or refresh raw snapshots on ordinary turns", async () => {
  const f = await fixture();
  const s = f.create();
  s.message("first"); s.end(); await f.history.stop();
  expect(io.bytes).toBe(0);
  await expect(readFile(s.readable)).rejects.toMatchObject({ code: "ENOENT" });
  await expect(readFile(s.raw)).rejects.toMatchObject({ code: "ENOENT" });
  const original = await readFile(await f.history.path(s.session.id), "utf8");
  io.bytes = 0;
  s.message("next"); s.end(); await f.history.stop();
  expect(io.bytes).toBe(0);
  expect(await readFile(s.raw, "utf8")).toBe(original);
  const published = await lines(await f.history.path(s.session.id));
  expect(published[0]).toMatchObject({ type: "nano-dsh-history", version: 1 });
  expect(published.slice(1)).toEqual(s.events);
  await expect(readFile(s.readable)).rejects.toMatchObject({ code: "ENOENT" });
});

it("coalesces a busy session without losing an export request or blocking another session", async () => {
  const f = await fixture();
  const a = f.create("a"), b = f.create("b");
  const entered = deferred(), release = deferred();
  f.flush.mockImplementation(async session => {
    if (session === a.session) { entered.resolve(); await release.promise; }
    return true;
  });
  a.message("first"); a.end();
  const exported = f.history.path("a");
  await entered.promise;
  const requests = Array.from({ length: 20 }, (_, i) => {
    a.message(`queued ${i}`); a.end();
    return f.history.path("a");
  });
  b.message("independent"); b.end();
  expect((await lines(await f.history.path("b"))).slice(1)).toEqual(b.events);
  release.resolve();
  const path = await exported;
  await Promise.all(requests);
  await f.history.stop();
  expect((await lines(path)).slice(1)).toEqual(a.events);
});

it("exports only the cut captured before the persistence barrier", async () => {
  const f = await fixture();
  const s = f.create();
  const entered = deferred(), release = deferred();
  f.flush.mockImplementationOnce(async () => { entered.resolve(); await release.promise; return true; });
  s.message("persisted");
  const exported = f.history.path(s.session.id);
  await entered.promise;
  s.message("arrived during flush");
  release.resolve();
  expect(JSON.stringify(await lines(await exported))).not.toContain("arrived during flush");
  expect(JSON.stringify(await lines(await f.history.path(s.session.id)))).toContain("arrived during flush");
});

it("keeps a complete published snapshot after failure and retries only on request", async () => {
  const f = await fixture();
  const s = f.create();
  s.message("old");
  const original = await readFile(await f.history.path(s.session.id), "utf8");
  s.message("new");
  io.fail = async (operation, path) => {
    if (operation === "write" && path === `${s.raw}.tmp`) throw new Error("raw disk failure");
  };
  await expect(f.history.path(s.session.id)).rejects.toThrow("raw disk failure");
  expect(await readFile(s.raw, "utf8")).toBe(original);
  io.fail = undefined;
  s.message("later"); s.end(); await f.history.stop();
  expect(await readFile(s.raw, "utf8")).toBe(original);
  expect((await lines(await f.history.path(s.session.id))).slice(1)).toEqual(s.events);
});

it("exports cold native history without changing an existing workspace copy", async () => {
  const f = await fixture();
  const s = f.create();
  s.message("native history");
  await mkdir(join(f.home, ".nanoassistant", "chat_history"), { recursive: true });
  await writeFile(s.readable, "untouched legacy bytes");
  f.sessions.delete(s.session.id);
  f.observeSession.mockResolvedValue({ source: "prepared", header: s.session.header, events: s.events, [Symbol.dispose]() {} });
  expect((await lines(await f.history.path(s.session.id))).slice(1)).toEqual(s.events);
  expect(await readFile(s.readable, "utf8")).toBe("untouched legacy bytes");
});

it("fulfills a newer explicit request queued during a failed publication", async () => {
  const f = await fixture();
  const s = f.create();
  s.message("first"); s.end(); await f.history.stop();
  const entered = deferred(), release = deferred();
  let failed = false;
  io.fail = async (operation, path) => {
    if (!failed && operation === "write" && path === `${s.raw}.tmp`) {
      failed = true;
      entered.resolve();
      await release.promise;
      throw new Error("interrupted publication");
    }
  };
  const exported = f.history.path(s.session.id);
  await entered.promise;
  s.message("during failure"); s.end();
  const requested = f.history.path(s.session.id);
  const stopped = f.history.stop();
  release.resolve();
  await stopped;
  expect((await lines(await exported)).slice(1)).toEqual(s.events);
  expect(await requested).toBe(await exported);
});

it("requires persistence when a cold query becomes live before observation returns", async () => {
  const f = await fixture();
  const s = f.create(); s.message("not yet durable");
  f.sessions.delete(s.session.id);
  f.observeSession.mockImplementation(async () => {
    f.sessions.set(s.session.id, s.session);
    return { source: "live", header: s.session.header, events: s.events, [Symbol.dispose]() {} };
  });
  f.flush.mockResolvedValue(false);
  await expect(f.history.path(s.session.id)).rejects.toThrow("persistence barrier");
  await expect(readFile(s.raw)).rejects.toMatchObject({ code: "ENOENT" });
  f.flush.mockResolvedValue(true);
  expect((await lines(await f.history.path(s.session.id))).slice(1)).toEqual(s.events);
});
