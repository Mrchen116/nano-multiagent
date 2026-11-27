import { expect, it } from 'vitest';
import { classifyOriginSecurity, normalizeReleaseBaseUrl, parseReleaseManifest } from '../src/node-update.js';

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

it('classifies origin security strictly by literal IPv4/IPv6, loopback, .local, and reserved domains', () => {
  expect(classifyOriginSecurity('https://im.crewden.work')).toEqual({
    kind: 'https',
    normalizedOrigin: 'https://im.crewden.work',
  });
  expect(classifyOriginSecurity('http://im.crewden.work')).toEqual({
    kind: 'rejected_public_http',
    normalizedOrigin: 'http://im.crewden.work',
  });
  expect(classifyOriginSecurity('http://sub.crewden.work:8080')).toEqual({
    kind: 'rejected_public_http',
    normalizedOrigin: 'http://sub.crewden.work:8080',
  });
  // Must not confuse domain names starting with digits for RFC1918 IPv4 literals.
  expect(classifyOriginSecurity('http://10.evil.com')).toEqual({
    kind: 'rejected_public_http',
    normalizedOrigin: 'http://10.evil.com',
  });
  expect(classifyOriginSecurity('http://192.168.evil.com')).toEqual({
    kind: 'rejected_public_http',
    normalizedOrigin: 'http://192.168.evil.com',
  });
  // CGNAT 100.64.0.0/10 is not treated as trusted cleartext private LAN.
  expect(classifyOriginSecurity('http://100.64.0.1:8011')).toEqual({
    kind: 'rejected_public_http',
    normalizedOrigin: 'http://100.64.0.1:8011',
  });
  expect(classifyOriginSecurity('http://127.0.0.1:18080')).toEqual({
    kind: 'loopback_http',
    normalizedOrigin: 'http://127.0.0.1:18080',
  });
  expect(classifyOriginSecurity('http://localhost:8011')).toEqual({
    kind: 'loopback_http',
    normalizedOrigin: 'http://localhost:8011',
  });
  expect(classifyOriginSecurity('http://[::1]:8011')).toEqual({
    kind: 'loopback_http',
    normalizedOrigin: 'http://[::1]:8011',
  });
  expect(classifyOriginSecurity('http://10.24.8.15:8011')).toEqual({
    kind: 'private_http',
    normalizedOrigin: 'http://10.24.8.15:8011',
  });
  expect(classifyOriginSecurity('http://172.16.5.9:8011')).toEqual({
    kind: 'private_http',
    normalizedOrigin: 'http://172.16.5.9:8011',
  });
  expect(classifyOriginSecurity('http://172.32.5.9:8011').kind).toBe('rejected_public_http');
  expect(classifyOriginSecurity('http://192.168.1.20:8011')).toEqual({
    kind: 'private_http',
    normalizedOrigin: 'http://192.168.1.20:8011',
  });
  expect(classifyOriginSecurity('http://[fd12:3456::1]:8011').kind).toBe('private_http');
  expect(classifyOriginSecurity('http://crewden-box.local:8011')).toEqual({
    kind: 'private_http',
    normalizedOrigin: 'http://crewden-box.local:8011',
  });
});

it('accepts self-hosted release_base_url only when explicitly trusted and within HTTP security rules', () => {
  expect(normalizeReleaseBaseUrl('https://releases.corp.internal/crewden')).toBe('https://releases.corp.internal/crewden/');
  expect(normalizeReleaseBaseUrl('http://10.24.8.15:9000/releases', false)).toBeNull();
  expect(normalizeReleaseBaseUrl('http://10.24.8.15:9000/releases', true)).toBe('http://10.24.8.15:9000/releases/');
  expect(normalizeReleaseBaseUrl('http://im.crewden.work/releases', true)).toBeNull();
  expect(normalizeReleaseBaseUrl('http://10.evil.com/releases', true)).toBeNull();

  const privateBase = 'http://10.24.8.15:9000/releases/v1.2.3/';
  const selfHostedWinDesktop = {
    ...release,
    release_base_url: privateBase,
    platform: 'desktop-win32-x64',
    package: 'desktop-win32-x64.json',
    size: 520,
    shell_protocol: 1,
    download_url: privateBase + 'desktop-win32-x64.json',
    installer: {
      download_url: privateBase + 'Crewden-Desktop-Setup-x64.exe',
      sha256: 'f'.repeat(64),
      size: 24576,
    },
  };

  // Untrusted by default.
  expect(parseReleaseManifest(selfHostedWinDesktop)).toBeNull();
  // Rejected when private HTTP is not enabled on the verifier.
  expect(
    parseReleaseManifest(selfHostedWinDesktop, {
      trustedReleaseBaseUrls: ['http://10.24.8.15:9000/releases'],
      allowPrivateHttpReleaseBase: false,
    }),
  ).toBeNull();
  // Accepted when both trustedReleaseBaseUrls and allowPrivateHttpReleaseBase match.
  expect(
    parseReleaseManifest(selfHostedWinDesktop, {
      trustedReleaseBaseUrls: ['http://10.24.8.15:9000/releases'],
      allowPrivateHttpReleaseBase: true,
    }),
  ).toEqual(selfHostedWinDesktop);
});
