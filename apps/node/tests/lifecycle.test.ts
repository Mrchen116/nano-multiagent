import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";
import { expect, it } from "vitest";
const exec = promisify(execFile);
it("manages one real node, preserves its environment, and refuses a reused PID", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-lifecycle-"));
  const config = join(home, "config.yaml");
  const cli = (...args: string[]) =>
    exec(
      process.execPath,
      [resolve("apps/node/lib/cli.js"), ...args, "--config", config],
      { env: { ...process.env, NANO_OWNER_CONFIG_ROOT: home }, timeout: 70000 },
    );
  let unrelated: ReturnType<typeof spawn> | undefined;
  try {
    await writeFile(
      config,
      JSON.stringify({
        node: { node_id: "lifecycle", user_id: "owner" },
        im_service: { url: "http://127.0.0.1:9", token: "device-test" },
        agents: [],
        gateway: {
          autostart: false,
          environment: { NANO_TEST_ENV: "configured" },
        },
        llm: {
          default_model: "test",
          providers: [
            {
              name: "fixture",
              base_url: "http://127.0.0.1:9",
              models: [{ name: "test" }],
            },
          ],
        },
      }),
    );
    expect((await cli("start")).stdout).toContain("Gateway started");
    let state = JSON.parse(
      await readFile(join(home, ".gateway-state.json"), "utf8"),
    );
    expect(state.ready).toBe(true);
    expect(state.runtime_pid).toBeGreaterThan(0);
    const environment = await exec("/bin/ps", [
      "eww",
      "-p",
      String(state.runtime_pid),
      "-o",
      "command=",
    ]);
    expect(environment.stdout.includes("NANO_TEST_ENV=configured")).toBe(true);
    expect((await cli("status")).stdout).toContain("RUNNING");
    await expect(cli("start")).rejects.toThrow("already running");
    const oldRuntime = state.runtime_pid;
    process.kill(oldRuntime, "SIGKILL");
    await expect.poll(async () => JSON.parse(await readFile(join(home, ".gateway-state.json"), "utf8")).ready, {interval: 10, timeout: 3000}).toBe(false);
    await expect.poll(async () => {
      state = JSON.parse(await readFile(join(home, ".gateway-state.json"), "utf8"));
      return state.ready && state.runtime_pid !== oldRuntime;
    }, {timeout: 15000}).toBe(true);
    expect((await cli("status")).stdout).toContain(String(state.runtime_pid));
    expect((await cli("stop")).stdout).toContain("STOPPED");
    await expect
      .poll(
        () => {
          try {
            process.kill(state.runtime_pid, 0);
            return true;
          } catch {
            return false;
          }
        },
        { timeout: 10000 },
      )
      .toBe(false);
    unrelated = spawn(process.execPath, ["-e", "setInterval(()=>{},1000)"], {
      stdio: "ignore",
    });
    await new Promise((resolve) => unrelated!.once("spawn", resolve));
    await writeFile(
      join(home, ".gateway-state.json"),
      JSON.stringify({
        ...state,
        pid: unrelated.pid,
        process_start: "different birth",
      }),
    );
    await expect(cli("stop")).rejects.toThrow("identity changed");
    expect(() => process.kill(unrelated!.pid!, 0)).not.toThrow();
    expect(
      JSON.parse(await readFile(join(home, ".gateway-state.json"), "utf8")).pid,
    ).toBe(unrelated.pid);
  } finally {
    unrelated?.kill();
    await cli("stop").catch(() => {});
    await rm(home, { recursive: true, force: true });
  }
}, 90000);
