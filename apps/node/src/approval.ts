import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { load } from 'js-yaml';
import { approvalDefaults, type ApprovalConfiguration } from '@nano/product-contracts';

/** Reads existing product configuration sections; workspace fields override owner fields. */
export function readApproval(globalRoot: string, workspace: string): ApprovalConfiguration {
  const section = (root: string): Record<string, unknown> => {
    try { const file = load(readFileSync(join(root, 'config.yaml'), 'utf8')) as { auto_mode?: Record<string, unknown> } | null; return file?.auto_mode ?? {}; }
    catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {}; throw error; }
  };
  const raw = { ...section(globalRoot), ...section(join(workspace, '.nanoassistant')) };
  const result: ApprovalConfiguration = { ...approvalDefaults, globalRoot };
  const fields = { enabled: 'enabled', rules: 'rules', dangerously_skip_permissions: 'dangerouslySkipPermissions', always_allow_tools: 'alwaysAllowTools',
    deny_limit: 'denyLimit', total_deny_limit: 'totalDenyLimit', ask_timeout_sec: 'askTimeoutSec', unattended_fallback: 'unattendedFallback',
    allow: 'allow', soft_deny: 'softDeny', hard_deny: 'hardDeny', environment: 'environment' } as const;
  for (const [from, to] of Object.entries(fields)) {
    const value = raw[from]; const current = result[to];
    if (Array.isArray(current)) { if (Array.isArray(value)) Object.assign(result, { [to]: value.filter(item => typeof item === 'string') }); }
    else if (typeof value === typeof current) Object.assign(result, { [to]: value });
  }
  if (!['nano', 'dsh'].includes(result.rules)) throw new Error('auto_mode.rules must be nano or dsh');
  if (!['allow', 'deny'].includes(result.unattendedFallback)) throw new Error('Invalid auto_mode.unattended_fallback');
  return result;
}
