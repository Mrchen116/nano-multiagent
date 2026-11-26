import { execFile } from 'node:child_process';
import { access, readFile, readdir, readlink, rename, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { randomUUID } from 'node:crypto';

const exec = promisify(execFile);
const extensionId = 'mmlmfjhmonkocbjadbfplnigmagldckm';
const macBundle = '/Applications/Google Chrome.app';
export interface Pairing {
  id: string;
  profile: string;
  token: string;
}

/** Inspect only local install metadata. Neither status nor diagnostics expose the token. */
export async function pairing(): Promise<Pairing | undefined> {
  const file = process.env.NANO_BROWSER_PAIRING_FILE;
  if (!file) return undefined;
  try {
    const data = JSON.parse(await readFile(file, 'utf8'));
    if (
      typeof data.id !== 'string' ||
      !/^(Default|Profile [0-9]+)$/.test(data.profile) ||
      !/^[A-Za-z0-9_-]{20,256}$/.test(data.token)
    )
      throw new Error();
    return { id: data.id, profile: data.profile, token: data.token };
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw new Error('Invalid pairing record. Run browser pair on the node.');
  }
}

export async function requiresRepair(id: string) {
  const file = process.env.NANO_BROWSER_PAIRING_FILE;
  if (!file) return false;
  try {
    const prior = JSON.parse(await readFile(file + '.status', 'utf8'));
    return prior.id === id && prior.state === 'reconnect';
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw e;
  }
}

export async function recordCheck(id: string, state: 'verified' | 'reconnect') {
  const file = process.env.NANO_BROWSER_PAIRING_FILE;
  if (!file) return;
  const temp = file + '.' + randomUUID() + '.tmp';
  try {
    await writeFile(temp, JSON.stringify({ id, state, at: new Date().toISOString() }), { flag: 'wx', mode: 0o600 });
    await rename(temp, file + '.status');
  } finally {
    await rm(temp, { force: true });
  }
}

function atLeast(version: string, min: number[]) {
  if (!/^\d+(?:\.\d+)+$/.test(version)) return false;
  const nums = version.split('.').map(Number);
  for (const [index, wanted] of min.entries()) {
    const actual = nums[index] ?? 0;
    if (actual !== wanted) return actual > wanted;
  }
  return true;
}

export async function chromeExecutable() {
  const candidates =
    process.platform === 'darwin'
      ? [join(macBundle, 'Contents/MacOS/Google Chrome')]
      : process.platform === 'win32'
        ? [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA]
            .filter(Boolean)
            .map((root) => join(root!, 'Google/Chrome/Application/chrome.exe'))
        : [
            '/usr/bin/google-chrome-stable',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/opt/google/chrome/chrome',
          ];
  for (const path of candidates) {
    try {
      await access(path, 1);
      return path;
    } catch {
      /* inspect the next standard installation */
    }
  }
  throw new Error('Install Chrome or Chromium on the node before using an isolated browser.');
}

export async function dailyPrerequisites(profile: string) {
  if (!['darwin', 'win32'].includes(process.platform))
    throw new Error('Daily Chrome is supported on macOS and Windows. Choose isolated for a clean browser.');
  const exe = await chromeExecutable();
  const windows = process.platform === 'win32';
  let version: string;
  try {
    if (windows) {
      // A product version from a live process also establishes that opening the connect page will not cold-start Chrome.
      version = (
        await exec(
          'powershell.exe',
          [
            '-NoProfile',
            '-NonInteractive',
            '-Command',
            '(Get-Process chrome -ErrorAction Stop | Where-Object { $_.Path -eq $env:NANO_CHROME_EXE } | Select-Object -First 1 -ExpandProperty ProductVersion)',
          ],
          { env: { ...process.env, NANO_CHROME_EXE: exe } },
        )
      ).stdout.trim();
      if (!version) throw new Error();
    } else {
      const root = join(homedir(), 'Library/Application Support/Google/Chrome');
      const lock = await readlink(join(root, 'SingletonLock'));
      const pid = /-([1-9]\d*)$/.exec(lock)?.[1];
      if (!pid || (await exec('/bin/ps', ['-p', pid, '-o', 'comm='])).stdout.trim() !== exe) throw new Error();
      const children = (await exec('/usr/bin/pgrep', ['-P', pid])).stdout.trim().split(/\s+/);
      const paths = (await exec('/bin/ps', ['-p', children.join(','), '-o', 'comm='])).stdout;
      version = /Google Chrome Framework\.framework\/Versions\/([\d.]+)\//.exec(paths)?.[1] ?? '';
    }
  } catch {
    throw new Error('Open daily Chrome on the node, then retry.');
  }
  if (!atLeast(version, [158, 0, 8127, 2]))
    throw new Error('Update Chrome to 158.0.8127.2 or later for background connection.');
  const root = windows
    ? join(process.env.LOCALAPPDATA!, 'Google/Chrome/User Data')
    : join(homedir(), 'Library/Application Support/Google/Chrome');
  const extensionDir = join(root, profile, 'Extensions', extensionId);
  const entries = await readdir(extensionDir).catch(() => []);
  for (const entry of entries) {
    const manifest = await readFile(join(extensionDir, entry, 'manifest.json'), 'utf8')
      .then((raw) => JSON.parse(raw))
      .catch(() => undefined);
    if (manifest && atLeast(manifest.version, [0, 5, 0])) return exe;
  }
  throw new Error('Install or update the official Playwright Extension (0.5.0+) in the paired Chrome profile.');
}
