import { afterEach, expect, it, vi } from "vitest";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
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
    appendFile: async (path: string, body: string) => {
      await io.fail?.("append", path, body);
      io.bytes += Buffer.byteLength(body);
      return fs.appendFile(path, body);
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
  let listener!: (session: Session, event: { type: string }) => void;
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

it("writes only new readable messages on warm turns and publishes raw snapshots on request", async () => {
  const f = await fixture();
  const s = f.create();
  for (let i = 0; i < 256; i++) s.add("tool/result", { text: "x".repeat(4096) });
  s.message("inherited prefix"); s.end();
  await f.history.stop();
  const original = await readFile(await f.history.path(s.session.id), "utf8");
  io.bytes = 0;
  for (let i = 0; i < 10; i++) { s.message(`new ${i}`); s.end(); await f.history.stop(); }
  // Filesystem payload is the performance boundary, independent of queue representation.
  expect(io.bytes).toBeLessThan(5000);
  expect((await lines(s.readable)).map(row => row.content)).toEqual(["inherited prefix", ...Array.from({ length: 10 }, (_, i) => `new ${i}`)]);
  expect(await readFile(s.raw, "utf8")).toBe(original);
  const published = await lines(await f.history.path(s.session.id));
  expect(published[0]).toMatchObject({ type: "nano-dsh-history", version: 1 });
  expect(published.slice(1)).toEqual(s.events);
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
  await entered.promise;
  const exported = f.history.path("a");
  for (let i = 0; i < 20; i++) { a.message(`queued ${i}`); a.end(); }
  b.message("independent"); b.end();
  expect((await lines(await f.history.path("b"))).slice(1)).toEqual(b.events);
  release.resolve();
  const path = await exported;
  await f.history.stop();
  expect((await lines(path)).slice(1)).toEqual(a.events);
  expect(await lines(a.readable)).toHaveLength(21);
  // The persistence seam must not be asked to flush every superseded turn.
  expect(f.flush.mock.calls.filter(([session]) => session === a.session).length).toBeLessThan(5);
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
  expect((await lines(s.readable)).map(row => row.content)).toEqual(["persisted"]);
  expect(JSON.stringify(await lines(await f.history.path(s.session.id)))).toContain("arrived during flush");
});

it("rebuilds after a partial append, a missing copy, and a failed raw publication", async () => {
  const f = await fixture();
  const s = f.create();
  s.message("old"); s.end(); await f.history.stop();
  const original = await readFile(await f.history.path(s.session.id), "utf8");
  const fs = await vi.importActual<typeof import("node:fs/promises")>("node:fs/promises");
  io.fail = async (operation, path, body) => {
    if (operation === "append") {
      await fs.appendFile(path, body!.slice(0, 9));
      throw new Error("partial append");
    }
  };
  s.message("new"); s.end(); await f.history.stop();
  io.fail = async (operation, path) => {
    if (operation === "write" && path === `${s.raw}.tmp`) throw new Error("raw disk failure");
  };
  await expect(f.history.path(s.session.id)).rejects.toThrow("raw disk failure");
  expect(await readFile(s.raw, "utf8")).toBe(original);
  io.fail = undefined;
  expect((await lines(await f.history.path(s.session.id))).slice(1)).toEqual(s.events);
  expect((await lines(s.readable)).map(row => row.content)).toEqual(["old", "new"]);
  await rm(s.readable);
  s.message("after deletion"); s.end(); await f.history.stop();
  expect((await lines(s.readable)).map(row => row.content)).toEqual(["old", "new", "after deletion"]);
});

it("rebuilds cold copies and starts a fresh watermark for a newly live session", async () => {
  const f = await fixture();
  const old = f.create();
  old.message("cold projection"); old.end(); await f.history.stop();
  await writeFile(old.readable, '{"partial":');
  f.sessions.delete(old.session.id);
  f.observeSession.mockResolvedValue({ source: "prepared", header: old.session.header, events: old.events, [Symbol.dispose]() {} });
  await f.history.recoverExports([old.session.id]);
  expect((await lines(old.readable)).map(row => row.content)).toEqual(["cold projection"]);
  const live = f.create();
  live.message("restored lifecycle"); live.end(); await f.history.stop();
  expect((await lines(live.readable)).map(row => row.content)).toEqual(["restored lifecycle"]);
});

it("retains a requested snapshot when a newer turn arrives during a failed publication", async () => {
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
  const stopped = f.history.stop();
  release.resolve();
  await stopped;
  expect((await lines(await exported)).slice(1)).toEqual(s.events);
  expect((await lines(s.readable)).map(row => row.content)).toEqual(["first", "during failure"]);
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
