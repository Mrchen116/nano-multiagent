import { expect, it } from "vitest";
import { WorkflowControl, type WorkflowCall } from "../src/workflow/control.js";

function fixture(previous: WorkflowCall[] = []) {
  const starts: {
    prompt: string;
    signal: AbortSignal;
    finish: (value: string) => void;
    disposed: boolean;
  }[] = [];
  const snapshots: WorkflowCall[][] = [];
  const control = new WorkflowControl({
    concurrency: 2,
    maxAgents: 10,
    previous,
    persist: async (calls) => {
      snapshots.push(structuredClone(calls));
    },
    remaining: async () => null,
    start: async (prompt, _options, signal) => {
      let resolve!: (v: { value: string; success: boolean }) => void;
      const result = new Promise<{ value: string; success: boolean }>(
        (r) => (resolve = r),
      );
      const item = {
        prompt,
        signal,
        finish: (value: string) => resolve({ value, success: !signal.aborted }),
        disposed: false,
      };
      starts.push(item);
      signal.addEventListener("abort", () => item.finish("old"), {
        once: true,
      });
      return {
        id: `child-${starts.length}`,
        result,
        dispose: async () => {
          item.disposed = true;
        },
      };
    },
  });
  return { control, starts, snapshots };
}

it("pauses admission, restarts the same logical promise after old cleanup, and stop wakes queued calls", async () => {
  const { control, starts } = fixture();
  const first = control.call("first", {});
  await expect.poll(() => starts.length).toBe(1);
  control.pause();
  const second = control.call("second", {});
  await control.restart(1);
  expect(starts).toHaveLength(1);
  expect(starts[0]!.disposed).toBe(true);
  control.resume();
  await expect.poll(() => starts.length).toBe(3);
  const replacement = starts.findLast((x) => x.prompt === "first")!;
  replacement.finish("replacement");
  expect(await first).toBe("replacement");
  expect(control.calls[0]!.attempts).toHaveLength(2);
  control.stop();
  await expect(second).rejects.toThrow("stopped");
  await control.drain();
  expect(starts.every((x) => x.disposed)).toBe(true);
});

it("persists before release, replays in completion order, and invalidates from the first changed call", async () => {
  const old = fixture();
  const a = old.control.call("A", { label: "old" });
  const b = old.control.call("B", {});
  await expect.poll(() => old.starts.length).toBe(2);
  old.starts[1]!.finish("B1");
  await b;
  old.starts[0]!.finish("A1");
  await a;
  expect(old.snapshots.at(-1)![0]!.value).toBe("A1");
  const replay = fixture(old.control.calls);
  const order: string[] = [];
  await Promise.all([
    replay.control
      .call("A", { label: "new", phase: "new" })
      .then((v) => order.push(String(v))),
    replay.control.call("B", {}).then((v) => order.push(String(v))),
  ]);
  expect(order).toEqual(["B1", "A1"]);
  expect(replay.starts).toHaveLength(0);
  const changed = fixture(old.control.calls);
  const c = changed.control.call("A", {});
  const d = changed.control.call("changed", {});
  expect(await c).toBe("A1");
  await expect.poll(() => changed.starts.length).toBe(1);
  changed.starts[0]!.finish("new");
  expect(await d).toBe("new");
});

it("shares an exhausted budget across queued work and counts restarted attempts without consuming another logical call", async () => {
  let balance = 3;
  let starts = 0;
  const control = new WorkflowControl({
    concurrency: 1,
    maxAgents: 2,
    persist: async () => {},
    remaining: async () => balance,
    start: async () => {
      starts++;
      balance = 0;
      return {
        id: "child",
        result: Promise.resolve({ value: "ok", success: true }),
        dispose: async () => {},
      };
    },
  });
  expect(await control.call("A", {})).toBe("ok");
  await expect(control.call("B", {})).rejects.toThrow("budget");
  expect(starts).toBe(1);
});
