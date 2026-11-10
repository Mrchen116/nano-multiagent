import { spawn as nodeSpawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { browserError, excerpt, isBrowserError } from './errors.js';

export const DRIVER_VERSION_PREFIX = '0.38.';
export const DEFAULT_TIMEOUT_MS = 20_000;
export const NAVIGATE_TIMEOUT_MS = 30_000;
export const MAX_OUTPUT_BYTES = 32 * 1024 * 1024;

/** Tools this client may dispatch through `cua-driver call`.
 *
 * Everything outside this set has no call entry here (notably run_script,
 * run_steps, page, hotkey, type_text, press_key, bring_to_front, launch_app,
 * download/upload/dialog/clipboard and set_value).
 */
export const DRIVER_CALL_TOOLS = [
  'browser_prepare',
  'get_browser_state',
  'browser_navigate',
  'browser_click',
  'browser_type',
  'browser_pointer',
  'list_windows',
  'end_session',
] as const;
export type DriverCallTool = (typeof DRIVER_CALL_TOOLS)[number];

/** Probe-only commands; they never accept page arguments. */
export const DRIVER_PROBE_COMMANDS = ['--version', 'status', 'permissions status --json'] as const;

export interface DriverProbe {
  version: string;
}

export interface DriverCallOptions {
  timeoutMs?: number;
  requireFields?: readonly string[];
}

export interface BrowserDriverLike {
  probe(): Promise<DriverProbe>;
  call(tool: DriverCallTool, args: Record<string, unknown>, options?: DriverCallOptions): Promise<Record<string, unknown>>;
}

type Spawn = (command: string, args: readonly string[], options: Record<string, unknown>) => ChildProcessWithoutNullStreams;

export interface DriverClientOptions {
  /** `NANO_CUA_DRIVER` override is applied when this is omitted. */
  command?: string;
  env?: NodeJS.ProcessEnv;
  spawn?: Spawn;
  timeoutMs?: number;
  navigateTimeoutMs?: number;
  maxOutputBytes?: number;
}

interface RawRun {
  stdout: string;
  stderr: string;
  code: number;
}

/** Spawn-based client for the pinned `cua-driver` CLI.
 *
 * The client uses an argument array and never a shell, so URLs and typed text
 * cannot enter command parsing. A probe caches the version/daemon/permission
 * result; failures clear the cache so a later call can observe a repaired host.
 */
export class DriverClient implements BrowserDriverLike {
  private readonly command: string;
  private readonly env: NodeJS.ProcessEnv;
  private readonly spawn: Spawn;
  private readonly timeoutMs: number;
  private readonly navigateTimeoutMs: number;
  private readonly maxOutputBytes: number;
  private probed?: Promise<DriverProbe>;

  constructor(options: DriverClientOptions = {}) {
    this.command = options.command ?? options.env?.NANO_CUA_DRIVER ?? process.env.NANO_CUA_DRIVER ?? 'cua-driver';
    this.env = options.env ?? process.env;
    this.spawn = options.spawn ?? (nodeSpawn as unknown as Spawn);
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.navigateTimeoutMs = options.navigateTimeoutMs ?? NAVIGATE_TIMEOUT_MS;
    this.maxOutputBytes = options.maxOutputBytes ?? MAX_OUTPUT_BYTES;
  }

  /** Validate the installed driver once per process and report its version. */
  probe(): Promise<DriverProbe> {
    this.probed ??= this.probeOnce().catch(error => {
      this.probed = undefined;
      throw error;
    });
    return this.probed;
  }

  /** Dispatch one whitelisted driver tool and return its JSON object. */
  async call(tool: DriverCallTool, args: Record<string, unknown>, options: DriverCallOptions = {}): Promise<Record<string, unknown>> {
    if (!(DRIVER_CALL_TOOLS as readonly string[]).includes(tool)) {
      throw browserError('browser_arguments_invalid', `Driver tool "${String(tool)}" has no call entry in this capability.`);
    }
    const run = await this.run(['call', tool, JSON.stringify(args)], tool === 'browser_navigate' ? this.navigateTimeoutMs : options.timeoutMs ?? this.timeoutMs);
    let parsed: unknown;
    try {
      parsed = JSON.parse(run.stdout);
    } catch {
      throw browserError('browser_driver_malformed', `${tool} 返回了无法解析的 JSON：${excerpt(run.stdout) || '<empty>'}`);
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw browserError('browser_driver_malformed', `${tool} 返回的 JSON 不是对象：${excerpt(run.stdout)}`);
    }
    const value = parsed as Record<string, unknown>;
    if (value.status === 'refused' || value.effect === 'refused' || value.refusal) {
      const refusal = value.refusal as { code?: unknown; message?: unknown } | undefined;
      throw browserError('browser_driver_refused', `${tool} 被驱动拒绝：${String(refusal?.code ?? 'refused')} ${String(refusal?.message ?? '')}`.trim(), {
        refusalCode: refusal?.code,
        hint: value.hint,
      });
    }
    for (const field of options.requireFields ?? []) {
      if (!(field in value)) throw browserError('browser_driver_malformed', `${tool} 响应缺少字段 ${field}：${excerpt(run.stdout)}`);
    }
    return value;
  }

  private async probeOnce(): Promise<DriverProbe> {
    const versionRun = await this.run(['--version'], this.timeoutMs);
    const version = /(\d+)\.(\d+)\.(\d+)/.exec(versionRun.stdout)?.[0];
    if (!version) {
      throw browserError('browser_driver_version_unsupported', `无法从 --version 输出识别版本：${excerpt(versionRun.stdout || versionRun.stderr)}`);
    }
    if (!version.startsWith(DRIVER_VERSION_PREFIX)) {
      throw browserError('browser_driver_version_unsupported', `当前 cua-driver 版本为 ${version}，需要 ${DRIVER_VERSION_PREFIX}x。`);
    }
    const status = await this.run(['status'], this.timeoutMs);
    const statusText = `${status.stdout}\n${status.stderr}`;
    if (status.code !== 0 || !/daemon is running/i.test(statusText) || !/permission mode/i.test(statusText)) {
      throw browserError('browser_driver_not_running', `cua-driver status 未确认 daemon 正在运行：${excerpt(statusText)}`);
    }
    const permissions = await this.run(['permissions', 'status', '--json'], this.timeoutMs);
    let parsed: unknown;
    try {
      parsed = JSON.parse(permissions.stdout);
    } catch {
      throw browserError('browser_driver_malformed', `permissions status --json 返回无法解析的 JSON：${excerpt(permissions.stdout) || '<empty>'}`);
    }
    const missing = ['accessibility', 'screen_recording'].filter(name => !permissionGranted(parsed, name));
    if (missing.length) throw browserError('browser_permission_missing', `缺少系统权限：${missing.join(', ')}。`, { missing });
    return { version };
  }

  private run(args: readonly string[], timeoutMs: number): Promise<RawRun> {
    return new Promise((resolve, reject) => {
      let child: ChildProcessWithoutNullStreams;
      try {
        child = this.spawn(this.command, args, {
          shell: false,
          env: this.env,
          stdio: ['ignore', 'pipe', 'pipe'],
          windowsHide: true,
        });
      } catch (error) {
        reject(spawnFailure(error));
        return;
      }
      const stdout: Buffer[] = [];
      const stderr: Buffer[] = [];
      let bytes = 0;
      let settled = false;
      let timedOut = false;
      let timer: ReturnType<typeof setTimeout>;
      const settle = (action: () => void) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        action();
      };
      const collect = (target: Buffer[], chunk: Buffer) => {
        if (settled) return;
        bytes += chunk.length;
        if (bytes > this.maxOutputBytes) {
          child.kill('SIGKILL');
          settle(() => reject(browserError('browser_driver_malformed', `cua-driver 输出超过上限 ${this.maxOutputBytes} 字节，已终止。`)));
          return;
        }
        target.push(chunk);
      };
      child.stdout?.on('data', (chunk: Buffer) => collect(stdout, chunk));
      child.stderr?.on('data', (chunk: Buffer) => collect(stderr, chunk));
      child.once('error', error => settle(() => reject(spawnFailure(error))));
      child.once('close', code => settle(() => {
        if (timedOut) return;
        const output = Buffer.concat(stdout).toString('utf8');
        const errors = Buffer.concat(stderr).toString('utf8');
        if (code !== 0) {
          reject(browserError('browser_driver_malformed', `cua-driver 退出码 ${String(code)}：${excerpt(errors || output)}`, { exitCode: code }));
          return;
        }
        if (!output.trim()) {
          reject(browserError('browser_driver_malformed', `cua-driver ${args.slice(0, 2).join(' ')} 返回空 stdout。`));
          return;
        }
        resolve({ stdout: output, stderr: errors, code });
      }));
      timer = setTimeout(() => {
        timedOut = true;
        child.kill('SIGKILL');
        settle(() => reject(browserError('browser_driver_timeout', `cua-driver ${args.slice(0, 2).join(' ')} 超过 ${timeoutMs}ms 未返回。`)));
      }, timeoutMs);
      timer.unref?.();
    });
  }
}

function spawnFailure(error: unknown): Error {
  if (isBrowserError(error)) return error;
  const code = (error as { code?: string })?.code;
  if (code === 'ENOENT') return browserError('browser_driver_unavailable', `找不到可执行的 cua-driver：${String((error as Error)?.message ?? error)}`);
  return browserError('browser_driver_unavailable', `无法启动 cua-driver：${String((error as Error)?.message ?? error)}`);
}

function permissionGranted(value: unknown, name: string, depth = 0): boolean {
  if (!value || typeof value !== 'object' || depth > 6) return false;
  for (const [key, candidate] of Object.entries(value as Record<string, unknown>)) {
    const normalized = key.replace(/[^a-z]/gi, '').toLowerCase();
    const wanted = name.replace(/_/g, '').toLowerCase();
    if (normalized === wanted) {
      if (typeof candidate === 'boolean') return candidate;
      if (candidate && typeof candidate === 'object') {
        const status = candidate as Record<string, unknown>;
        for (const field of ['granted', 'authorized', 'enabled', 'ok']) if (typeof status[field] === 'boolean') return status[field];
        for (const field of ['status', 'state', 'value']) {
          if (typeof status[field] === 'string') return ['granted', 'authorized', 'ok', 'true', 'allowed'].includes(status[field].toLowerCase());
        }
      }
      return false;
    }
    if (candidate && typeof candidate === 'object' && permissionGranted(candidate, name, depth + 1)) return true;
  }
  return false;
}
