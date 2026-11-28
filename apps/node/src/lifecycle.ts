import { execFile, spawn } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { promisify } from "node:util";
import {
  open,
  readdir,
  readFile,
  rmdir,
  writeFile,
  rename,
  mkdir,
  rm,
  realpath,
  stat,
  unlink,
} from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";
import { createHash, randomUUID } from "node:crypto";
import { setGlobalProxyFromEnv } from "node:http";
import lockfile from "proper-lockfile";
import { windowsHost } from "./windows-platform.js";
import { syncDirectoryIfSupported } from "./platform-io.js";
import { loadNodeRelease } from "./release.js";
import type { NodeRelease } from "@nano/product-contracts";
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
  connected?: boolean;
  entry?: string;
  node_exec?: string;
  release?: NodeRelease;
}
// Cold startup after Windows logon can take over a minute on an ordinary desktop.
export const defaultGatewayStartupSeconds = process.platform === "win32" ? 120 : 60;
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
  await syncDirectoryIfSupported(dirname(path));
}
export async function processBirth(pid: number): Promise<string | undefined> {
  if (process.platform === "win32")
    return await windowsHost("birth", String(pid)) || undefined;
  try {
    const { stdout } = await exec("/bin/ps", [
      "-p",
      String(pid),
      "-o",
      "stat=,lstart=",
    ]);
    const match = stdout.trim().match(/^(\S+)\s+(.+)$/);
    return match && !match[1]!.includes("Z") ? match[2] : undefined;
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
let windowsBootFileTime: Promise<bigint> | undefined;
async function currentWindowsBootFileTime(): Promise<bigint> {
  windowsBootFileTime ??= windowsHost("boot-filetime").then(BigInt).catch(error => {
    windowsBootFileTime = undefined;
    throw error;
  });
  return windowsBootFileTime;
}
async function ownedState(config: string, observed?: GatewayState) {
  const state = observed ?? await gatewayState(config);
  if (!state) return;
  if (state.config_path !== config)
    throw new Error(
      "Gateway state belongs to another config; refusing to signal it",
    );
  // A previous boot cannot own a live PID, even if Windows has reassigned it.
  if (process.platform === "win32" && /^[1-9]\d*$/.test(state.process_start)) {
    if (BigInt(state.process_start) < await currentWindowsBootFileTime()) return;
  }
  const birth = await processBirth(state.pid);
  if (!birth) return;
  if (!state.process_start || birth !== state.process_start)
    throw new Error(
      "Gateway PID identity changed; preserving evidence and refusing to signal it",
    );
  return state;
}

interface ProcessLockOwner {
  pid: number;
  process_start: string;
  acquired_at: number;
}
const ORPHAN_LOCK_WITHOUT_OWNER_MS = 3000;
const EMPTY_GUARD_STALE_MS = 1000;
const ownedOwnerFilesOnExit = new Set<string>();
let exitCleanupRegistered = false;

function ensureExitOwnerCleanup() {
  if (exitCleanupRegistered) return;
  exitCleanupRegistered = true;
  process.on("exit", () => {
    for (const file of ownedOwnerFilesOnExit) {
      try {
        rmSync(file, { force: true });
      } catch {
        // Best-effort sync cleanup matching proper-lockfile's signal-exit rmdirSync.
      }
    }
    ownedOwnerFilesOnExit.clear();
  });
}

const lockOwnerDir = (lockDir: string) => join(dirname(lockDir), ".gateway-owner");
const lockOwnerPath = (lockDir: string) =>
  join(lockOwnerDir(lockDir), `${basename(lockDir)}.json`);
const lockGuardDir = (lockDir: string) =>
  join(lockOwnerDir(lockDir), `${basename(lockDir)}.guard`);

async function isProcessIdentityAlive(
  pid: unknown,
  processStart: unknown,
): Promise<boolean> {
  if (
    typeof pid !== "number" ||
    pid <= 0 ||
    typeof processStart !== "string" ||
    processStart.length === 0
  ) {
    return false;
  }
  if (process.platform === "win32" && /^[1-9]\d*$/.test(processStart)) {
    if (BigInt(processStart) < await currentWindowsBootFileTime()) {
      return false;
    }
  }
  return (await processBirth(pid)) === processStart;
}

async function reapDeadGuardDir(guardDir: string): Promise<void> {
  const gStat = await stat(guardDir).catch(() => undefined);
  if (!gStat) return;
  const entries = await readdir(guardDir).catch(() => []);
  if (entries.length === 0) {
    if (Date.now() - gStat.mtimeMs > EMPTY_GUARD_STALE_MS) {
      await rmdir(guardDir).catch(() => {});
    }
    return;
  }
  for (const name of entries) {
    const markerPath = join(guardDir, name);
    try {
      const raw = await readFile(markerPath, "utf8");
      const parsed = JSON.parse(raw) as Partial<ProcessLockOwner>;
      if (await isProcessIdentityAlive(parsed.pid, parsed.process_start)) {
        return;
      }
      await unlink(markerPath).catch(() => {});
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
        const mStat = await stat(markerPath).catch(() => undefined);
        if (mStat && Date.now() - mStat.mtimeMs > EMPTY_GUARD_STALE_MS) {
          await unlink(markerPath).catch(() => {});
        }
      }
    }
  }
  // Non-recursive `rmdir` succeeds ONLY when zero live markers remain inside `guardDir`.
  await rmdir(guardDir).catch(() => {});
}

async function withLockTransitionGuard<T>(
  lockDir: string,
  selfBirth: string,
  fn: () => Promise<T>,
): Promise<T> {
  const ownerRoot = lockOwnerDir(lockDir);
  const guardDir = lockGuardDir(lockDir);
  await mkdir(ownerRoot, { recursive: true });
  const birthTag = createHash("sha256").update(selfBirth).digest("hex").slice(0, 12);
  const myMarkerName = `owner-${process.pid}-${birthTag}.json`;
  const deadline = Date.now() + 15000;
  for (;;) {
    let createdDir = false;
    try {
      await mkdir(guardDir, { mode: 0o700 });
      createdDir = true;
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== "EEXIST") throw err;
    }
    if (createdDir) {
      const markerPath = join(guardDir, myMarkerName);
      let markerReady = false;
      try {
        const fd = await open(markerPath, "wx", 0o600);
        try {
          await fd.writeFile(
            JSON.stringify({
              pid: process.pid,
              process_start: selfBirth,
              acquired_at: Date.now(),
            }),
          );
        } finally {
          await fd.close();
        }
        markerReady = existsSync(markerPath);
      } catch (err) {
        if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
          await unlink(markerPath).catch(() => {});
          await rmdir(guardDir).catch(() => {});
          throw err;
        }
      }
      if (markerReady) {
        try {
          return await fn();
        } finally {
          await unlink(markerPath).catch(() => {});
          await rmdir(guardDir).catch(() => {});
        }
      }
    } else {
      await reapDeadGuardDir(guardDir);
      if (Date.now() >= deadline) {
        throw new Error(`Timed out waiting for lock transition guard ${guardDir}`);
      }
      await delay(25);
    }
  }
}

async function reapDeadProcessLockUnlocked(lockDir: string): Promise<boolean> {
  const ownerPath = lockOwnerPath(lockDir);
  let dirStat;
  try {
    dirStat = await stat(lockDir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      // Clean up any leftover sidecar left behind when `signal-exit` removed `lockDir` on SIGINT/SIGTERM.
      await rm(ownerPath, { force: true }).catch(() => {});
      return false;
    }
    throw error;
  }
  try {
    const raw = await readFile(ownerPath, "utf8");
    const parsed = JSON.parse(raw) as Partial<ProcessLockOwner>;
    if (await isProcessIdentityAlive(parsed.pid, parsed.process_start)) {
      return false;
    }
    await rm(ownerPath, { force: true }).catch(() => {});
    const staleDir = `${lockDir}.stale-${randomUUID()}`;
    await rename(lockDir, staleDir).catch(() => {});
    await rm(staleDir, { recursive: true, force: true }).catch(() => {});
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      if (Date.now() - dirStat.mtimeMs > ORPHAN_LOCK_WITHOUT_OWNER_MS) {
        await rm(ownerPath, { force: true }).catch(() => {});
        const staleDir = `${lockDir}.stale-${randomUUID()}`;
        await rename(lockDir, staleDir).catch(() => {});
        await rm(staleDir, { recursive: true, force: true }).catch(() => {});
        return true;
      }
      return false;
    }
  }
  if (Date.now() - dirStat.mtimeMs <= ORPHAN_LOCK_WITHOUT_OWNER_MS) return false;
  const staleDir = `${lockDir}.stale-${randomUUID()}`;
  await rename(lockDir, staleDir).catch(() => {});
  await rm(staleDir, { recursive: true, force: true }).catch(() => {});
  return true;
}

/** Reap a proper-lockfile directory immediately under a transition guard when its owner PID/birth is dead,
 * or when a legacy/interrupted lock directory has no owner metadata and no heartbeat.
 * Never mutates files inside `lockDir` so `proper-lockfile` mtime tracking stays intact.
 */
export async function reapDeadProcessLock(lockDir: string): Promise<boolean> {
  const selfBirth = await processBirth(process.pid);
  if (!selfBirth) return false;
  return withLockTransitionGuard(lockDir, selfBirth, () =>
    reapDeadProcessLockUnlocked(lockDir),
  );
}

async function acquireProcessLock(
  targetPath: string,
  lockDir: string,
  staleMs: number,
  waitTimeoutMs: number,
): Promise<{ process_start: string; release: () => Promise<void> }> {
  const selfBirth = await processBirth(process.pid);
  if (!selfBirth) {
    throw new Error("Cannot establish Gateway process identity");
  }
  ensureExitOwnerCleanup();
  await mkdir(dirname(lockDir), { recursive: true });
  const ownerPath = lockOwnerPath(lockDir);
  const deadline = Date.now() + waitTimeoutMs;
  for (;;) {
    const acquired = await withLockTransitionGuard(
      lockDir,
      selfBirth,
      async (): Promise<(() => Promise<void>) | undefined> => {
        await reapDeadProcessLockUnlocked(lockDir);
        try {
          const unlock = await lockfile.lock(targetPath, {
            realpath: false,
            lockfilePath: lockDir,
            stale: staleMs,
            update: 1000,
            retries: 0,
          });
          const ownerPayload: ProcessLockOwner = {
            pid: process.pid,
            process_start: selfBirth,
            acquired_at: Date.now(),
          };
          try {
            await atomicPrivate(ownerPath, ownerPayload);
            ownedOwnerFilesOnExit.add(ownerPath);
          } catch (writeError) {
            await rm(ownerPath, { force: true }).catch(() => {});
            await unlock().catch(() => {});
            throw writeError;
          }
          return unlock;
        } catch (error) {
          if ((error as { code?: string }).code === "ELOCKED") {
            return undefined;
          }
          throw error;
        }
      },
    );
    if (acquired) {
      return {
        process_start: selfBirth,
        async release() {
          await withLockTransitionGuard(lockDir, selfBirth, async () => {
            ownedOwnerFilesOnExit.delete(ownerPath);
            await rm(ownerPath, { force: true }).catch(() => {});
            await acquired().catch(() => {});
          }).catch(async () => {
            ownedOwnerFilesOnExit.delete(ownerPath);
            await acquired().catch(() => {});
          });
        },
      };
    }
    if (Date.now() >= deadline) {
      throw Object.assign(new Error("Lock file is already being held"), {
        code: "ELOCKED",
        file: targetPath,
      });
    }
    await delay(150);
  }
}
export function gatewayLabel(config: string) {
  return (
    "io.github.mrchen116.nano-multiagent.gateway." +
    createHash("sha256").update(config).digest("hex").slice(0, 16)
  );
}
export function gatewayPlist(config: string) {
  if (process.env.NANO_TEST_AUTOSTART_DIR) {
    return join(
      resolve(process.env.NANO_TEST_AUTOSTART_DIR),
      gatewayLabel(config) + ".plist",
    );
  }
  return join(
    homedir(),
    "Library/LaunchAgents",
    gatewayLabel(config) + ".plist",
  );
}
export function isDesktopManagedConfig(config: string): boolean {
  return (
    existsSync(join(dirname(config), ".desktop-active.json")) ||
    process.env.CREWDEN_DESKTOP_MANAGED === "1"
  );
}
const target = (config: string) =>
  `gui/${process.getuid!()}/${gatewayLabel(config)}`;
async function loaded(config: string) {
  if (process.env.NANO_TEST_AUTOSTART_DIR) return false;
  try {
    await exec("/bin/launchctl", ["print", target(config)]);
    return true;
  } catch {
    return false;
  }
}
async function unload(config: string) {
  if (process.platform !== "darwin" || process.env.NANO_TEST_AUTOSTART_DIR || !(await loaded(config))) return;
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
/** Keep Chrome pairing local to this configuration, physical node and bound owner. */
export function browserPairingFile(configPath: string, node: NodeConfigurationFile['node']) {
  const identity = createHash('sha256').update(JSON.stringify([node.node_id, node.user_id])).digest('hex');
  return join(dirname(configPath), '.nano-browser', identity + '.json');
}

/** Runtime lease prevents duplicate foreground, background and launchd consumers. */
export async function claimGateway(config: string) {
  const { process_start, release } = await acquireProcessLock(
    config,
    join(dirname(config), ".gateway-runtime.lock"),
    15000,
    15000,
  );
  const state: GatewayState = {
    pid: process.pid,
    config_path: config,
    process_start,
    ready: false,
    connected: false,
    entry,
    node_exec: process.execPath,
    release: await loadNodeRelease(),
  };
  await atomicPrivate(statePath(config), state);
  return {
    async ready(runtimePid: number) {
      state.ready = true;
      state.runtime_pid = runtimePid;
      await atomicPrivate(statePath(config), state);
    },
    async connected(connected: boolean) {
      state.connected = connected;
      await atomicPrivate(statePath(config), state);
    },
    async unavailable() {
      state.ready = false;
      delete state.runtime_pid;
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
/** Apply configured environment and refresh clients created before config loading.
 *
 * Args:
 *   config: Local node configuration owning the stable service environment.
 */
export function applyGatewayEnvironment(config: NodeConfigurationFile, configPath?: string) {
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
  if (configPath) process.env.NANO_BROWSER_PAIRING_FILE = browserPairingFile(configPath, config.node);
  // The official bundle is also available to a launchd Gateway without shell dotfiles.
  const cuaDriverBin = "/Applications/CuaDriver.app/Contents/MacOS";
  if (process.platform === "darwin" && existsSync(join(cuaDriverBin, "cua-driver"))) {
    const paths = (process.env.PATH ?? "").split(":").filter(Boolean);
    process.env.PATH = [cuaDriverBin, ...paths.filter(path => path !== cuaDriverBin)].join(":");
  }
  // launchd starts Node before this config is read; assigning the flag alone
  // leaves the existing HTTP/HTTPS agents and fetch dispatcher on their old route.
  if (process.env.NODE_USE_ENV_PROXY === "1") setGlobalProxyFromEnv();
}
/** Serializes public lifecycle commands and rechecks process birth before every signal. */
export async function manageGateway(
  configPath: string,
  config: NodeConfigurationFile,
  action: "start" | "stop" | "restart" | "status" | "autostart-on" | "autostart-off" | "autostart-status",
  args: string[] = [],
) {
  const path = await realpath(configPath);
  const timing = config.gateway ?? {};
  const startup = timing.startup_timeout_seconds ?? defaultGatewayStartupSeconds,
    grace = timing.shutdown_grace_seconds ?? 15,
    poll = timing.poll_interval_seconds ?? 0.1;
  if (
    [startup, grace, poll].some(
      (value) => !Number.isFinite(value) || value <= 0,
    )
  )
    throw new Error("Gateway lifecycle timing must be positive");
  const { release } = await acquireProcessLock(
    path,
    join(dirname(path), ".gateway-lifecycle.lock"),
    120000,
    Math.max(30000, Math.ceil((startup + grace + 10) * 1000)),
  );
  try {
    if (action === "autostart-on" || action === "autostart-off" || action === "autostart-status") {
      if (process.platform === "win32") {
        if (process.env.NANO_TEST_AUTOSTART_DIR) {
          const marker = join(resolve(process.env.NANO_TEST_AUTOSTART_DIR), gatewayLabel(path) + ".win-autostart");
          if (action === "autostart-on") await atomicPrivate(marker, "enabled");
          else if (action === "autostart-off") await rm(marker, { force: true });
          return { text: existsSync(marker) ? "enabled" : "disabled", success: true };
        }
        const text = await windowsHost(action, path, String(Math.ceil(grace * 1000)), String(config.gateway?.autostart !== false));
        return { text, success: true };
      }
      if (process.platform === "darwin" || process.env.NANO_TEST_AUTOSTART_DIR) {
        const desktopManaged = isDesktopManagedConfig(path);
        const plist = gatewayPlist(path);
        if (action === "autostart-status") {
          const enabled = desktopManaged ? config.gateway?.autostart !== false : existsSync(plist);
          return { text: enabled ? "enabled" : "disabled", success: true };
        }
        if (action === "autostart-on") {
          if (desktopManaged) {
            await rm(plist, { force: true });
          } else {
            await atomicPrivate(plist, launchDefinition(path, grace));
          }
          return { text: "enabled", success: true };
        }
        if (!desktopManaged && !(await ownedState(path))) {
          await unload(path);
        }
        await rm(plist, { force: true });
        return { text: "disabled", success: true };
      }
      throw new Error("Login autostart requires macOS or Windows");
    }
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
      const state = await ownedState(path);
      if (process.platform === "win32") {
        await windowsHost("stop", path, String(state?.pid ?? 0), state?.process_start ?? "");
        await rm(statePath(path), { force: true });
        return;
      }
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
    const logStartSize = await stat(log).then(
      (s) => s.size,
      () => 0,
    );
    await rm(statePath(path), { force: true });
    const extractLogFailure = async () => {
      try {
        const raw = await readFile(log, "utf8");
        const recent = raw.slice(Math.min(logStartSize, raw.length)).trim();
        if (!recent) return undefined;
        const lines = recent
          .split(/\r?\n/)
          .map((l) => l.trim())
          .filter(Boolean);
        const preferred = lines.find((l) =>
          /^(Error|[A-Za-z]+Error|Exception|Unhandled)/i.test(l),
        );
        return (preferred ?? lines[0])?.slice(0, 240);
      } catch {
        return undefined;
      }
    };
    const waitReady = async (hasExited?: () => boolean) => {
      const deadline = Date.now() + startup * 1000;
      const runtimeLockPath = join(dirname(path), ".gateway-runtime.lock");
      while (Date.now() < deadline) {
        const state = await gatewayState(path);
        if (state?.ready && await ownedState(path, state)) return state;
        if (hasExited?.()) {
          await delay(50);
          const finalState = await gatewayState(path);
          if (finalState?.ready && await ownedState(path, finalState)) return finalState;
          const detail = await extractLogFailure();
          throw new Error(
            `Gateway exited before becoming ready${detail ? `: ${detail}` : ""}; inspect ${log}`,
          );
        }
        if (!hasExited) {
          const currentSize = await stat(log).then(
            (s) => s.size,
            () => 0,
          );
          if (currentSize > logStartSize && !(await ownedState(path))) {
            const locked = await lockfile
              .check(path, { realpath: false, lockfilePath: runtimeLockPath })
              .catch(() => false);
            if (!locked) {
              await delay(250);
              const stillUnlocked = !(await lockfile
                .check(path, { realpath: false, lockfilePath: runtimeLockPath })
                .catch(() => false));
              if (stillUnlocked && !(await ownedState(path))) {
                const detail = await extractLogFailure();
                if (detail && /(Error|Exception|Invalid|Cannot find|ERR_)/i.test(detail)) {
                  throw new Error(
                    `Gateway exited before becoming ready: ${detail}; inspect ${log}`,
                  );
                }
              }
            }
          }
        }
        await delay(poll * 1000);
      }
      const detail = await extractLogFailure();
      throw new Error(
        `Gateway startup timed out${detail ? `: ${detail}` : ""}; inspect ${log}`,
      );
    };
    const background = async () => {
      let childExited = false;
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
        child.once("exit", () => {
          childExited = true;
        });
        await new Promise<void>((resolve, reject) => {
          child.once("spawn", resolve);
          child.once("error", reject);
        });
        child.unref();
      } finally {
        await fd.close();
      }
      return waitReady(() => childExited);
    };
    let autostart = "disabled";
    let failure: string | undefined;
    let state: GatewayState;
    if (process.platform === "win32") {
      const enabled = await windowsHost("start", path, String(Math.ceil(grace * 1000)), String(config.gateway?.autostart !== false), ...args);
      state = await waitReady();
      const active = join(dirname(path), ".windows-active.json");
      if (state.release?.kind === "managed" && !isDesktopManagedConfig(path) && !existsSync(active) && !existsSync(join(dirname(path), ".windows-switch.json")))
        await atomicPrivate(active, {sha256: state.release.sha256});
      autostart = enabled === "enabled" ? "enabled (Windows login and crash recovery)" : "disabled";
    } else if (process.platform === "darwin" && config.gateway?.autostart !== false && !isDesktopManagedConfig(path)) {
      try {
        await unload(path);
        await atomicPrivate(gatewayPlist(path), launchDefinition(path, grace));
        if (process.env.NANO_TEST_AUTOSTART_DIR) {
          state = await background();
        } else {
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
        }
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
      if (isDesktopManagedConfig(path) && config.gateway?.autostart !== false) {
        autostart = "enabled (Crewden Desktop login item)";
      }
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
