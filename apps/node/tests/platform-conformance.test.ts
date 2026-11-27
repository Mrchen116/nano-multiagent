import { mkdtemp, readFile, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  ensurePrivateDirectory,
  isPathWithinRoot,
  localNodeBridgeEndpoint,
  readMachineBootToken,
  syncDirectoryIfSupported,
} from '../src/platform-io.js';

interface IpcVectorCase {
  id: string;
  platform: NodeJS.Platform;
  config_path: string;
  tmpdir: string;
  expected_endpoint: string;
}

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');

describe('apps/node cross-platform I/O conformance', () => {
  it('matches src/IM/shared/local-ipc-endpoint-test-cases.json byte-for-byte across win32, darwin, and linux', async () => {
    const raw = await readFile(
      join(repoRoot, 'src/IM/shared/local-ipc-endpoint-test-cases.json'),
      'utf8',
    );
    const parsed = JSON.parse(raw) as { cases: IpcVectorCase[] };
    expect(parsed.cases.length).toBeGreaterThanOrEqual(6);

    for (const item of parsed.cases) {
      const actual = localNodeBridgeEndpoint(item.config_path, {
        platform: item.platform,
        tmpdir: item.tmpdir,
      });
      expect(actual, item.id).toBe(item.expected_endpoint);
    }
  });

  it('skips directory fsync on win32 and flushes real directory handles on POSIX', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'nano-platform-sync-'));
    try {
      await expect(syncDirectoryIfSupported('Z:\\nonexistent-win-dir', 'win32')).resolves.toBeUndefined();
      if (process.platform !== 'win32') {
        await expect(syncDirectoryIfSupported(dir, process.platform)).resolves.toBeUndefined();
      }
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it('enforces private directory permissions on POSIX and delegates ACL hardening on win32', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'nano-platform-priv-'));
    const sub = join(dir, 'secret');
    try {
      const winCalls: Array<[string, ...string[]]> = [];
      await ensurePrivateDirectory(sub, {
        platform: 'win32',
        runWindowsHost: async (cmd, ...args) => {
          winCalls.push([cmd, ...args]);
          return 'ok';
        },
      });
      expect(winCalls).toEqual([['private-directory', sub]]);

      if (process.platform !== 'win32') {
        const posixSub = join(dir, 'posix-secret');
        await ensurePrivateDirectory(posixSub, { platform: process.platform });
        const info = await stat(posixSub);
        expect(info.mode & 0o777).toBe(0o700);
      }
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it('checks workspace root containment with OS-appropriate case sensitivity and boundary separators', () => {
    expect(isPathWithinRoot('/ws/agent-a/file.txt', '/ws/agent-a', 'darwin')).toBe(true);
    expect(isPathWithinRoot('/ws/agent-a-sibling/file.txt', '/ws/agent-a', 'darwin')).toBe(false);
    expect(isPathWithinRoot('/ws/Agent-A/file.txt', '/ws/agent-a', 'linux')).toBe(false);

    expect(
      isPathWithinRoot('C:\\Workspaces\\Agent-A\\Sub\\file.txt', 'c:\\workspaces\\agent-a', 'win32'),
    ).toBe(true);
    expect(
      isPathWithinRoot('C:\\Workspaces\\Agent-A-Other\\file.txt', 'C:\\Workspaces\\Agent-A', 'win32'),
    ).toBe(false);
  });

  it('resolves trimmed machine boot tokens across win32, darwin, and linux', async () => {
    await expect(
      readMachineBootToken({
        platform: 'win32',
        runWindowsHost: async cmd => (cmd === 'boot' ? ' 2026-11-27T00:00:00Z \n' : ''),
      }),
    ).resolves.toBe('2026-11-27T00:00:00Z');

    await expect(
      readMachineBootToken({
        platform: 'darwin',
        execDarwinBootTime: () => '{ sec = 1760000000, usec = 0 }\n',
      }),
    ).resolves.toBe('{ sec = 1760000000, usec = 0 }');

    await expect(
      readMachineBootToken({
        platform: 'linux',
        readLinuxBootId: async () => '7f1d9c44-1122-3344-5566-778899aabbcc\n',
      }),
    ).resolves.toBe('7f1d9c44-1122-3344-5566-778899aabbcc');
  });
});
