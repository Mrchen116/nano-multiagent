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
  expect(parseReleaseManifest(value)?.updater_protocol).toBeUndefined();
});
