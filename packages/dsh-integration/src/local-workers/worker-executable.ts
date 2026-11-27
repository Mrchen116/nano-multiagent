import { stat } from 'node:fs/promises';
import { delimiter, resolve } from 'node:path';

/** Find a Windows Worker entry point in the same order for desktop settings and delegation. */
export async function findWindowsWorker(binary: string, searchPath: string): Promise<string | null> {
  for (const segment of searchPath.split(delimiter)) {
    const directory = segment.trim().replace(/^"(.*)"$/, '$1');
    if (!directory) continue;
    for (const extension of ['.exe', '.cmd', '.bat']) {
      const candidate = resolve(directory, binary + extension);
      if (await stat(candidate).then(entry => entry.isFile(), () => false)) return candidate;
    }
  }
  return null;
}

export const isWindowsBatch = (file: string) => process.platform === 'win32' && /\.(cmd|bat)$/i.test(file);
