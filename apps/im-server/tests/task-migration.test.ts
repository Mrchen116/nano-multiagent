import { afterEach, expect, it, vi } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fixture } from './control-fixture.js';
import { TaskGraphService } from '../src/task-graphs.js';
import { Messaging } from '../src/messaging.js';
import { applyMigration, inspectMigration, verifyMigration } from '../src/migrate-task-collaboration.js';

const directories: string[] = [];
afterEach(() => { for (const path of directories.splice(0)) rmSync(path, { recursive: true }); });

it('migrates an evidenced Agent assignee before personal-space columns exist', async () => {
  const { db, ctx } = fixture();
  ctx.gateway.broadcast = vi.fn();
  ctx.messaging = new Messaging(ctx);
  const graph = new TaskGraphService(db, ctx.messaging).execute({ kind: 'user', id: 'u1' }, 'create', {
    title: 'Legacy task', mode: 'dag', conversation_id: 'chat', request_key: 'legacy',
  });
  const document = JSON.parse(db.prepare('SELECT document_json FROM task_graphs').get()!.document_json as string);
  document.schema_version = 1;
  delete document.conversation_id;
  for (const node of document.nodes) { delete node.created_by; delete node.assignee; }
  db.prepare('UPDATE task_graphs SET document_json=?').run(JSON.stringify(document));
  db.exec(`DELETE FROM task_graph_mutation_receipts;
    ALTER TABLE task_graphs DROP COLUMN conversation_id;
    ALTER TABLE task_graph_mutation_receipts DROP COLUMN conversation_id;
    ALTER TABLE conversations DROP COLUMN visibility;
    ALTER TABLE conversations DROP COLUMN dissolved_at;
    ALTER TABLE conversations DROP COLUMN space_id;
    ALTER TABLE agent_profiles DROP COLUMN space_id;
    ALTER TABLE users DROP COLUMN personal_space_enabled;`);
  // Historical Agent placeholders need not be active; their company owner confers eligibility.
  db.prepare("UPDATE users SET membership_status='pending',owner_id='' WHERE id='a1'").run();
  const mapping = inspectMigration(db);
  mapping.graphs[graph.graph_id] = {
    conversation_id: 'chat', evidence: 'Reviewed original conversation',
    nodes: { n1: { created_by: { type: 'user', id: 'u1' }, assignee: { type: 'agent', id: 'a' }, evidence: 'Reviewed original assignment' } },
  };
  const directory = mkdtempSync(join(tmpdir(), 'nano-task-migration-'));
  directories.push(directory);
  const backup = join(directory, 'before.sqlite3');
  expect(await applyMigration(db, mapping, backup)).toMatchObject({ state: 'migrated', graphs: 1, nodes: 1 });
  const migrated = JSON.parse(db.prepare('SELECT document_json FROM task_graphs').get()!.document_json as string);
  expect(migrated.nodes[0].assignee).toEqual({ type: 'agent', id: 'a' });
  const before = new DatabaseSync(backup, { readOnly: true });
  try { expect(verifyMigration(db, before)).toMatchObject({ state: 'verified', graphs: 1 }); }
  finally { before.close(); }
});
