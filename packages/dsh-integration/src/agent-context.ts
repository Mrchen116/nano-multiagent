import { initProfile, readProfileManifest } from '@deepseek-ai/dsh-app-boot';
import { saveManifest } from '@deepseek-ai/dsh-plugin-manager/operations';

export const agentContextBundle = 'dsh-agent-context';
export const contextTools = new Set(['notes', 'history', 'new_context', 'get_context_remaining']);

/** Seed the shipped context bundle once, preserving later native disable choices.
 *
 * Args:
 *   dir: Trusted workspace profile directory owned by Nano.
 */
export async function initializeContextProfile(dir: string): Promise<void> {
  initProfile(dir, []);
  const manifest = readProfileManifest('nano', dir) as ReturnType<typeof readProfileManifest> & {nano?: {agentContextDefaultInitialized?: boolean}};
  if (manifest.nano?.agentContextDefaultInitialized) return;
  const bundles = manifest.dsh?.profile?.bundles ?? [];
  // An existing installed-but-unselected copy is a prior explicit opt-out.
  if (!bundles.includes(agentContextBundle) && !manifest.dependencies?.[agentContextBundle]) {
    manifest.dsh = {...manifest.dsh, profile: {...manifest.dsh?.profile, bundles: [agentContextBundle, ...bundles]}};
  }
  manifest.nano = {...manifest.nano, agentContextDefaultInitialized: true};
  await saveManifest(dir, manifest);
}
