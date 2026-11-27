import { expect, it, vi } from 'vitest';
import { featureDependencies } from '@nano/product-contracts/capabilities';
import { connectFixtureGateway } from './control-fixture.js';
import { personalFixture } from './personal-fixture.js';
import { createAgent, featureOptions } from '../src/agent-creation.js';
import { configurationOperations } from '../src/configuration-assembly.js';
import { readAgentProfile } from '../src/configuration-records.js';
import { TaskGraphService, withdrawsTask } from '../src/task-graphs.js';

it('freezes full task_card_summaries and source provenance for PA disclosure review, failing closed on card mutation or source exclusion', () => {
  const { ctx, db, service, principal, args } = personalFixture();
  ctx.gateway.groupReply = vi.fn();
  ctx.gateway.tasks = new TaskGraphService(db, ctx.messaging);
  db.prepare("INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();

  const privateTask = ctx.gateway.tasks.execute({ kind: 'user', id: 'u1' }, 'create', {
    conversation_id: 'chat',
    title: 'Confidential Q4 pricing draft',
    description: 'Internal floor margin 38%; prepare deck on approval',
    status: 'proposed',
    proposed_for_user_id: 'u1',
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
      description: 'Internal floor margin 38%; prepare deck on approval',
      proposed_for_user_id: 'u1',
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

it('auto-fills proposed_for_user_id and surfaces mine focus across 1v1 human-Agent DMs without leaking across human DMs or groups', () => {
  const { ctx, db } = personalFixture();
  const tasks = new TaskGraphService(db, ctx.messaging);
  const now = new Date().toISOString();

  // Create a non-PA 1v1 direct chat between human u2 and team Global Agent a2 (agent:q)
  db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status,is_company_admin) VALUES('a2','agent:q','Agent Q','o1',?,'active',0)").run(now);
  db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,tool_allowlist_json,workspace_root,work_mode,created_at,updated_at) VALUES('q','o1','n','Agent Q','[\"task_graph\"]','/q','global',?,?)").run(now, now);
  db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,created_at) VALUES('dm-bob-q','Bob-Q DM','direct','private','company:default',?)").run(now);
  for (const id of ['u2', 'a2']) db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('dm-bob-q',?)").run(id);

  // Create a shared team group with u1, u2, and a2
  db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,created_at) VALUES('grp-rel','Release Group','group','public','company:default',?)").run(now);
  for (const id of ['u1', 'u2', 'a2']) db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('grp-rel',?)").run(id);

  // 1) In 1v1 human-Agent DM, Agent creating/applying a proposed card with omitted proposed_for_user_id auto-fills u2!
  const dmGraph = tasks.execute({ kind: 'agent', id: 'q', node_id: 'n' }, 'create', {
    conversation_id: 'dm-bob-q',
    title: '排查实验脚本超时',
    mode: 'dag',
    status: 'doing',
    request_key: 'dm-goal',
    operations: [
      { op: 'add_task', container_id: 'n1', client_ref: 'prop', title: '补充重试退避压测', description: '针对超时路径补一组指数退避压测脚本', status: 'proposed' },
      { op: 'add_task', container_id: 'n1', client_ref: 'stash', title: '稍后再看的归档脚本', status: 'backlog' },
      { op: 'add_task', container_id: 'n1', client_ref: 'done1', title: '定位日志瓶颈', status: 'done' },
    ],
  });
  const dmFull = tasks.execute({ kind: 'user', id: 'u2' }, 'get', { graph_id: dmGraph.graph_id, view: 'all' });
  const dmProposed = dmFull.nodes.find((n: any) => n.title === '补充重试退避压测');
  expect(dmProposed?.proposed_for_user_id).toBe('u2');

  const bobFocus = tasks.execute({ kind: 'user', id: 'u2' }, 'focus', { scope: 'mine' });
  expect(bobFocus.needs_you.map((n: any) => `${n.graph_id}:${n.node_id}`)).toContain(`${dmGraph.graph_id}:${dmProposed.id}`);
  expect(bobFocus.stashed.some((n: any) => n.graph_id === dmGraph.graph_id)).toBe(true);
  expect(bobFocus.goals.some((g: any) => g.graph_id === dmGraph.graph_id)).toBe(true);
  expect(bobFocus.completed_count).toBe(1);

  // u1 (bound admin of q, not in dm-bob-q) never sees Bob's 1v1 DM tasks in focus
  const aliceFocus = tasks.execute({ kind: 'user', id: 'u1' }, 'focus', { scope: 'mine' });
  expect(aliceFocus.needs_you.some((n: any) => n.graph_id === dmGraph.graph_id)).toBe(false);
  expect(aliceFocus.goals.some((g: any) => g.graph_id === dmGraph.graph_id)).toBe(false);

  // 2) In multi-user group, omitted proposed_for_user_id stays null; explicit non-member throws invalid_arguments
  const grpCard = tasks.execute({ kind: 'agent', id: 'q', node_id: 'n' }, 'create', {
    conversation_id: 'grp-rel',
    title: '发版回归检查',
    description: '核查跨源权限变更后的回归用例覆盖',
    status: 'proposed',
    request_key: 'grp-unassigned-prop',
  });
  const grpFull = tasks.execute({ kind: 'user', id: 'u1' }, 'get', { graph_id: grpCard.graph_id, view: 'all' });
  expect(grpFull.nodes[0]?.proposed_for_user_id ?? null).toBeNull();

  // Shared-group Agent-assigned card with explicit proposed_for_user_id stays in decider's Mine Stashed & Completed after Stash/Close
  const grpTargeted = tasks.execute({ kind: 'agent', id: 'q', node_id: 'n' }, 'create', {
    conversation_id: 'grp-rel',
    title: '发版第二波回归清单',
    description: '核查令牌轮换与会话吊销',
    status: 'proposed',
    assignee: { type: 'agent', id: 'q' },
    proposed_for_user_id: 'u2',
    request_key: 'grp-targeted-u2',
  });
  expect(tasks.execute({ kind: 'user', id: 'u2' }, 'focus', { scope: 'mine' }).needs_you.some((n: any) => n.graph_id === grpTargeted.graph_id)).toBe(true);

  const afterStash = tasks.execute({ kind: 'user', id: 'u2' }, 'apply', {
    graph_id: grpTargeted.graph_id,
    base_revision: grpTargeted.revision,
    request_key: 'stash-grp-u2',
    change_note: 'Stash for later',
    operations: [{ op: 'update_task', node_id: 'n1', patch: { status: 'backlog' } }],
  });
  const bobStashedFocus = tasks.execute({ kind: 'user', id: 'u2' }, 'focus', { scope: 'mine' });
  expect(bobStashedFocus.stashed.some((n: any) => n.graph_id === grpTargeted.graph_id)).toBe(true);
  expect(tasks.execute({ kind: 'user', id: 'u1' }, 'focus', { scope: 'mine' }).stashed.some((n: any) => n.graph_id === grpTargeted.graph_id)).toBe(false);

  tasks.execute({ kind: 'user', id: 'u2' }, 'apply', {
    graph_id: grpTargeted.graph_id,
    base_revision: afterStash.revision,
    request_key: 'close-grp-u2',
    change_note: 'Dismiss proposal',
    operations: [{ op: 'update_task', node_id: 'n1', patch: { status: 'closed' } }],
  });
  expect(tasks.execute({ kind: 'user', id: 'u2' }, 'focus', { scope: 'mine', section: 'completed' }).completed.some((n: any) => n.graph_id === grpTargeted.graph_id)).toBe(true);
  expect(tasks.execute({ kind: 'user', id: 'u1' }, 'focus', { scope: 'mine', section: 'completed' }).completed.some((n: any) => n.graph_id === grpTargeted.graph_id)).toBe(false);

  expect(() =>
    tasks.execute({ kind: 'agent', id: 'q', node_id: 'n' }, 'create', {
      conversation_id: 'dm-bob-q',
      title: '非法指向非会话成员 u1',
      description: '尝试指定不在私聊中的成员拍板',
      status: 'proposed',
      proposed_for_user_id: 'u1',
      request_key: 'bad-target-user',
    }),
  ).toThrow('proposed_for_user_id');

  // 3) Human-human 1v1 DM ('peer' has u1 + u2, zero agents) does NOT auto-fill or cross-contaminate needs_you
  const peerCard = tasks.execute({ kind: 'user', id: 'u1' }, 'create', {
    conversation_id: 'peer',
    title: '真人间私聊草稿',
    description: '真人之间私聊建的候选卡',
    status: 'proposed',
    request_key: 'peer-prop',
  });
  const peerFull = tasks.execute({ kind: 'user', id: 'u2' }, 'get', { graph_id: peerCard.graph_id, view: 'all' });
  expect(peerFull.nodes[0]?.proposed_for_user_id ?? null).toBeNull();
  const bobAfterPeer = tasks.execute({ kind: 'user', id: 'u2' }, 'focus', { scope: 'mine' });
  expect(bobAfterPeer.needs_you.some((n: any) => n.graph_id === peerCard.graph_id)).toBe(false);
});

it('expands mode-aware defaults in createAgent and avoids proactive_planning deadlocks on single_thread updates', async () => {
  const f = personalFixture();
  const { ctx, db } = f;
  connectFixtureGateway(f);

  const rawFeatures = featureDependencies.map(feat => ({
    ...feat,
    label_i18n: `feature.${feat.key}.label`,
    help_i18n: `feature.${feat.key}.help`,
  }));
  expect(featureOptions(rawFeatures, 'global').some(x => x.key === 'proactive_planning')).toBe(true);
  expect(featureOptions(rawFeatures, 'single_thread').some(x => x.key === 'proactive_planning')).toBe(false);

  const appliedPayloads: Record<string, any>[] = [];
  ctx.gateway.request = vi.fn(async (_nodeId: string, method: string, params: any) => {
    if (method === 'node.capabilities.resolve') {
      return {
        capabilities: {
          models: ['gpt-5.4'],
          skills: [
            { name: 'nano-proactive-care', default_on: true },
            { name: 'nano-memory', default_on: true },
          ],
          tools: [
            { name: 'task_graph', default_on: true },
            { name: 'schedule_create', default_on: true },
            { name: 'schedule_list', default_on: true },
            { name: 'schedule_update', default_on: true },
            { name: 'schedule_delete', default_on: true },
            { name: 'schedule_run', default_on: true },
            { name: 'schedule_history', default_on: true },
          ],
          features: rawFeatures,
          fixed_tools: [],
        },
      };
    }
    if (method === 'agent.config.operation.status') {
      return { operation_id: params.operation_id, status: 'pending' };
    }
    if (method === 'agent.create' || method === 'agent.config.apply') {
      appliedPayloads.push(params.agent);
      return {
        operation_id: params.operation_id,
        candidate_fingerprint: params.candidate_fingerprint,
        status: 'applied',
        agent: {
          ...params.agent,
          workspace_root: params.agent.workspace_root ?? `/tmp/${params.agent.agent_id}`,
          workspace_is_default: true,
        },
      };
    }
    return null;
  });

  const scheduleTools = ['schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'];
  const createdSingle = await createAgent(ctx, 'o1', 'n', {
    agent_id: 'helper-single',
    display_name: 'Single Helper',
    work_mode: 'single_thread',
    tool_allowlist: ['task_graph', ...scheduleTools],
  });
  expect(createdSingle.work_mode).toBe('single_thread');
  expect(createdSingle.features).not.toHaveProperty('proactive_planning');
  expect(createdSingle.skills).not.toContain('nano-proactive-care');
  expect(createdSingle.skills).toContain('nano-memory');

  const createdGlobal = await createAgent(ctx, 'o1', 'n', {
    agent_id: 'emp-global',
    display_name: 'Global Employee',
    work_mode: 'global',
    tool_allowlist: ['task_graph', ...scheduleTools],
  });
  expect(createdGlobal.work_mode).toBe('global');
  expect(createdGlobal.features.proactive_planning).toBe(true);
  expect(createdGlobal.skills).toContain('nano-proactive-care');

  // Turning off task_graph on single_thread succeeds without required_by_feature deadlock from proactive_planning
  const singleRecord = readAgentProfile(db, 'helper-single', 'o1')!;
  const withoutTaskGraphTools = createdSingle.tool_allowlist.filter(t => t !== 'task_graph');
  expect(withdrawsTask(singleRecord, { features: { ...createdSingle.features, task_graph: false }, tool_allowlist: withoutTaskGraphTools, work_mode: 'single_thread' })).toBe(true);
  const updatedSingle = await configurationOperations(ctx).update(
    singleRecord,
    {
      ...createdSingle,
      features: { ...createdSingle.features, task_graph: false },
      tool_allowlist: withoutTaskGraphTools,
      work_mode: 'single_thread',
    },
    'o1',
  );
  expect(updatedSingle.features.task_graph).toBe(false);

  // Explicitly enabling proactive_planning on single_thread is rejected by IM server capability validation
  const singleRecordAfter = readAgentProfile(db, 'helper-single', 'o1')!;
  await expect(
    configurationOperations(ctx).update(
      singleRecordAfter,
      {
        ...updatedSingle,
        features: { ...updatedSingle.features, task_graph: true, proactive_planning: true },
        tool_allowlist: [...withoutTaskGraphTools, 'task_graph'],
        work_mode: 'single_thread',
      },
      'o1',
    ),
  ).rejects.toThrow('Configuration is missing required capabilities');
});
