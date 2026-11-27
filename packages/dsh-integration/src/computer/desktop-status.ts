import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

export const cuaDriver = '/Applications/CuaDriver.app/Contents/MacOS/cua-driver';
const exec = promisify(execFile);

/** Query the application-owned daemon without starting it or requesting macOS grants. */
export async function desktopStatus(signal: AbortSignal) {
  if (process.platform !== 'darwin')
    return { available: false, message: 'Native window control requires a macOS node.' };
  let stdout: string;
  try {
    ({ stdout } = await exec(cuaDriver, ['permissions', 'status', '--json'], { signal, timeout: 5000 }));
  } catch (error) {
    signal.throwIfAborted();
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return { available: false, message: 'Install the Nano node CuaDriver.app dependency on this Mac.' };
    }
    throw error;
  }
  const status = JSON.parse(stdout);
  if (status.daemon_running === false || status.status === 'unknown') {
    return {
      available: false,
      message: 'Open CuaDriver.app or run cua-driver permissions grant on the node, then retry.',
    };
  }
  return {
    available: true,
    accessibility: status.accessibility === true,
    screen_recording: status.screen_recording === true,
  };
}

/** Reject desktop targets whose normal control surface belongs to the browser or shell tools. */
export function checkDesktopRole(info: {
  CFBundleIdentifier?: string;
  LSApplicationCategoryType?: string;
  CFBundleURLTypes?: { CFBundleURLSchemes?: string[] }[];
}) {
  const identifier = info.CFBundleIdentifier?.toLowerCase();
  if (!identifier) throw new Error('The application bundle identity is unavailable.');
  const schemes = new Set(
    (info.CFBundleURLTypes ?? []).flatMap((type) => type.CFBundleURLSchemes ?? []).map((s) => s.toLowerCase()),
  );
  if (
    schemes.has('http') ||
    schemes.has('https') ||
    /^(com\.apple\.safari|com\.google\.chrome|org\.mozilla\.firefox|com\.microsoft\.edgemac|com\.brave\.browser|org\.chromium\.chromium)(\.|$)/.test(
      identifier,
    )
  ) {
    throw new Error('Use the browser surface for this browser; native control is unavailable.');
  }
  const codeApps = new Set([
    'com.apple.terminal',
    'com.apple.scripteditor2',
    'com.apple.automator',
    'com.apple.shortcuts',
    'com.apple.dt.xcode',
    'com.googlecode.iterm2',
    'com.mitchellh.ghostty',
    'dev.warp.warp-stable',
    'net.kovidgoyal.kitty',
    'org.alacritty',
    'com.github.wez.wezterm',
    'org.hammerspoon.hammerspoon',
    'com.microsoft.vscode',
    'com.microsoft.vscodeinsiders',
    'com.todesktop.230313mzl4w4u92',
    'dev.zed.zed',
  ]);
  if (
    codeApps.has(identifier) ||
    info.LSApplicationCategoryType === 'public.app-category.developer-tools' ||
    ['ssh', 'telnet', 'applescript'].some((scheme) => schemes.has(scheme))
  ) {
    throw new Error(
      'Use the task’s approved shell tools for terminal, scripting and development applications.',
    );
  }
}

/** Check the running application's installed bundle, using only a path observed by Cua. */
export async function verifyDesktopApp(bundleId: string, path: string | undefined, signal: AbortSignal) {
  if (!path?.startsWith('/') || !path.endsWith('.app'))
    throw new Error('Cannot verify the installed desktop bundle.');
  const { stdout } = await exec(
    '/usr/bin/plutil',
    ['-convert', 'json', '-o', '-', path + '/Contents/Info.plist'],
    { signal, timeout: 3000 },
  );
  const info = JSON.parse(stdout);
  if (info.CFBundleIdentifier !== bundleId)
    throw new Error('Desktop bundle identity changed. Select the application again.');
  checkDesktopRole(info);
}
