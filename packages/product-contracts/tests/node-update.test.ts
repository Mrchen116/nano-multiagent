import { expect, it } from 'vitest';
import { parseReleaseManifest } from '../src/node-update.js';

const release = { version: '1.2.3', source_commit: 'a'.repeat(40), sha256: 'b'.repeat(64),
  package: 'nano-node.tgz', node_major: 24, pnpm_version: '11.7.0', updater_protocol: 1, data_epoch: 1,
  download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.2.3/nano-node.tgz' };

it('accepts the fixed release asset and preserves the compatibility declaration', () => {
  expect(parseReleaseManifest(release)).toEqual(release);
});
it.each([
  { download_url: 'https://example.test/nano-node.tgz' },
  { version: '1.2.4' }, { source_commit: '../escape' }, { sha256: 'bad' },
  { updater_protocol: '1' }, { release_notes: 'x'.repeat(2001) },
])('rejects untrusted or mismatched release metadata: %j', change => {
  expect(parseReleaseManifest({ ...release, ...change })).toBeNull();
});
it('retains legacy SHA install support without inventing updater capability', () => {
  const version = 'c'.repeat(40);
  const value = { ...release, version, download_url: `https://github.com/Mrchen116/nano-multiagent/releases/download/node-${version}/nano-node.tgz` };
  delete (value as Record<string, unknown>).updater_protocol;
  delete (value as Record<string, unknown>).data_epoch;
  const parsed = parseReleaseManifest(value);
  expect(parsed).toEqual(value);
  expect(parsed).not.toHaveProperty('updater_protocol');
  expect(parsed).not.toHaveProperty('data_epoch');
});

it('binds the Windows bootstrap and descriptor to the same versioned release', () => {
  const base = release.download_url.slice(0, release.download_url.lastIndexOf('/') + 1);
  const windows = {...release, platform: 'win32-x64', package: 'windows-x64.json', size: 420,
    download_url: base + 'windows-x64.json', installer: {
      download_url: base + 'Crewden-Setup-x64.exe', sha256: 'd'.repeat(64), size: 2048,
    }};
  expect(parseReleaseManifest(windows)).toEqual(windows);
  expect(parseReleaseManifest({...windows, installer: {...windows.installer, download_url: release.download_url}})).toBeNull();
  expect(parseReleaseManifest({...windows, platform: undefined})).toBeNull();
  expect(parseReleaseManifest({...release, platform: 'win32-x64'})).toBeNull();
});

it('validates desktop-darwin-arm64 and desktop-win32-x64 manifests with shell_protocol=1', () => {
  const base = release.download_url.slice(0, release.download_url.lastIndexOf('/') + 1);
  const macDesktop = {
    ...release,
    platform: 'desktop-darwin-arm64',
    package: 'desktop-darwin-arm64.json',
    size: 512,
    shell_protocol: 1,
    download_url: base + 'desktop-darwin-arm64.json',
    installer: {
      download_url: base + 'Crewden-Desktop-arm64.dmg',
      sha256: 'e'.repeat(64),
      size: 16384,
    },
  };
  const winDesktop = {
    ...release,
    platform: 'desktop-win32-x64',
    package: 'desktop-win32-x64.json',
    size: 520,
    shell_protocol: 1,
    download_url: base + 'desktop-win32-x64.json',
    installer: {
      download_url: base + 'Crewden-Desktop-Setup-x64.exe',
      sha256: 'f'.repeat(64),
      size: 24576,
    },
  };
  expect(parseReleaseManifest(macDesktop)).toEqual(macDesktop);
  expect(parseReleaseManifest(winDesktop)).toEqual(winDesktop);
  expect(parseReleaseManifest({ ...macDesktop, shell_protocol: undefined })).toBeNull();
  expect(parseReleaseManifest({ ...macDesktop, shell_protocol: 2 })).toBeNull();
  expect(parseReleaseManifest({ ...macDesktop, installer: { ...macDesktop.installer, download_url: base + 'Crewden-Setup-x64.exe' } })).toBeNull();
  expect(parseReleaseManifest({ ...release, shell_protocol: 1 })).toBeNull();
});
