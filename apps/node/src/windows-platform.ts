import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

const exec = promisify(execFile);
const host = fileURLToPath(new URL('./GatewayHost.exe', import.meta.url));

/** Invoke the current release's current-user Windows lifecycle adapter. */
export async function windowsHost(...args: string[]): Promise<string> {
  const {stdout} = await exec(host, args, {windowsHide: true, encoding: 'utf8'});
  return stdout.trim();
}
