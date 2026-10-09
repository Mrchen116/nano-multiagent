import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";
import {
  open,
  readFile,
  writeFile,
  rename,
  mkdir,
  rm,
  realpath,
} from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";
import { createHash, randomUUID } from "node:crypto";
import lockfile from "proper-lockfile";
import type { NodeConfigurationFile } from "./configuration.js";
const exec = promisify(execFile);
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const entry = fileURLToPath(new URL("./cli.js", import.meta.url));
const root = resolve(dirname(entry), "../../..");
export interface GatewayState {
  pid: number;
  config_path: string;
  process_start: string;
  ready: boolean;
  runtime_pid?: number;
}
export interface GatewayTiming {
  startup_timeout_seconds?: number;
  shutdown_grace_seconds?: number;
  poll_interval_seconds?: number;
}
const statePath = (config: string) =>
  join(dirname(config), ".gateway-state.json");
export async function atomicPrivate(path: string, value: unknown) {
  await mkdir(dirname(path), { recursive: true });
  const temporary = path + "." + randomUUID() + ".tmp";
  const file = await open(temporary, "wx", 0o600);
  try {
    await file.writeFile(
      typeof value === "string" ? value : JSON.stringify(value),
    );
    await file.sync();
  } finally {
    await file.close();
  }
  await rename(temporary, path);
  const directory = await open(dirname(path), "r");
  try {
    await directory.sync();
  } finally {
    await directory.close();
  }
}
export async function processBirth(pid: number): Promise<string | undefined> {
  try {
    const { stdout } = await exec("/bin/ps", [
      "-p",
      String(pid),
      "-o",
      "lstart=",
    ]);
    return stdout.trim() || undefined;
  } catch {
    return undefined;
  }
}
export async function gatewayState(
  config: string,
): Promise<GatewayState | undefined> {
  try {
    return JSON.parse(
      await readFile(statePath(config), "utf8"),
    ) as GatewayState;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
    throw error;
  }
}
async function ownedState(config: string) {
  const state = await gatewayState(config);
  if (!state) return;
  if (state.config_path !== config)
    throw new Error(
      "Gateway state belongs to another config; refusing to signal it",
    );
  const birth = await processBirth(state.pid);
  if (!birth) return;
  if (!state.process_start || birth !== state.process_start)
    throw new Error(
      "Gateway PID identity changed; preserving evidence and refusing to signal it",
    );
  return state;
}
export function gatewayLabel(config: string) {
  return (
    "io.github.mrchen116.nano-multiagent.gateway." +
    createHash("sha256").update(config).digest("hex").slice(0, 16)
  );
}
export function gatewayPlist(config: string) {
  return join(
    homedir(),
    "Library/LaunchAgents",
    gatewayLabel(config) + ".plist",
  );
}
const target = (config: string) =>
  `gui/${process.getuid!()}/${gatewayLabel(config)}`;
async function loaded(config: string) {
  try {
    await exec("/bin/launchctl", ["print", target(config)]);
    return true;
  } catch {
    return false;
  }
}
async function unload(config: string) {
  if (process.platform !== "darwin" || !(await loaded(config))) return;
  await exec("/bin/launchctl", ["bootout", target(config)]);
  for (let i = 0; i < 50; i++) {
    if (!(await loaded(config))) return;
    await delay(100);
  }
  throw new Error("LaunchAgent remained loaded after bootout");
}
const xml = (text: string) =>
  text.replace(
    /[<>&"']/g,
    (char) =>
      ({
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
      })[char]!,
  );
export function launchDefinition(
  config: string,
  grace: number,
  args: string[] = [],
) {
  const argv = [
    process.execPath,
    entry,
    "--foreground",
    "--config",
    config,
    ...args,
  ];
  return `<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>Label</key><string>${xml(gatewayLabel(config))}</string><key>ProgramArguments</key><array>${argv.map((arg) => `<string>${xml(arg)}</string>`).join("")}</array><key>WorkingDirectory</key><string>${xml(root)}</string><key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict><key>StandardOutPath</key><string>${xml(join(dirname(config), "gateway.log"))}</string><key>StandardErrorPath</key><string>${xml(join(dirname(config), "gateway.log"))}</string><key>RunAtLoad</key><true/><key>KeepAlive</key><true/><key>ExitTimeOut</key><integer>${Math.ceil(grace)}</integer></dict></plist>`;
}
/** Runtime lease prevents duplicate foreground, background and launchd consumers. */
export async function claimGateway(config: string) {
  const release = await lockfile.lock(config, {
    realpath: false,
    lockfilePath: join(dirname(config), ".gateway-runtime.lock"),
    stale: 10000,
    update: 1000,
  });
  const process_start = await processBirth(process.pid);
  if (!process_start) {
    await release();
    throw new Error("Cannot establish Gateway process identity");
  }
  const state: GatewayState = {
    pid: process.pid,
    config_path: config,
    process_start,
    ready: false,
  };
  await atomicPrivate(statePath(config), state);
  return {
    async ready(runtimePid: number) {
      state.ready = true;
      state.runtime_pid = runtimePid;
      await atomicPrivate(statePath(config), state);
    },
    async close() {
      const current = await gatewayState(config);
      if (
        current?.pid === process.pid &&
        current.process_start === process_start
      )
        await rm(statePath(config), { force: true });
      await release();
    },
  };
}
export function applyGatewayEnvironment(config: NodeConfigurationFile) {
  const environment = config.gateway?.environment ?? {};
  for (const [key, value] of Object.entries(environment)) {
    if (
      !key ||
      key.includes("=") ||
      key.includes("\0") ||
      typeof value !== "string" ||
      value.includes("\0")
    )
      throw new Error(
        "gateway.environment requires valid string environment values",
      );
    process.env[key] = value;
  }
}
/** Serializes public lifecycle commands and rechecks process birth before every signal. */
export async function manageGateway(
  configPath: string,
  config: NodeConfigurationFile,
  action: "start" | "stop" | "restart" | "status",
  args: string[] = [],
) {
  const path = await realpath(configPath);
  const timing = config.gateway ?? {};
  const startup = timing.startup_timeout_seconds ?? 60,
    grace = timing.shutdown_grace_seconds ?? 15,
    poll = timing.poll_interval_seconds ?? 0.1;
  if (
    [startup, grace, poll].some(
      (value) => !Number.isFinite(value) || value <= 0,
    )
  )
    throw new Error("Gateway lifecycle timing must be positive");
  const release = await lockfile.lock(path, {
    realpath: false,
    lockfilePath: join(dirname(path), ".gateway-lifecycle.lock"),
    stale: 120000,
    update: 1000,
    retries: { retries: 120, factor: 1, minTimeout: 250, maxTimeout: 250 },
  });
  try {
    if (action === "status") {
      const state = await ownedState(path);
      return {
        text: state
          ? `RUNNING pid=${state.pid} ready=${state.ready} DSH=${state.runtime_pid ?? "starting"}`
          : "NOT RUNNING",
        success: true,
        state,
      };
    }
    const stop = async () => {
      await unload(path);
      let state = await ownedState(path);
      if (!state) {
        await rm(statePath(path), { force: true });
        return;
      }
      if ((await processBirth(state.pid)) !== state.process_start)
        throw new Error("Gateway PID identity changed before stop");
      process.kill(state.pid, "SIGTERM");
      const until = Date.now() + grace * 1000;
      while (
        Date.now() < until &&
        (await processBirth(state.pid)) === state.process_start
      )
        await delay(poll * 1000);
      if ((await processBirth(state.pid)) === state.process_start)
        process.kill(state.pid, "SIGKILL");
      for (
        let i = 0;
        i < 50 && (await processBirth(state.pid)) === state.process_start;
        i++
      )
        await delay(100);
      if ((await processBirth(state.pid)) === state.process_start)
        throw new Error("Gateway process did not stop");
      await rm(statePath(path), { force: true });
    };
    if (action === "stop" || action === "restart") await stop();
    if (action === "stop") return { text: "STOPPED", success: true };
    if (await ownedState(path)) throw new Error("Gateway is already running");
    const log = join(dirname(path), "gateway.log");
    await rm(statePath(path), { force: true });
    const waitReady = async () => {
      const deadline = Date.now() + startup * 1000;
      while (Date.now() < deadline) {
        const state = await ownedState(path);
        if (state?.ready) return state;
        await delay(poll * 1000);
      }
      throw new Error(`Gateway startup timed out; inspect ${log}`);
    };
    const background = async () => {
      const fd = await open(log, "a", 0o600);
      try {
        const child = spawn(
          process.execPath,
          [entry, "--foreground", "--config", path, ...args],
          {
            cwd: root,
            env: process.env,
            detached: true,
            stdio: ["ignore", fd.fd, fd.fd],
          },
        );
        await new Promise<void>((resolve, reject) => {
          child.once("spawn", resolve);
          child.once("error", reject);
        });
        child.unref();
      } finally {
        await fd.close();
      }
      return waitReady();
    };
    let autostart = "disabled";
    let failure: string | undefined;
    let state: GatewayState;
    if (process.platform === "darwin" && config.gateway?.autostart !== false) {
      try {
        await unload(path);
        await atomicPrivate(gatewayPlist(path), launchDefinition(path, grace));
        const temporary = join(
          dirname(path),
          ".gateway-launch-" + randomUUID() + ".plist",
        );
        try {
          await atomicPrivate(temporary, launchDefinition(path, grace, args));
          await exec("/bin/launchctl", [
            "bootstrap",
            `gui/${process.getuid!()}`,
            temporary,
          ]);
        } finally {
          await rm(temporary, { force: true });
        }
        state = await waitReady();
        autostart = "enabled (macOS login and crash recovery)";
      } catch (error) {
        failure = String(error);
        await stop();
        state = await background();
        autostart = "failed (running without login recovery)";
      }
    } else {
      if (process.platform === "darwin") {
        await unload(path);
        await rm(gatewayPlist(path), { force: true });
      }
      state = await background();
    }
    return {
      text: `Gateway started (pid=${state.pid})\nAutostart: ${autostart}\nIM service: ${config.im_service.url}\nLog: ${log}${failure ? "\n" + failure : ""}`,
      success: !failure,
      state,
    };
  } finally {
    await release();
  }
}
