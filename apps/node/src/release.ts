import { readFile } from 'node:fs/promises';
import { delimiter, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  parseReleaseManifest,
  type NodeRelease,
  type ParseReleaseManifestOptions,
  type ReleaseManifest,
} from '@nano/product-contracts';

export const releaseRoot = fileURLToPath(new URL('../../../', import.meta.url));

async function readJsonObject(path: string): Promise<Record<string, unknown> | null> {
  try {
    const parsed = JSON.parse(await readFile(path, 'utf8'));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

/** Deterministically resolve trusted self-hosted release base options from installation files.
 *
 * Works identically across `local-admin`, Windows Scheduled Task (`DesktopGatewayHost`),
 * macOS `launchd`, and detached `update-worker` processes without relying on env inheritance.
 *
 * Args:
 *   root: Installed release version directory.
 * Returns:
 *   `ParseReleaseManifestOptions` containing any configured trusted release base URLs.
 */
export async function loadTrustedReleaseOptions(root = releaseRoot): Promise<ParseReleaseManifestOptions> {
  const trusted = new Set<string>();
  let allowPrivateHttpReleaseBase = false;
  const nanoMeta = await readJsonObject(resolve(root, '.nano-release.json'));
  if (typeof nanoMeta?.trusted_release_base_url === 'string' && nanoMeta.trusted_release_base_url.trim()) {
    trusted.add(nanoMeta.trusted_release_base_url.trim());
  }
  if (nanoMeta?.allow_private_http_release_base === true) {
    allowPrivateHttpReleaseBase = true;
  }
  const desktopHome = resolve(process.env.CREWDEN_DESKTOP_HOME ?? resolve(root, '../..'));
  const desktopDefaults = await readJsonObject(resolve(desktopHome, 'desktop-defaults.json'));
  if (typeof desktopDefaults?.trusted_release_base_url === 'string' && desktopDefaults.trusted_release_base_url.trim()) {
    trusted.add(desktopDefaults.trusted_release_base_url.trim());
  }
  if (desktopDefaults?.allow_private_http_release_base === true) {
    allowPrivateHttpReleaseBase = true;
  }
  return trusted.size > 0
    ? { trustedReleaseBaseUrls: [...trusted], allowPrivateHttpReleaseBase }
    : {};
}

/** Read the package's build identity and verified installation record.
 * Args:
 *   root: Installed package directory, defaulting to this running package.
 * Returns:
 *   Actual managed release, or a source checkout identity.
 */
export async function loadNodeRelease(root = releaseRoot): Promise<NodeRelease> {
  let manifest: ReleaseManifest | null;
  try {
    const raw = JSON.parse(await readFile(resolve(root, '.release-manifest.json'), 'utf8'));
    const trustedOptions = await loadTrustedReleaseOptions(root);
    manifest = parseReleaseManifest(raw, trustedOptions);
  }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {kind: 'source', version: 'source'}; throw error; }
  if (!manifest) throw new Error('Invalid installed release manifest');
  await verifyReleaseMetadata(root, manifest);
  return {kind: 'managed', ...(manifest.platform ? {platform: manifest.platform} : {}), version: manifest.version, source_commit: manifest.source_commit ?? manifest.version,
    sha256: manifest.sha256, updater_protocol: manifest.updater_protocol, data_epoch: manifest.data_epoch,
    ...(manifest.shell_protocol !== undefined ? {shell_protocol: manifest.shell_protocol} : {})};
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
  const toolsRoot = ['win32-x64', 'desktop-darwin-arm64', 'desktop-win32-x64'].includes(release.platform ?? '') ? resolve(root, 'runtime') : resolve(root, '../..');
  return { command: process.execPath, args: [resolve(toolsRoot, 'tooling/node_modules/pnpm/bin/pnpm.cjs')],
    env: { PATH: `${dirname(process.execPath)}${delimiter}${process.env.PATH ?? ''}` } };
}
