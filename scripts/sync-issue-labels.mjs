#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const [repository, ...extra] = process.argv.slice(2);
if (!repository || extra.length || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
  console.error('Usage: node scripts/sync-issue-labels.mjs OWNER/REPO');
  process.exit(1);
}

const labels = JSON.parse(readFileSync(new URL('../.github/labels.json', import.meta.url), 'utf8'));
// Upsert only the declared labels; never delete labels or rewrite issue assignments.
for (const { name, color, description } of labels) {
  execFileSync('gh', [
    'label', 'create', name, '--repo', repository,
    '--color', color, '--description', description, '--force',
  ], { stdio: 'inherit' });
}
console.log(`Synced ${labels.length} labels to ${repository}.`);
