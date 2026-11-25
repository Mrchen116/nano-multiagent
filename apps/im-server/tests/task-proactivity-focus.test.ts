import { expect, it, vi } from 'vitest';
import { personalFixture } from './personal-fixture.js';
import { TaskGraphService } from '../src/task-graphs.js';

it('freezes full task_card_summaries and source provenance for PA disclosure review, failing closed on card mutation or source exclusion', () => {
  const { ctx, db, service, principal, args } = personalFixture();
  ctx.gateway.groupReply = vi.fn();
  ctx.gateway.tasks = new TaskGraphService(db, ctx.messaging);
  db.prepare("INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();

  const privateTask = ctx.gateway.tasks.execute({ kind: 'user', id: 'u1' }, 'create', {
    conversation_id: 'chat',
    title: 'Confidential Q4 pricing draft',
    description: 'Internal floor margin 38%',
    status: 'proposed',
    proposal: { rationale: 'Owner discussed Q4 margins', on_approve: 'Prepare deck' },
    request_key: 'priv-card',
  });

  const proposal = service.actions.prepare(principal, {
    ...args,
    request_key: 'send-with-card',
    conversation_id: 'peer',
    content: 'Here is the status card',
    task_cards: [{ graph_id: privateTask.graph_id, node_id: 'n1' }],
  });

  expect(proposal.evidence.payload.task_card_summaries).toEqual([
    expect.objectContaining({
      graph_id: privateTask.graph_id,
      node_id: 'n1',
      conversation_id: 'chat',
      graph_revision: 1,
      title: 'Confidential Q4 pricing draft',
      status: 'proposed',
      description: 'Internal floor margin 38%',
      proposal: expect.objectContaining({ rationale: 'Owner discussed Q4 margins', on_approve: 'Prepare deck' }),
    }),
  ]);
  expect(proposal.evidence.sources).toContainEqual({ conversation_id: 'chat', allowed: true });

  const verdict = service.actions.review(principal, {
    ...args,
    proposal_ref: proposal.proposal_ref,
    payload_digest: proposal.payload_digest,
    evidence_digest: proposal.evidence_digest,
    verdict: { decision: 'allow' },
  });

  // Mutating the referenced card after review invalidates the frozen permit with task_revision_changed.
  ctx.gateway.tasks.execute({ kind: 'user', id: 'u1' }, 'apply', {
    graph_id: privateTask.graph_id,
    base_revision: 1,
    request_key: 'mutate-after-review',
    change_note: '',
    operations: [{ op: 'update_task', node_id: 'n1', patch: { description: 'Secret acquisition target added' } }],
  });
  expect(() =>
    service.actions.commit(principal, { ...args, proposal_ref: proposal.proposal_ref, verdict_ref: verdict.verdict_ref }),
  ).toThrow('task_revision_changed');

  // Re-preparing at the new revision and revoking read access to the card's conversation fails closed.
  const fresh = service.actions.prepare(principal, {
    ...args,
    request_key: 'send-with-card-v2',
    conversation_id: 'peer',
    content: 'Here is the status card',
    task_cards: [{ graph_id: privateTask.graph_id, node_id: 'n1' }],
  });
  const freshVerdict = service.actions.review(principal, {
    ...args,
    proposal_ref: fresh.proposal_ref,
    payload_digest: fresh.payload_digest,
    evidence_digest: fresh.evidence_digest,
    verdict: { decision: 'allow' },
  });
  db.prepare("INSERT INTO conversations(id,title,type,space_id,created_at) VALUES('shared-src','Shared','group','company:default',datetime('now'))").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('shared-src','u1')").run();
  const sharedCard = ctx.gateway.tasks.execute({ kind: 'user', id: 'u1' }, 'create', {
    conversation_id: 'shared-src',
    title: 'Shared card',
    request_key: 'shared-card',
  });
  const sharedProposal = service.actions.prepare(principal, {
    ...args,
    request_key: 'send-shared-card',
    conversation_id: 'peer',
    content: 'Card from shared group',
    task_cards: [{ graph_id: sharedCard.graph_id, node_id: 'n1' }],
  });
  const sharedVerdict = service.actions.review(principal, {
    ...args,
    proposal_ref: sharedProposal.proposal_ref,
    payload_digest: sharedProposal.payload_digest,
    evidence_digest: sharedProposal.evidence_digest,
    verdict: { decision: 'allow' },
  });
  service.updatePolicy('o1', { expected_revision: 1, excluded_conversation_ids: ['shared-src'] });
  expect(() =>
    service.actions.commit(principal, { ...args, proposal_ref: sharedProposal.proposal_ref, verdict_ref: sharedVerdict.verdict_ref }),
  ).toThrow('source_revoked');
  void freshVerdict;
});

it('keeps unassigned group quick-captures visible in mine active and scopes completed history across all node depths', () => {
  const { ctx, db } = personalFixture();
  const tasks = new TaskGraphService(db, ctx.messaging);
  db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,created_at) VALUES('team-joined','Joined Group','group','public','company:default',datetime('now'))").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('team-joined','u1')").run();
  db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,created_at) VALUES('team-unjoined','Other Public Group','group','public','company:default',datetime('now'))").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('team-unjoined','u2')").run();

  // Unassigned quick-capture created by u1 in a joined group appears in scope="mine" active.
  const quick = tasks.execute({ kind: 'user', id: 'u1' }, 'create', {
    conversation_id: 'team-joined',
    title: 'Quick group reminder',
    mode: 'none',
    status: 'todo',
    request_key: 'quick-grp',
  });
  // Completed child stage created by u1 vs unrelated done task in unjoined public group.
  const goal = tasks.execute({ kind: 'user', id: 'u1' }, 'create', {
    conversation_id: 'team-joined',
    title: 'Multi-stage goal',
    mode: 'dag',
    status: 'doing',
    request_key: 'goal-grp',
    operations: [{ op: 'add_task', container_id: 'n1', client_ref: 's1', title: 'Completed child stage', status: 'done' }],
  });
  tasks.execute({ kind: 'user', id: 'u2' }, 'create', {
    conversation_id: 'team-unjoined',
    title: 'Unrelated public done task',
    status: 'done',
    request_key: 'unjoined-done',
  });

  const mineFocus = tasks.execute({ kind: 'user', id: 'u1' }, 'focus', { scope: 'mine' });
  expect(mineFocus.active.map((x: any) => x.graph_id)).toContain(quick.graph_id);
  expect(mineFocus.completed_count).toBe(1);

  const mineCompleted = tasks.execute({ kind: 'user', id: 'u1' }, 'focus', { scope: 'mine', section: 'completed' });
  expect(mineCompleted.completed.map((x: any) => `${x.graph_id}:${x.node_id}`)).toEqual([`${goal.graph_id}:n2`]);
});
