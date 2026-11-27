import { execFile, spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { access, mkdir, readFile, readdir, readlink, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { createInterface } from 'node:readline/promises';
import { Writable } from 'node:stream';
import { promisify } from 'node:util';
import type {
  DesktopBrowserActionResponse,
  DesktopBrowserPairingState,
  DesktopBrowserProfileItem,
  DesktopBrowserStatus,
} from '@nano/product-contracts/desktop-local';
import { atomicPrivate } from './lifecycle.js';

const exec = promisify(execFile);

export const PLAYWRIGHT_EXTENSION_ID = 'mmlmfjhmonkocbjadbfplnigmagldckm';
export const PLAYWRIGHT_EXTENSION_STORE_URL =
  'https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm';
export const PLAYWRIGHT_EXTENSION_TOKEN_URL =
  'chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/status.html';

const PROFILE_PATTERN = /^(Default|Profile [0-9]+)$/;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{20,256}$/;

export interface BrowserPairingDeps {
  platform?: NodeJS.Platform;
  chromeExecutable?: string | null;
  userDataDir?: string | null;
  chromeRunning?: { running: boolean; versionOk: boolean };
  openChromeUrl?: (executable: string, profile: string, url: string) => void | Promise<void>;
  interactivePrompt?: () => Promise<string>;
  stderrWrite?: (chunk: string) => void;
  pollIntervalMs?: number;
}

/** Validate Chrome profile directory names accepted for daily browser pairing. */
export function isValidChromeProfileName(profile: string): boolean {
  return PROFILE_PATTERN.test(profile);
}

/** Extract and validate a Playwright Extension token from raw token text or `PLAYWRIGHT_MCP_EXTENSION_TOKEN=...` lines. */
export function normalizeExtensionToken(raw: string): string | null {
  let text = raw.trim();
  if (!text || text.length > 512) return null;
  text = text.replace(/^export\s+/, '').trim();
  if (text.startsWith('PLAYWRIGHT_MCP_EXTENSION_TOKEN=')) {
    text = text.slice('PLAYWRIGHT_MCP_EXTENSION_TOKEN='.length).trim();
  }
  if (
    (text.startsWith('"') && text.endsWith('"') && text.length >= 2) ||
    (text.startsWith("'") && text.endsWith("'") && text.length >= 2)
  ) {
    text = text.slice(1, -1).trim();
  }
  return TOKEN_PATTERN.test(text) ? text : null;
}

function versionAtLeast(version: string, min: readonly number[]): boolean {
  if (!/^\d+(?:\.\d+)+$/.test(version)) return false;
  const nums = version.split('.').map(Number);
  for (const [index, wanted] of min.entries()) {
    const actual = nums[index] ?? 0;
    if (actual !== wanted) return actual > wanted;
  }
  return true;
}

async function pathExists(target: string): Promise<boolean> {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

async function findChromeExecutable(platform: NodeJS.Platform): Promise<string | null> {
  const candidates =
    platform === 'darwin'
      ? [
          '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
          join(homedir(), 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
        ]
      : platform === 'win32'
        ? [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA]
            .filter(Boolean)
            .map(root => join(root!, 'Google/Chrome/Application/chrome.exe'))
        : [];
  for (const candidate of candidates) {
    try {
      await access(candidate, platform === 'win32' ? 0 : 1);
      return candidate;
    } catch {
      // Inspect next standard Chrome path.
    }
  }
  return null;
}

function defaultChromeUserDataDir(platform: NodeJS.Platform): string | null {
  if (platform === 'darwin') {
    return join(homedir(), 'Library/Application Support/Google/Chrome');
  }
  if (platform === 'win32' && process.env.LOCALAPPDATA) {
    return join(process.env.LOCALAPPDATA, 'Google/Chrome/User Data');
  }
  return null;
}

async function hasValidExtensionInProfile(userDataDir: string | null, profile: string): Promise<boolean> {
  if (!userDataDir || !PROFILE_PATTERN.test(profile)) return false;
  const extDir = join(userDataDir, profile, 'Extensions', PLAYWRIGHT_EXTENSION_ID);
  const entries = await readdir(extDir).catch(() => []);
  for (const entry of entries) {
    const manifest = await readFile(join(extDir, entry, 'manifest.json'), 'utf8')
      .then(raw => JSON.parse(raw) as { version?: unknown })
      .catch(() => undefined);
    if (typeof manifest?.version === 'string' && versionAtLeast(manifest.version, [0, 5, 0])) {
      return true;
    }
  }
  return false;
}

function profileSortRank(profile: string): number {
  return profile === 'Default' ? -1 : Number(profile.slice('Profile '.length));
}

async function readLastUsedProfile(userDataDir: string | null): Promise<string | undefined> {
  if (!userDataDir) return undefined;
  try {
    const state = JSON.parse(await readFile(join(userDataDir, 'Local State'), 'utf8')) as {
      profile?: { last_used?: unknown };
    };
    const last = state.profile?.last_used;
    return typeof last === 'string' && PROFILE_PATTERN.test(last) ? last : undefined;
  } catch {
    return undefined;
  }
}

async function listChromeProfiles(
  userDataDir: string | null,
  chromeInstalled: boolean,
): Promise<DesktopBrowserProfileItem[]> {
  const names = new Set<string>();
  if (userDataDir) {
    const entries = await readdir(userDataDir, { withFileTypes: true }).catch(() => []);
    for (const entry of entries) {
      if (entry.isDirectory() && PROFILE_PATTERN.test(entry.name)) {
        names.add(entry.name);
      }
    }
  }
  if (chromeInstalled && names.size === 0) {
    names.add('Default');
  }
  const ordered = [...names].sort((a, b) => profileSortRank(a) - profileSortRank(b));
  return Promise.all(
    ordered.map(async profile => ({
      profile,
      extension_installed: await hasValidExtensionInProfile(userDataDir, profile),
    })),
  );
}

async function probeRunningChrome(
  platform: NodeJS.Platform,
  executable: string,
  userDataDir: string,
): Promise<{ running: boolean; versionOk: boolean }> {
  try {
    let version = '';
    if (platform === 'win32') {
      version = (
        await exec(
          'powershell.exe',
          [
            '-NoProfile',
            '-NonInteractive',
            '-Command',
            '(Get-Process chrome -ErrorAction Stop | Where-Object { $_.Path -eq $env:NANO_CHROME_EXE } | Select-Object -First 1 -ExpandProperty ProductVersion)',
          ],
          { env: { ...process.env, NANO_CHROME_EXE: executable } },
        )
      ).stdout.trim();
      if (!version) return { running: false, versionOk: false };
    } else {
      const lock = await readlink(join(userDataDir, 'SingletonLock'));
      const pid = /-([1-9]\d*)$/.exec(lock)?.[1];
      if (!pid || (await exec('/bin/ps', ['-p', pid, '-o', 'comm='])).stdout.trim() !== executable) {
        return { running: false, versionOk: false };
      }
      const children = (await exec('/usr/bin/pgrep', ['-P', pid])).stdout.trim().split(/\s+/).filter(Boolean);
      if (children.length > 0) {
        const paths = (await exec('/bin/ps', ['-p', children.join(','), '-o', 'comm='])).stdout;
        version = /Google Chrome Framework\.framework\/Versions\/([\d.]+)\//.exec(paths)?.[1] ?? '';
      }
    }
    return { running: true, versionOk: versionAtLeast(version, [158, 0, 8127, 2]) };
  } catch {
    return { running: false, versionOk: false };
  }
}

async function openChromeProfileUrl(
  executable: string,
  profile: string,
  url: string,
  deps?: BrowserPairingDeps,
): Promise<void> {
  if (!PROFILE_PATTERN.test(profile)) {
    throw new Error('Use the Chrome profile directory name, such as Default or Profile 1.');
  }
  if (url !== PLAYWRIGHT_EXTENSION_STORE_URL && url !== PLAYWRIGHT_EXTENSION_TOKEN_URL) {
    throw new Error('Refusing to open non-allowlisted browser setup URL.');
  }
  if (deps?.openChromeUrl) {
    await deps.openChromeUrl(executable, profile, url);
    return;
  }
  if (process.env.CREWDEN_SUPPRESS_OS_OPEN === '1') return;
  const child = spawn(executable, [`--profile-directory=${profile}`, url], {
    detached: true,
    shell: false,
    stdio: 'ignore',
    windowsHide: false,
  });
  child.unref();
}

/** Inspect local Chrome installation, profile extension presence, and token-free pairing state. */
export async function inspectDailyBrowserStatus(
  file: string,
  requestedProfile?: string,
  deps?: BrowserPairingDeps,
): Promise<DesktopBrowserStatus> {
  const platform = deps?.platform ?? process.platform;
  if (platform !== 'darwin' && platform !== 'win32') {
    return {
      supported: false,
      state: 'unsupported',
      chrome_installed: false,
      chrome_running: false,
      chrome_version_ok: false,
      selected_profile: 'Default',
      extension_installed: false,
      profiles: [],
    };
  }

  const executable =
    deps?.chromeExecutable !== undefined ? deps.chromeExecutable : await findChromeExecutable(platform);
  const userDataDir =
    deps?.userDataDir !== undefined ? deps.userDataDir : defaultChromeUserDataDir(platform);
  const chromeInstalled = Boolean(executable);
  const profiles = await listChromeProfiles(userDataDir, chromeInstalled);
  const lastUsed = await readLastUsedProfile(userDataDir);

  let state: DesktopBrowserPairingState = 'not_paired';
  let pairedProfile: string | undefined;
  let lastCheckedAt: string | undefined;

  try {
    const raw = JSON.parse(await readFile(file, 'utf8')) as {
      id?: unknown;
      profile?: unknown;
      token?: unknown;
    };
    if (
      typeof raw.id !== 'string' ||
      typeof raw.profile !== 'string' ||
      !PROFILE_PATTERN.test(raw.profile) ||
      typeof raw.token !== 'string' ||
      !TOKEN_PATTERN.test(raw.token)
    ) {
      state = 'reconnect';
    } else {
      pairedProfile = raw.profile;
      state = 'paired';
      try {
        const status = JSON.parse(await readFile(file + '.status', 'utf8')) as {
          id?: unknown;
          state?: unknown;
          at?: unknown;
        };
        if (status.id === raw.id && (status.state === 'verified' || status.state === 'reconnect')) {
          state = status.state;
          if (typeof status.at === 'string') lastCheckedAt = status.at;
        }
      } catch (err) {
        if ((err as NodeJS.ErrnoException).code !== 'ENOENT') state = 'reconnect';
      }
      // Surface missing/removed extension immediately when the paired profile exists locally.
      if (
        (state === 'paired' || state === 'verified') &&
        userDataDir &&
        (await pathExists(join(userDataDir, pairedProfile))) &&
        !(await hasValidExtensionInProfile(userDataDir, pairedProfile))
      ) {
        state = 'reconnect';
      }
    }
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
      state = 'reconnect';
    }
  }

  const validRequested = requestedProfile && PROFILE_PATTERN.test(requestedProfile) ? requestedProfile : undefined;
  const preferredInstalled =
    (lastUsed && profiles.find(item => item.profile === lastUsed && item.extension_installed)?.profile) ??
    profiles.find(item => item.profile === 'Default' && item.extension_installed)?.profile ??
    profiles.find(item => item.extension_installed)?.profile;

  const selectedProfile =
    validRequested ??
    pairedProfile ??
    preferredInstalled ??
    (lastUsed && profiles.some(item => item.profile === lastUsed) ? lastUsed : undefined) ??
    profiles[0]?.profile ??
    'Default';

  const selectedInstalled =
    profiles.find(item => item.profile === selectedProfile)?.extension_installed ??
    (await hasValidExtensionInProfile(userDataDir, selectedProfile));

  const normalizedProfiles = profiles.some(item => item.profile === selectedProfile)
    ? profiles
    : [...profiles, { profile: selectedProfile, extension_installed: selectedInstalled }].sort(
        (a, b) => profileSortRank(a.profile) - profileSortRank(b.profile),
      );

  const runningProbe =
    deps?.chromeRunning ??
    (executable && userDataDir
      ? await probeRunningChrome(platform, executable, userDataDir)
      : { running: false, versionOk: false });

  return {
    supported: true,
    state,
    chrome_installed: chromeInstalled,
    chrome_running: runningProbe.running,
    chrome_version_ok: runningProbe.versionOk,
    ...(pairedProfile ? { paired_profile: pairedProfile } : {}),
    selected_profile: selectedProfile,
    extension_installed: selectedInstalled,
    profiles: normalizedProfiles,
    ...(lastCheckedAt ? { last_checked_at: lastCheckedAt } : {}),
  };
}

/** Open the official Chrome Web Store install page or the installed Playwright Extension token page in `profile`. */
export async function openDailyBrowserGuide(
  file: string,
  profile: string,
  target: 'auto' | 'store' | 'token' = 'auto',
  deps?: BrowserPairingDeps,
): Promise<DesktopBrowserActionResponse> {
  if (!PROFILE_PATTERN.test(profile)) {
    throw new Error('Use the Chrome profile directory name, such as Default or Profile 1.');
  }
  const platform = deps?.platform ?? process.platform;
  const status = await inspectDailyBrowserStatus(file, profile, deps);
  if (!status.supported) {
    throw new Error('Daily Chrome pairing is supported on macOS and Windows only.');
  }
  const executable =
    deps?.chromeExecutable !== undefined ? deps.chromeExecutable : await findChromeExecutable(platform);
  if (!executable) {
    throw new Error('Install Google Chrome before connecting your daily browser.');
  }
  const opened: 'store' | 'token' =
    target === 'store' || (target === 'auto' && !status.extension_installed) ? 'store' : 'token';
  const url = opened === 'store' ? PLAYWRIGHT_EXTENSION_STORE_URL : PLAYWRIGHT_EXTENSION_TOKEN_URL;
  await openChromeProfileUrl(executable, profile, url, deps);
  return { browser: status, opened };
}

/** Persist a normalized Playwright Extension token into node-private `0600` storage. */
export async function saveBrowserPairing(
  file: string,
  profile: string,
  rawToken: string,
): Promise<{ state: 'paired'; profile: string }> {
  if (!PROFILE_PATTERN.test(profile)) {
    throw new Error('Use the Chrome profile directory name, such as Default or Profile 1.');
  }
  const token = normalizeExtensionToken(rawToken);
  if (!token) throw new Error('Invalid Playwright Extension token.');
  await mkdir(dirname(file), { mode: 0o700, recursive: true });
  await atomicPrivate(file, { id: randomUUID(), profile, token });
  await rm(file + '.status', { force: true });
  return { state: 'paired', profile };
}

async function promptToken(deps?: BrowserPairingDeps): Promise<string> {
  if (deps?.interactivePrompt) {
    return (await deps.interactivePrompt()).trim();
  }
  if (!process.stdin.isTTY) {
    let token = '';
    for await (const chunk of process.stdin) {
      token += String(chunk);
      if (token.length > 512) throw new Error('Invalid Playwright Extension token.');
    }
    return token.trim();
  }
  const writeErr = deps?.stderrWrite ?? ((chunk: string) => process.stderr.write(chunk));
  writeErr('Paste the token from the official Playwright Extension (input hidden): ');
  const sink = new Writable({
    write(_chunk, _encoding, done) {
      done();
    },
  });
  const lines = createInterface({ input: process.stdin, output: sink, terminal: true });
  try {
    return (await lines.question('')).trim();
  } finally {
    lines.close();
    writeErr('\n');
  }
}

/** Pair, inspect, or disconnect the local extension without sending its token to IM. */
export async function browserCommand(
  action: string,
  file: string,
  profile: string,
  deps?: BrowserPairingDeps,
) {
  if (action === 'disconnect') {
    await rm(file, { force: true });
    await rm(file + '.status', { force: true });
    return { state: 'not_paired' };
  }
  if (action === 'status') {
    let id: string;
    try {
      id = JSON.parse(await readFile(file, 'utf8')).id;
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code === 'ENOENT')
        return { state: 'not_paired', next: 'Run browser pair on this computer.' };
      throw new Error('Cannot read pairing. Run browser pair to replace it.');
    }
    try {
      const status = JSON.parse(await readFile(file + '.status', 'utf8'));
      if (status.id === id && ['verified', 'reconnect'].includes(status.state))
        return { state: status.state, lastCheckedAt: status.at };
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw err;
    }
    return { state: 'paired', next: 'Verification occurs on the first authorized browser operation.' };
  }
  if (action !== 'pair') throw new Error('Usage: browser pair|status|disconnect [--profile Default]');
  if (!PROFILE_PATTERN.test(profile))
    throw new Error('Use the Chrome profile directory name, such as Default or Profile 1.');

  const interactive = Boolean(deps?.interactivePrompt || process.stdin.isTTY);
  const writeErr = deps?.stderrWrite ?? ((chunk: string) => process.stderr.write(chunk));
  let watcher: ReturnType<typeof setInterval> | undefined;

  try {
    if (interactive) {
      const platform = deps?.platform ?? process.platform;
      const executable =
        deps?.chromeExecutable !== undefined ? deps.chromeExecutable : await findChromeExecutable(platform);
      const userDataDir =
        deps?.userDataDir !== undefined ? deps.userDataDir : defaultChromeUserDataDir(platform);
      if ((platform === 'darwin' || platform === 'win32') && executable) {
        const installed = await hasValidExtensionInProfile(userDataDir, profile);
        if (installed) {
          await openChromeProfileUrl(executable, profile, PLAYWRIGHT_EXTENSION_TOKEN_URL, deps);
          writeErr(`Opened Playwright Extension token page in Chrome (${profile}). Copy the token there.\n`);
        } else {
          await openChromeProfileUrl(executable, profile, PLAYWRIGHT_EXTENSION_STORE_URL, deps);
          writeErr(
            `Opened Chrome Web Store in Chrome (${profile}). Click "Add to Chrome" -> "Add extension"; the token page will open automatically once installed.\n`,
          );
          let openedTokenPage = false;
          let checking = false;
          watcher = setInterval(() => {
            if (openedTokenPage || checking) return;
            checking = true;
            void hasValidExtensionInProfile(userDataDir, profile)
              .then(async ready => {
                if (!ready || openedTokenPage) return;
                openedTokenPage = true;
                if (watcher) clearInterval(watcher);
                await openChromeProfileUrl(executable, profile, PLAYWRIGHT_EXTENSION_TOKEN_URL, deps);
                writeErr(
                  `\nDetected Playwright Extension in Chrome (${profile}) — opened token page. Copy and paste the token: `,
                );
              })
              .catch(() => {})
              .finally(() => {
                checking = false;
              });
          }, deps?.pollIntervalMs ?? 800);
          watcher.unref?.();
        }
      }
    }
    const rawToken = await promptToken(deps);
    return await saveBrowserPairing(file, profile, rawToken);
  } finally {
    if (watcher) clearInterval(watcher);
  }
}
