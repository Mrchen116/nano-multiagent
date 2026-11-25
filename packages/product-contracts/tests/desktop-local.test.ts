import { expect, it } from 'vitest';
import {
  extractDesktopProxySettings,
  isBlockedDesktopOpenPath,
  mergeDesktopEnvironment,
  validateDesktopProxyUrl,
} from '../src/desktop-local.js';

it('normalizes HTTP(S) proxy settings into the 9 gateway environment keys and strips them when disabled', () => {
  const merged = mergeDesktopEnvironment(
    { NANO_OWNER_CONFIG_ROOT: '/isolated/owner', OLD_KEY: 'drop' },
    { enabled: true, url: 'http://127.0.0.1:7890', no_proxy: 'localhost,127.0.0.1' },
    [
      { key: 'SEARXNG_URL', value: 'http://127.0.0.1:8888' },
      { key: 'PATH', value: '/opt/homebrew/bin:/usr/bin:/bin' },
    ],
  );
  expect(merged).toEqual({
    NANO_OWNER_CONFIG_ROOT: '/isolated/owner',
    SEARXNG_URL: 'http://127.0.0.1:8888',
    PATH: '/opt/homebrew/bin:/usr/bin:/bin',
    NODE_USE_ENV_PROXY: '1',
    HTTP_PROXY: 'http://127.0.0.1:7890',
    http_proxy: 'http://127.0.0.1:7890',
    HTTPS_PROXY: 'http://127.0.0.1:7890',
    https_proxy: 'http://127.0.0.1:7890',
    ALL_PROXY: 'http://127.0.0.1:7890',
    all_proxy: 'http://127.0.0.1:7890',
    NO_PROXY: 'localhost,127.0.0.1',
    no_proxy: 'localhost,127.0.0.1',
  });

  const extracted = extractDesktopProxySettings(merged);
  expect(extracted).toEqual({
    proxy: { enabled: true, url: 'http://127.0.0.1:7890', no_proxy: 'localhost,127.0.0.1' },
    userEnvironment: [
      { key: 'SEARXNG_URL', value: 'http://127.0.0.1:8888' },
      { key: 'PATH', value: '/opt/homebrew/bin:/usr/bin:/bin' },
    ],
  });

  const disabled = mergeDesktopEnvironment(
    merged,
    { enabled: false, url: 'http://127.0.0.1:7890', no_proxy: 'localhost' },
    extracted.userEnvironment,
  );
  expect(disabled).toEqual({
    NANO_OWNER_CONFIG_ROOT: '/isolated/owner',
    SEARXNG_URL: 'http://127.0.0.1:8888',
    PATH: '/opt/homebrew/bin:/usr/bin:/bin',
  });
});

it('rejects socks:// proxy URLs and forbids overriding managed keys in userEnvironment', () => {
  expect(() => validateDesktopProxyUrl('socks5://127.0.0.1:1080')).toThrow(/socks:\/\//i);
  expect(() => validateDesktopProxyUrl('socks://127.0.0.1:1080')).toThrow(/socks:\/\//i);
  expect(() => validateDesktopProxyUrl('not-a-url')).toThrow(/http:\/\//i);
  expect(() =>
    mergeDesktopEnvironment(undefined, { enabled: false, url: '', no_proxy: '' }, [
      { key: 'HTTPS_PROXY', value: 'http://127.0.0.1:7890' },
    ]),
  ).toThrow(/managed automatically/i);
  expect(() =>
    mergeDesktopEnvironment(undefined, { enabled: false, url: '', no_proxy: '' }, [
      { key: 'NANO_OWNER_CONFIG_ROOT', value: '/escape' },
    ]),
  ).toThrow(/managed automatically/i);
});

it('blocks executable scripts and app bundles from direct open while allowing regular documents', () => {
  expect(isBlockedDesktopOpenPath('reports/perf-audit.md')).toBe(false);
  expect(isBlockedDesktopOpenPath('data/output.json')).toBe(false);
  expect(isBlockedDesktopOpenPath('scripts/run-bench.sh')).toBe(true);
  expect(isBlockedDesktopOpenPath('tools/setup.EXE')).toBe(true);
  expect(isBlockedDesktopOpenPath('dist/Crewden.app')).toBe(true);
  expect(isBlockedDesktopOpenPath('dist/Crewden.app/Contents/MacOS/crewden')).toBe(true);
  expect(isBlockedDesktopOpenPath('scripts/deploy.ps1')).toBe(true);
});
