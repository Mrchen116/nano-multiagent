import { createHash } from 'node:crypto';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import sharp from 'sharp';
import { Gateway, type Connection } from '../src/gateway.js';
import { TaskGraphService } from '../src/task-graphs.js';
import { personalFixture } from './personal-fixture.js';

it('exempts pure-owner-private PA destinations (including >4096px PNG, GIF, PDF, and task_graph) while stripping local_path from public messages', async () => {
  const { ctx, db, service, principal, args } = personalFixture();
  const gateway = new Gateway(ctx);
  ctx.gateway.tasks = new TaskGraphService(db, ctx.messaging);
  gateway.nodes.set('n', principal as Connection);
  const folder = mkdtempSync(join(tmpdir(), 'pa-pure-owner-priv-'));
  ctx.dbPath = join(folder, 'im.db');
  mkdirSync(join(folder, 'message-images'));

  try {
    // Set PA `a` to `owner_only` first; create same-owner `owner_only` helper Agent `helper_priv`.
    db.prepare("UPDATE agent_profiles SET collaboration_scope='owner_only' WHERE agent_id='a'").run();
    db.prepare("INSERT OR REPLACE INTO pa_binding_scopes(binding_id,collaboration_scope) VALUES('binding','owner_only')").run();

    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('u_hpriv','agent:helper_priv','Private Helper','o1',datetime('now'),'active')").run();
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,collaboration_scope,created_at,updated_at) VALUES('helper_priv','o1','n','Private Helper','owner_only',datetime('now'),datetime('now'))").run();

    // Pure owner-private group: [Owner u1, PA a1, Private Helper u_hpriv]
    db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,owner_id,creator_id,created_at) VALUES('c_pure_priv','Owner Private Room','group','private','company:default','o1','u1',datetime('now'))").run();
    for (const uid of ['u1', 'a1', 'u_hpriv']) {
      db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('c_pure_priv',?)").run(uid);
      db.prepare("INSERT OR IGNORE INTO conversation_participation_history(conversation_id,user_id) VALUES('c_pure_priv',?)").run(uid);
    }

    const stage = (id: string, mime: string, name: string, bytes: Buffer, kind: 'images' | 'attachments') => {
      writeFileSync(join(folder, 'message-images', id), bytes);
      db.prepare('INSERT INTO message_images VALUES(?,?,?,?,?,?,?,?)')
        .run(id, 'chat', `stage:${id}`, createHash('sha256').update(bytes).digest('hex'), mime, name, bytes.length, id);
      return `/im/v1/conversations/chat/${kind}/${id}`;
    };

    // 1) >4096px PNG + GIF + PDF sent to pure-owner-private room bypasses decodePersonalImages AND disclosure review!
    const tallPng = await sharp({
      create: { width: 16, height: 4200, channels: 3, background: { r: 10, g: 20, b: 30 } },
    }).png().toBuffer();
    const gifBytes = Buffer.from('GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;', 'binary');
    const pdfBytes = Buffer.from('%PDF-1.4 pure owner private draft\n');

    const tallUrl = stage('tall-png', 'image/png', 'tall-board.png', tallPng, 'images');
    const gifUrl = stage('anim-gif', 'image/gif', 'demo.gif', gifBytes, 'images');
    const pdfUrl = stage('priv-pdf', 'application/pdf', 'private-notes.pdf', pdfBytes, 'attachments');

    const res = await service.actions.prepareChecked(principal, {
      ...args,
      request_key: 'pure-priv-media',
      conversation_id: 'c_pure_priv',
      content: 'Syncing private draft materials',
      attachments: [
        { url: tallUrl, local_path: '/Users/alice/Desktop/tall-board.png' },
        { url: gifUrl, local_path: '/Users/alice/Desktop/demo.gif' },
        { url: pdfUrl, local_path: '/Users/alice/Documents/private-notes.pdf' },
      ],
    });
    expect(res).toMatchObject({ state: 'confirmed', conversation_id: 'c_pure_priv' });
    expect(typeof res.message_id).toBe('string');

    // Verify idempotent retry returns exact same confirmed message_id without creating prepared rows.
    const retry = await service.actions.prepareChecked(principal, {
      ...args,
      request_key: 'pure-priv-media',
      conversation_id: 'c_pure_priv',
      content: 'Syncing private draft materials',
      attachments: [
        { url: tallUrl, local_path: '/Users/alice/Desktop/tall-board.png' },
        { url: gifUrl, local_path: '/Users/alice/Desktop/demo.gif' },
        { url: pdfUrl, local_path: '/Users/alice/Documents/private-notes.pdf' },
      ],
    });
    expect(retry).toEqual(res);
    expect(db.prepare("SELECT count(*) AS n FROM pa_operations WHERE state='prepared'").get()).toEqual({ n: 0 });

    // Stored public message attachments MUST strip local_path!
    const storedMsg = ctx.messaging.message(res.message_id);
    expect(storedMsg.attachments).toHaveLength(3);
    for (const att of storedMsg.attachments) {
      expect(att).not.toHaveProperty('local_path');
      expect(att.url).toMatch(/^\/im\/v1\/conversations\/c_pure_priv\/(images|attachments)\//);
    }

    // 2) Even when PA itself has collaboration_scope='team', [PA(team), Private Helper(owner_only)] is still pure-owner-private!
    db.prepare("UPDATE agent_profiles SET collaboration_scope='team' WHERE agent_id='a'").run();
    db.prepare("UPDATE pa_binding_scopes SET collaboration_scope='team' WHERE binding_id='binding'").run();
    const taskRes = await service.actions.prepareChecked(principal, {
      ...args,
      request_key: 'pure-priv-task-create',
      task: {
        action: 'create',
        arguments: {
          conversation_id: 'c_pure_priv',
          title: 'Private Helper Plan',
          mode: 'dag',
          request_key: 'pure-priv-task-create',
        },
      },
    });
    expect(taskRes).toMatchObject({ state: 'confirmed', conversation_id: 'c_pure_priv', result: { revision: 1 } });
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

it('requires PA disclosure review when messaging same-owner project/team Agents, projects downstream_exposure & PDF matched_sources, and invalidates on group member change', async () => {
  const { ctx, db, service, principal, args } = personalFixture();
  ctx.gateway.groupReply = vi.fn();
  const folder = mkdtempSync(join(tmpdir(), 'pa-cross-circle-'));
  ctx.dbPath = join(folder, 'im.db');
  mkdirSync(join(folder, 'message-images'));

  try {
    // PA is `owner_only`: still allowed to reach same-owner `project` and `team` Agents (`ownerOrInternalDestination = true`),
    // while blocked from external colleague conversations (`403 collaboration_scope_restricted`).
    db.prepare("UPDATE agent_profiles SET collaboration_scope='owner_only' WHERE agent_id='a'").run();
    db.prepare("INSERT OR REPLACE INTO pa_binding_scopes(binding_id,collaboration_scope) VALUES('binding','owner_only')").run();

    await expect(service.actions.prepareChecked(principal, {
      ...args,
      request_key: 'blocked-external-peer',
      conversation_id: 'peer',
      content: 'Cannot send to external colleague under owner_only',
    })).rejects.toMatchObject({ statusCode: 403, detail: expect.objectContaining({ code: 'collaboration_scope_restricted' }) });

    // Create external humans u2 (Bob, already in fixture) and u3 (Charlie), plus same-owner `project` Agent `proj_bot` and `team` Agent `team_bot`.
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('u3','charlie','Charlie','o3',datetime('now'),'active')").run();
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('u_proj','agent:proj_bot','Proj Bot','o1',datetime('now'),'active')").run();
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,collaboration_scope,work_mode,created_at,updated_at) VALUES('proj_bot','o1','n','Proj Bot','project','global',datetime('now'),datetime('now'))").run();
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('u_team','agent:team_bot','Team Bot','o1',datetime('now'),'active')").run();
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,collaboration_scope,work_mode,created_at,updated_at) VALUES('team_bot','o1','n','Team Bot','team','global',datetime('now'),datetime('now'))").run();

    // Put `proj_bot` in private project group `c_alpha_grp` with Owner `u1` and Colleague `u2` (Bob).
    db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,owner_id,creator_id,created_at) VALUES('c_alpha_grp','Alpha Project','group','private','company:default','o1','u1',datetime('now'))").run();
    for (const uid of ['u1', 'u2', 'u_proj']) {
      db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('c_alpha_grp',?)").run(uid);
    }

    // Internal DM between PA `a1` and same-owner `proj_bot` (`u_proj`) + Owner `u1`.
    db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,owner_id,creator_id,created_at) VALUES('c_pa_to_proj','PA <-> Proj Bot','group','private','company:default','o1','u1',datetime('now'))").run();
    for (const uid of ['u1', 'a1', 'u_proj']) {
      db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('c_pa_to_proj',?)").run(uid);
      db.prepare("INSERT OR IGNORE INTO conversation_participation_history(conversation_id,user_id) VALUES('c_pa_to_proj',?)").run(uid);
    }

    // Internal DM between PA `a1` and same-owner `team_bot` (`u_team`) + Owner `u1`.
    db.prepare("INSERT INTO conversations(id,title,type,visibility,space_id,owner_id,creator_id,created_at) VALUES('c_pa_to_team','PA <-> Team Bot','group','private','company:default','o1','u1',datetime('now'))").run();
    for (const uid of ['u1', 'a1', 'u_team']) {
      db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('c_pa_to_team',?)").run(uid);
      db.prepare("INSERT OR IGNORE INTO conversation_participation_history(conversation_id,user_id) VALUES('c_pa_to_team',?)").run(uid);
    }

    // Seed an inbound owner message in `chat` carrying `Spec.pdf` so `matched_sources` links sha256 -> owner's message!
    const pdfBytes = Buffer.from('%PDF-1.4 Approved Alpha Spec v2\n');
    const pdfSha = createHash('sha256').update(pdfBytes).digest('hex');
    writeFileSync(join(folder, 'message-images', 'inbound-pdf'), pdfBytes);
    db.prepare('INSERT INTO message_images VALUES(?,?,?,?,?,?,?,?)')
      .run('inbound-pdf', 'chat', 'owner-upload-1', pdfSha, 'application/pdf', 'Spec.pdf', pdfBytes.length, 'inbound-pdf');
    const ownerMsg = ctx.messaging.insertMessage(
      'chat',
      'u1',
      'user',
      '把这份 Spec.pdf 发给 Proj Bot 处理',
      [{ url: '/im/v1/conversations/chat/attachments/inbound-pdf', content_type: 'application/pdf', file_name: 'Spec.pdf' }],
    );

    // Stage local downloaded copy in `chat` (simulating download_attachment -> send_message(local_files=[...])).
    writeFileSync(join(folder, 'message-images', 'staged-pdf'), pdfBytes);
    db.prepare('INSERT INTO message_images VALUES(?,?,?,?,?,?,?,?)')
      .run('staged-pdf', 'chat', 'pa-stage-1', pdfSha, 'application/pdf', 'Spec.pdf', pdfBytes.length, 'staged-pdf');

    // 1) Sending to `c_pa_to_proj` MUST NOT bypass review (`state: 'prepared'`) and MUST include downstream_exposure + matched_sources!
    const projProposal = await service.actions.prepareChecked(principal, {
      ...args,
      request_key: 'pa-to-proj-pdf',
      conversation_id: 'c_pa_to_proj',
      content: '转发主人授权的 Spec.pdf',
      attachments: [{
        url: '/im/v1/conversations/chat/attachments/staged-pdf',
        local_path: '/Users/alice/.nano-downloads/a_123456-Spec.pdf',
      }],
    });
    expect(projProposal.state).toBe('prepared');
    const projMember = projProposal.evidence.recipient.members.find((m: any) => m.id === 'proj_bot');
    expect(projMember).toMatchObject({
      collaboration_scope: 'project',
      downstream_exposure: {
        scope: 'shared_private_group_members_via_project_agent',
        shared_private_group_members: [{ id: 'u2', name: 'u2' }],
      },
    });
    expect(projProposal.evidence.payload.attachment_snapshots[0]).toMatchObject({
      file: true,
      content_review: 'unreadable',
      sha256: pdfSha,
      local_path: '/Users/alice/.nano-downloads/a_123456-Spec.pdf',
      matched_sources: [
        expect.objectContaining({
          message_id: ownerMsg.id,
          conversation_id: 'chat',
          sender_user_id: 'u1',
          is_owner: true,
          file_name: 'Spec.pdf',
        }),
      ],
    });
    expect(projProposal.evidence.payload.attachments[0]).not.toHaveProperty('local_path');

    // 2) If Charlie (`u3`) joins `c_alpha_grp` BEFORE commit, downstream exposure changed -> commit fails with `audience_changed`!
    const allowVerdict = service.actions.review(principal, {
      ...args,
      proposal_ref: projProposal.proposal_ref,
      payload_digest: projProposal.payload_digest,
      evidence_digest: projProposal.evidence_digest,
      verdict: { decision: 'allow', reason: 'Owner explicitly authorized sending Spec.pdf to Proj Bot' },
    });
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('c_alpha_grp','u3')").run();
    const staleCommit = await service.actions.commitChecked(principal, {
      ...args,
      proposal_ref: projProposal.proposal_ref,
      verdict_ref: allowVerdict.verdict_ref,
    });
    expect(staleCommit).toMatchObject({ state: 'not_sent', changed_reason: expect.stringContaining('audience_changed') });

    // Remove Charlie so audience matches again (or re-prepare with updated audience [Bob, Charlie]) and commit cleanly!
    const refreshed = await service.actions.prepareChecked(principal, {
      ...args,
      request_key: 'pa-to-proj-pdf-v2',
      conversation_id: 'c_pa_to_proj',
      content: '转发主人授权的 Spec.pdf',
      attachments: [{
        url: '/im/v1/conversations/chat/attachments/staged-pdf',
        local_path: '/Users/alice/.nano-downloads/a_123456-Spec.pdf',
      }],
    });
    const refreshedProjMember = refreshed.evidence.recipient.members.find((m: any) => m.id === 'proj_bot');
    expect(refreshedProjMember.downstream_exposure.shared_private_group_members).toEqual([
      { id: 'u2', name: 'u2' },
      { id: 'u3', name: 'Charlie' },
    ]);
    const refreshedVerdict = service.actions.review(principal, {
      ...args,
      proposal_ref: refreshed.proposal_ref,
      payload_digest: refreshed.payload_digest,
      evidence_digest: refreshed.evidence_digest,
      verdict: { decision: 'allow', reason: 'Owner authorized for Alpha Project members' },
    });
    const committed = await service.actions.commitChecked(principal, {
      ...args,
      proposal_ref: refreshed.proposal_ref,
      verdict_ref: refreshedVerdict.verdict_ref,
    });
    expect(committed.state).toBe('confirmed');
    const deliveredMsg = ctx.messaging.message(committed.message_id);
    expect(deliveredMsg.attachments[0]).toMatchObject({
      content_type: 'application/pdf',
      file_name: 'Spec.pdf',
    });
    expect(deliveredMsg.attachments[0]).not.toHaveProperty('local_path');
    expect(deliveredMsg.attachments[0]!.url).toMatch(/^\/im\/v1\/conversations\/c_pa_to_proj\/attachments\//);

    // 3) Sending to `c_pa_to_team` projects `eligible_company_members_via_team_agent`!
    const teamProposal = await service.actions.prepareChecked(principal, {
      ...args,
      request_key: 'pa-to-team-msg',
      conversation_id: 'c_pa_to_team',
      content: 'Syncing public summary to Team Bot',
    });
    expect(teamProposal.state).toBe('prepared');
    expect(teamProposal.evidence.recipient.members.find((m: any) => m.id === 'team_bot')).toMatchObject({
      collaboration_scope: 'team',
      downstream_exposure: { scope: 'eligible_company_members_via_team_agent' },
    });
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
