import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

const exec = promisify(execFile);
const standardHost = fileURLToPath(new URL('./GatewayHost.exe', import.meta.url));
const desktopHost = fileURLToPath(new URL('./DesktopGatewayHost.exe', import.meta.url));

function selectWindowsHost(args: string[]): string {
  const configArg = args[1];
  const desktopActive = typeof configArg === 'string' && configArg.endsWith('.yaml') && existsSync(join(dirname(configArg), '.desktop-active.json'));
  if ((desktopActive || process.env.CREWDEN_DESKTOP_MANAGED === '1') && existsSync(desktopHost)) {
    return desktopHost;
  }
  if (!existsSync(standardHost) && existsSync(desktopHost)) {
    return desktopHost;
  }
  return standardHost;
}

/** Invoke the current release's current-user Windows lifecycle adapter. */
export async function windowsHost(...args: string[]): Promise<string> {
  const binary = selectWindowsHost(args);
  const {stdout} = await exec(binary, args, {windowsHide: true, encoding: 'utf8'});
  return stdout.trim();
}
