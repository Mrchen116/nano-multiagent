import { readFile, writeFile } from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { planRuntimeMigration, applyRuntimeMigration, verifyRuntimeMigration, type RuntimeMigrationConfig } from '@nano/dsh-integration/runtime-migration';

const {values, positionals} = parseArgs({allowPositionals: true, options: {config: {type: 'string'}, output: {type: 'string'}}});
if (!values.config || positionals.length !== 1 || !['plan', 'apply', 'verify'].includes(positionals[0]!)) {
  throw new Error('Usage: migrate-agent-runtime-partitions.ts plan|apply|verify --config /absolute/config.json [--output /protected/report.json]');
}
const config = JSON.parse(await readFile(values.config, 'utf8')) as RuntimeMigrationConfig;
const operation = positionals[0] === 'plan' ? planRuntimeMigration : positionals[0] === 'apply' ? applyRuntimeMigration : verifyRuntimeMigration;
try {
  const result = await operation(config);
  // The complete plan can contain private history/configuration; stdout carries counts and blockers only.
  if (values.output) await writeFile(values.output, JSON.stringify(result, null, 2) + '\n', {mode: 0o600});
  if ('blockers' in result) {
    console.log(JSON.stringify({phase: 'planned', sourceDigest: result.sourceDigest, sessions: result.sessions.length,
      records: result.records.length, blockers: result.blockers, report: values.output}, null, 2));
    if (result.blockers.length) process.exitCode = 1;
  } else console.log(JSON.stringify(result, null, 2));
} catch (error) {
  console.error(error instanceof Error ? error.message : 'Migration failed');
  process.exitCode = 1;
}
