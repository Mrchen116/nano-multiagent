import { readFile } from 'node:fs/promises';
import type { ApprovalConfiguration } from '@nano/product-contracts';

export interface ReviewDecision { behavior: 'allow' | 'deny'; reason: string; risk?: 'low' | 'medium' | 'high' }
const assets = new URL('../../assets/auto/', import.meta.url);
const loaded = new Map<string, Promise<string>>();
export function policyAsset(name: string): Promise<string> {
  if (!loaded.has(name)) loaded.set(name, readFile(new URL(name, assets), 'utf8'));
  return loaded.get(name)!;
}
export function parseNanoDecision(text: string): ReviewDecision | undefined {
  const clean = text.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').replace(/<thinking>[\s\S]*$/, '');
  const block = /<block>(yes|no)\b(?:<\/block>)?/i.exec(clean)?.[1]?.toLowerCase();
  if (!block) return;
  return { behavior: block === 'yes' ? 'deny' : 'allow', reason: block === 'yes' ? /<reason>([\s\S]*?)<\/reason>/.exec(clean)?.[1]?.trim() || 'Blocked by classifier' : 'Allowed by classifier' };
}
export function parseDshDecision(text: string): ReviewDecision | undefined {
  let value: { risk?: string; decision?: string; reason?: string };
  try { value = JSON.parse(text); } catch { return; }
  if (!value || typeof value !== 'object' || Object.keys(value).some(key => !['risk', 'decision', 'reason'].includes(key))) return;
  if (value.decision === 'allow' && ['low', 'medium'].includes(value.risk ?? '') && value.reason === undefined) return { behavior: 'allow', reason: 'Allowed by classifier' };
  if (value.decision === 'deny' && ['medium', 'high'].includes(value.risk ?? '') && (value.reason === undefined || typeof value.reason === 'string')) return { behavior: 'deny', reason: value.reason || 'Blocked by classifier', risk: value.risk as 'medium' | 'high' };
}
/** Pinned policy assets, with configured text expanded exactly once. */
export async function buildPolicy(config: ApprovalConfiguration, cwd: string) {
  if (config.rules === 'dsh') return policyAsset('dsh-5badb150.txt');
  const base = 'cc-2.1.267-nano-v1/';
  const defaults = JSON.parse(await policyAsset(base + 'defaults.json')) as Record<string, string[]>;
  const paths: Record<string, string> = { workspace_root: cwd, global_config_dir: config.globalRoot, workspace_config_dir: `${cwd}/.nanoassistant` };
  const withPaths = (text: string) => text.replace(/<nano_(workspace_root|global_config_dir|workspace_config_dir)>/g, (_, key: string) => paths[key]!);
  const configured = { allow: config.allow, soft_deny: config.softDeny, hard_deny: config.hardDeny, environment: config.environment };
  const replacements: Record<string, string> = {};
  for (const [key, values] of Object.entries(defaults)) {
    const original = values.map(withPaths); const selected = configured[key as keyof typeof configured];
    let expanded = false;
    replacements[key] = (selected.length ? selected.flatMap(rule => {
      if (rule !== '$defaults') return [rule]; if (expanded) return []; expanded = true; return original;
    }) : original).map(rule => `- ${rule}`).join('\n');
  }
  return withPaths(await policyAsset(base + 'security_monitor.txt')).replace(/<nano_(allow|soft_deny|hard_deny|environment)_rules>/g, (_, key: string) => replacements[key]!);
}
