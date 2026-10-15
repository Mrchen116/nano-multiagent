import { encodeTrajectoryValue } from "@nano/product-contracts";
import { MessageChannel } from "node:worker_threads";
import { afterEach, describe, expect, it } from "vitest";
import { createReadonlyTransport } from "../src/transport.js";

const dispose: (() => void)[] = [];
afterEach(() => { for (const close of dispose.splice(0)) close(); });

function channel() {
  const { port1, port2 } = new MessageChannel();
  const messages: Record<string, unknown>[] = [];
  const waiting: ((message: Record<string, unknown>) => void)[] = [];
  port2.on("message", (message) => {
    messages.push(message);
    waiting.shift()?.(message);
  });
  const generations: string[] = [];
  const transport = createReadonlyTransport(port1 as unknown as MessagePort, {
    onGenerationChanged: () => { generations.push("reconnect"); },
  });
  dispose.push(() => { transport.dispose(); port1.close(); port2.close(); });
  return {
    transport, messages, generations,
    send: (value: unknown) => port2.postMessage(value),
    nextMessage: () => new Promise<Record<string, unknown>>(resolve => { waiting.push(resolve); }),
    respond: (request: Record<string, unknown>, value: unknown) => {
      port2.postMessage({ type: "result", requestId: request.requestId, value });
    },
    fail: (request: Record<string, unknown>, code: string) => {
      port2.postMessage({ type: "error", requestId: request.requestId, code, message: code });
    },
  };
}

const payload = { args: { request: { address: { kind: "session", sessionId: "selected" } } } };

describe("read-only native viewer transport", () => {
  it("rejects mutations and unknown channels before they can reach the parent", async () => {
    const c = channel();
    for (const endpoint of ["session/prompt", "session/cancel", "session/create", "session/rename", "commands/execute", "settings/set", "unknown/read"]) {
      await expect(c.transport.rpc.call("/api", endpoint, payload)).rejects.toThrow(/read.only/i);
    }
    await expect(c.transport.rpc.call("/rpc", "session/page", payload)).rejects.toThrow(/read.only/i);
    expect(c.messages).toEqual([]);
    const sent = c.nextMessage();
    const result = c.transport.rpc.call("/api", "session/page", payload);
    const request = await sent;
    expect(request).toMatchObject({ type: "call", method: "session/page", params: payload });
    c.respond(request, { ok: true, value: { records: [], hasMore: false } });
    await expect(result).resolves.toEqual({ ok: true, value: { records: [], hasMore: false } });
  });

  it("pulls one bounded batch only after native iteration consumes the previous batch", async () => {
    const c = channel();
    const stream = c.transport.rpc.open!("/api", "session/follow", payload, new AbortController().signal)[Symbol.asyncIterator]();
    expect(c.messages).toEqual([]);
    const opened = c.nextMessage();
    const first = stream.next();
    const request = await opened;
    expect(request).toMatchObject({ type: "open", method: "session/follow", params: payload });
    const pulled = c.nextMessage();
    c.respond(request, { streamId: "s1" });
    const pull = await pulled;
    expect(pull).toMatchObject({ type: "next", streamId: "s1" });
    c.respond(pull, { frames: [{ n: 1 }, { n: 2 }], done: false });
    await expect(first).resolves.toEqual({ value: { n: 1 }, done: false });
    await expect(stream.next()).resolves.toEqual({ value: { n: 2 }, done: false });
    expect(c.messages.filter(m => m.type === "next")).toHaveLength(1);
    const nextPull = c.nextMessage();
    const last = stream.next();
    const finalRequest = await nextPull;
    c.respond(finalRequest, { frames: [], done: true });
    await expect(last).resolves.toMatchObject({ done: true });
  });

  it("reassembles multi-batch native snapshots and large unary pages before publishing them", async () => {
    const c = channel();
    const opening = { type: "snapshot", records: [{ text: '历史😀"\\'.repeat(160_000) }] };
    const parts = [...encodeTrajectoryValue(opening)];
    expect(parts.length).toBeGreaterThan(2);
    const stream = c.transport.rpc.open!("/api", "session/follow", payload, new AbortController().signal)[Symbol.asyncIterator]();
    const opened = c.nextMessage(), first = stream.next();
    const open = await opened;
    let pulled = c.nextMessage();
    c.respond(open, { streamId: "large" });
    let published = false;
    void first.then(() => { published = true; });
    for (let i = 0; i < parts.length; i++) {
      const request = await pulled;
      if (i + 1 < parts.length) pulled = c.nextMessage();
      expect(published).toBe(false);
      c.respond(request, { frames: [parts[i]], done: i + 1 === parts.length });
    }
    await expect(first).resolves.toEqual({ value: opening, done: false });
    const released = c.nextMessage();
    await expect(stream.next()).resolves.toMatchObject({ done: true });
    expect(await released).toMatchObject({ type: "abort", streamId: "large" });

    const sent = c.nextMessage();
    const page = c.transport.rpc.call("/api", "session/page", payload);
    const request = await sent;
    const response = { type: "result", requestId: request.requestId, value: { ok: true, value: opening } };
    for (const part of encodeTrajectoryValue(response)) c.send(part);
    await expect(page).resolves.toEqual(response.value);
  });

  it("aborts a pending read and releases its stream without invoking Agent cancellation", async () => {
    const c = channel();
    const abort = new AbortController();
    const stream = c.transport.rpc.open!("/api", "session/control", { args: {} }, abort.signal)[Symbol.asyncIterator]();
    const opened = c.nextMessage();
    const read = stream.next();
    const rejected = expect(read).rejects.toThrow();
    const request = await opened;
    const pulled = c.nextMessage();
    c.respond(request, { streamId: "s1" });
    await pulled;
    const canceled = c.nextMessage();
    abort.abort(new Error("viewer left"));
    expect(await canceled).toMatchObject({ type: "abort", streamId: "s1" });
    await rejected;
    expect(c.messages.some(m => m.method === "session/cancel")).toBe(false);
  });

  it("keeps readiness local and closes its hold when the native generation ends", async () => {
    const c = channel();
    const abort = new AbortController();
    const events = c.transport.rpc.open!("/api", "$events", { args: {} }, abort.signal)[Symbol.asyncIterator]();
    expect((await events.next()).value).toMatchObject({ type: "ready", host: { home: "" } });
    expect(c.messages).toEqual([]);
    const waiting = events.next();
    abort.abort();
    await expect(waiting).resolves.toMatchObject({ done: true });
  });

  it("requests a new native generation on generation_changed instead of reopening within the stream", async () => {
    const c = channel();
    const sent = c.nextMessage();
    const result = c.transport.rpc.call("/api", "session/projections", { args: { request: { sessionId: "selected" } } });
    const failed = expect(result).rejects.toThrow("generation_changed");
    c.fail(await sent, "generation_changed");
    await failed;
    expect(c.generations).toEqual(["reconnect"]);
    expect(c.messages).toHaveLength(1);
  });
});
