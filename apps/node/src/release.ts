import { readFile } from 'node:fs/promises';
import { delimiter, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseReleaseManifest, type NodeRelease, type ReleaseManifest } from '@nano/product-contracts';

export const releaseRoot = fileURLToPath(new URL('../../../', import.meta.url));
/** Read the package's build identity and verified installation record.
 * Args:
 *   root: Installed package directory, defaulting to this running package.
 * Returns:
 *   Actual managed release, or a source checkout identity.
 */
export async function loadNodeRelease(root = releaseRoot): Promise<NodeRelease> {
  let manifest: ReleaseManifest | null;
  try { manifest = parseReleaseManifest(JSON.parse(await readFile(resolve(root, '.release-manifest.json'), 'utf8'))); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {kind: 'source', version: 'source'}; throw error; }
  if (!manifest) throw new Error('Invalid installed release manifest');
  await verifyReleaseMetadata(root, manifest);
  return {kind: 'managed', version: manifest.version, source_commit: manifest.source_commit ?? manifest.version,
    sha256: manifest.sha256, updater_protocol: manifest.updater_protocol, data_epoch: manifest.data_epoch};
}
/** Check extracted package identity against its independently verified manifest. */
export async function verifyReleaseMetadata(root: string, manifest: ReleaseManifest): Promise<void> {
  const metadata = JSON.parse(await readFile(resolve(root, '.nano-release.json'), 'utf8'));
  if (metadata.source_commit !== (manifest.source_commit ?? manifest.version)
      || metadata.updater_protocol !== 1 || metadata.data_epoch !== 1
      || manifest.updater_protocol !== 1 || manifest.data_epoch !== 1)
    throw new Error('Package release metadata does not match the compatible manifest');
}

/** Supply the installer's private pnpm for managed Node package operations.
 *
 * Args:
 *   release: Verified identity of this running Node.
 *   root: Release directory beneath the installation's releases directory.
 * Returns:
 *   Bundled invocation for managed installs, or the native default for source checkouts.
 */
export function installedPackageManager(release: NodeRelease, root = releaseRoot) {
  if (release.kind !== 'managed') return;
  return { command: process.execPath, args: [resolve(root, '../../tooling/node_modules/pnpm/bin/pnpm.cjs')],
    env: { PATH: `${dirname(process.execPath)}${delimiter}${process.env.PATH ?? ''}` } };
}
