/** Offline entry for an explicitly selected, stopped PA workspace or its backup copy. */
import { parseArgs } from 'node:util';
import { isAbsolute } from 'node:path';
import { PersonalMemoryStore } from './knowledge/personal-memory.js';

const { values } = parseArgs({ options: {
  workspace: { type: 'string' }, owner: { type: 'string' }, agent: { type: 'string' },
  binding: { type: 'string' }, offline: { type: 'boolean' },
} });
if (!values.offline || !values.workspace || !isAbsolute(values.workspace) || !values.owner || !values.agent || !values.binding) {
  throw new Error('Usage: node packages/dsh-integration/lib/migrate-personal-memory.js --offline --workspace /absolute/stopped/pa/workspace --owner OWNER --agent AGENT --binding BINDING');
}
const store = new PersonalMemoryStore(values.workspace, { ownerId: values.owner, agentId: values.agent, bindingId: values.binding });
const receipt = await store.execute({ action: 'migrate', idempotency_key: 'personal-memory-migration-v1' }, { sessionId: 'offline-memory-migration' });
const snapshot = await store.snapshot();
console.log(JSON.stringify({ receipt, mode: snapshot.mode, revision: snapshot.revision, record_count: snapshot.records.length,
  legacy_source_count: snapshot.records.filter(record => record.certainty === 'legacy_unverified').length,
  records_path: store.recordsPath }, null, 2));
