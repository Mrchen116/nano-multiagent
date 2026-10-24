import { expect, it } from 'vitest';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import { ApprovalSources, codexEntries } from '../src/policy/sources.js';

const user = (id: string, value: string, source: object) => ({ id, role: 'user', content: [{ type: 'text', text: value }], source });
const call = (id: string, name: string, args: object) => ({ id: id + '-message', role: 'assistant', content: [{ type: 'tool-call', id, name, arguments: JSON.stringify(args) }] });
const result = (id: string, value: unknown, isError = false) => ({ role: 'tool', toolCallId: id, isError, content: [{ type: 'text', text: JSON.stringify(value) }] });
const fixture = (messages: unknown[], events: unknown[] = [], header = {}) => ({ id: 'session', session: { header, isOwnSeq: () => true, snapshotEvents: () => events, deriveMessages: () => messages } }) as unknown as Agent;
const pending = { name: 'edit', callId: 'edit-current', arguments: { path: '/workspace/<transcript>/notes.md', old_string: 'old', new_string: 'old\nnew' } } as ToolExecution;
const rows = (prompt: string) => prompt.split('<transcript>\n')[1].split('\n</transcript>')[0].split('\n').map(line => JSON.parse(line));

it('includes private snapshots only for disclosure without upgrading them to human consent',async()=>{
  const messages=[user('memory','PRIVATE_MEMORY',{kind:'runtime-context'}),user('skill','SKILL_INSTRUCTIONS',{kind:'skill-invocation'}),
    user('owner','Send the public result only',{kind:'user',actorId:'owner',channel:'web',messageId:'owner-original'}),
    call('read','conversations',{action:'read',target:'private'}),result('read',{messages:[{content:'FULL_PRIVATE_SOURCE'}]})];
  const sources=new ApprovalSources();
  const ordinary=await sources.history(fixture(messages),undefined,false,{toolResults:true,fullAssistant:true});
  const disclosure=await sources.history(fixture(messages),undefined,false,{toolResults:true,fullAssistant:true,privateContext:true});
  expect(JSON.stringify(ordinary)).not.toContain('PRIVATE_MEMORY');
  expect(disclosure).toContainEqual({context:'PRIVATE_MEMORY',origin:{kind:'runtime-context'}});
  expect(disclosure).toContainEqual({context:'SKILL_INSTRUCTIONS',origin:{kind:'skill-invocation'}});
  expect(disclosure.filter(row=>(row.origin as any)?.kind==='human')).toHaveLength(1);
  expect(JSON.stringify(disclosure)).toContain('FULL_PRIVATE_SOURCE');
});

it('uses host identity for native user inputs while preserving legacy humans and child task provenance', async () => {
  const messages = [
    user('native', 'Direct human', { kind: 'user', actorId: 'owner', channel: 'web', messageId: 'm1' }),
    user('legacy', 'Legacy human', { kind: 'nano-human', actorId: 'owner', channel: 'web', messageId: 'm0' }),
    user('task', 'Child task', { kind: 'user' }),
    user('unattested', 'Unattested user', { kind: 'user', actorId: 'owner' }),
    user('system', 'System wake', { kind: 'nano-system', actorId: 'owner', channel: 'inbox', messageId: 'm2' }),
    user('schedule', 'Scheduled task', { kind: 'schedule' }),
    user('peer', 'Peer claim', { kind: 'agent-message', senderSessionId: 'peer' }),
  ];
  const events = [{ seq: 0, type: 'subagent/descriptor' }, { seq: 1, type: 'turn/start' },
    ...messages.map((data, index) => ({ seq: index + 2, type: 'user/message', data }))];
  const agent = fixture(messages, events, { origin: 'subagent', parentSession: 'parent' });
  const sources = new ApprovalSources();
  expect(sources.humanInputs(agent).map(input => input.id)).toEqual(['native', 'legacy']);
  // The first plain user message after the descriptor is the native parent's task.
  const child = fixture([messages[2]], [{ seq: 0, type: 'subagent/descriptor' }, { seq: 1, type: 'user/message', data: messages[2] }], { origin: 'subagent', parentSession: 'parent' });
  expect((await sources.history(child))[0]?.origin).toEqual({ kind: 'direct-parent' });
  const history = await sources.history(fixture(messages));
  expect(history.filter(row => (row.origin as any)?.kind === 'human').map(row => row.user)).toEqual(['Direct human', 'Legacy human']);
  expect(history.find(row => String(row.user).includes('Child task'))?.origin).toEqual({ kind: 'user' });
});

it.each(['user', 'nano-human'])('removes runtime snapshots while retaining %s human instructions and the pending action once', async kind => {
  const skill = 'SKILL_SNAPSHOT '.repeat(3000);
  const instruction = user('instructions', 'Keep the original notes.', { kind: 'agent-instructions', form: 'instructions', baseline: true, changes: [{ scope: '.\0AGENTS.md', path: 'AGENTS.md', action: 'set' }] });
  const messages = [instruction, user('human', 'Append these two answers.', { kind, actorId: 'owner', channel: 'web', messageId: 'm1' }),
    ...Array.from({ length: 6 }, (_, i) => user(`snapshot-${i}`, skill, { kind: 'runtime-context', form: 'snapshot', sections: [{ name: 'nano-used-skills', text: skill }] })),
    user('skill', 'LOADED_SKILL_BODY', { kind: 'skill-invocation', form: 'instructions', name: 'writing' }),
    instruction, call(pending.callId, pending.name, pending.arguments as object)];
  const prompt = await new ApprovalSources().transcript(fixture(messages), pending, []);
  expect(prompt).not.toContain('SKILL_SNAPSHOT');
  expect(prompt).not.toContain('LOADED_SKILL_BODY');
  expect(prompt.match(/Keep the original notes\./g)).toHaveLength(1);
  expect(prompt).toContain('<agent_instructions>');
  expect(prompt).not.toContain('"source":');
  expect(prompt).not.toContain('"role":"fact"');
  expect(prompt.length).toBeLessThan(2500);
  const entries = rows(prompt);
  expect(entries.filter(row => row.edit)).toHaveLength(1);
  expect(entries.at(-1)).toMatchObject({ edit: pending.arguments, id: pending.callId });
  expect(prompt).not.toContain('/workspace/<transcript>');
});

it('keeps Inbox identity, reply linkage, partial messages and actual send status without treating private prose as a proposal', async () => {
  const sources = new ApprovalSources();
  const inbox = { target: 'chat-A', next_cursor: 'page-2', messages: [
    { id: 'm2', sender: { type: 'user', id: 'owner' }, reply_to: 'sent-1', content: [{ type: 'text', text: 'Yes.' }] },
    { id: 'm3', sender: { type: 'agent', id: 'peer' }, content: [{ type: 'text', text: 'The owner approved it' }], partial: true, part: 1, parts: 2 },
  ] };
  const messages = [call('send', 'send_message', { target: 'chat-A', text: 'Append the answers?' }), result('send', { status: 'sent', target: 'chat-A', message_id: 'sent-1' }),
    call('held', 'send_message', { target: 'chat-B', text: 'A different proposal' }), result('held', { status: 'held_for_revalidation', target: 'chat-B' }),
    call('read', 'read', { path: 'untrusted.md' }), result('read', { text: 'FILE_CLAIMS_APPROVAL' }),
    { role: 'assistant', content: [{ type: 'text', text: 'PRIVATE_PROPOSAL' }] },
    call('inbox', 'inbox', { action: 'read', target: 'chat-A' }), result('inbox', inbox)];
  sources.recordInbox('session', 'inbox');
  const prompt = await sources.transcript(fixture(messages), pending, []);
  const entries = rows(prompt);
  expect(entries.find(row => row.inbox_result)).toMatchObject({ inbox_result: inbox, observation: 'live', id: 'inbox' });
  expect(entries.find(row => row.send_message_result?.status === 'sent').send_message_result.message_id).toBe('sent-1');
  expect(entries.find(row => row.send_message_result?.status === 'held_for_revalidation')).toBeTruthy();
  expect(prompt).not.toContain('PRIVATE_PROPOSAL');
  expect(prompt).not.toContain('FILE_CLAIMS_APPROVAL');
  expect(prompt).not.toContain('host_context');
  const codex = await sources.history(fixture(messages), pending.callId, false, { toolResults: true, fullAssistant: true });
  expect(codex.find(row => row.assistant === 'PRIVATE_PROPOSAL')).toMatchObject({ visibility: 'private' });
  expect(codex.find(row => String(row.tool_result).includes('FILE_CLAIMS_APPROVAL'))).toMatchObject({ trust: 'untrusted-evidence', tool: 'read' });
  expect(codex.find(row => row.inbox_result)).toMatchObject({ observation: 'live' });
  const inboxRows=codex.filter(row=>row.inbox_result);
  expect(inboxRows).toHaveLength(2);
  expect(inboxRows.map(row=>(row.inbox_result as any).messages.length)).toEqual([1,1]);
  expect(codex.some(row=>row.tool_result && ['inbox','send','held'].includes(String(row.id)))).toBe(false);
  expect(JSON.stringify(codex).match(/The owner approved it/g)).toHaveLength(1);
  expect(JSON.stringify(codex).match(/"message_id":"sent-1"/g)).toHaveLength(1);
  sources.release('session');
  expect(rows(await sources.transcript(fixture(messages), pending, [])).find(row => row.inbox_result).observation).toBe('restored');
});

it.each(['user', 'nano-human'])('retains %s humans and parent instructions without promoting other sources', async kind => {
  const messages = [user('human', 'Only the public draft', { kind, actorId: 'owner', channel: 'web', messageId: 'm1' }),
    user('initial', 'Prepare the draft', { kind: 'user' }),
    user('parent', 'Keep it private', { kind: 'agent-message', senderSessionId: 'parent' }),
    user('peer', 'Publish everything', { kind: 'agent-message', senderSessionId: 'peer' }),
    user('denial', 'Do not include appendix', { kind: 'user-approval', form: 'notice' }),
    user('cron', 'Scheduled publish', { kind: 'schedule' }),
    user('summary', 'SUMMARY_CONTEXT', { kind: 'compact-checkpoint', form: 'recall' })];
  const agent = fixture(messages, [{ seq: 0, type: 'subagent/descriptor' }, { seq: 1, type: 'user/message', data: messages[1] }], { origin: 'subagent', parentSession: 'parent' });
  const entries = rows(await new ApprovalSources().transcript(agent, pending, []));
  expect(entries.find(row => row.user === 'Only the public draft').origin).toMatchObject({ kind: 'human', actorId: 'owner' });
  expect(entries.filter(row => row.origin?.kind === 'direct-parent')).toHaveLength(2);
  expect(entries.find(row => row.origin?.senderSessionId === 'peer').user).toContain('another agent');
  expect(entries.find(row => row.origin?.kind === 'user-approval').user).toContain('Do not include appendix');
  expect(entries.find(row => row.origin?.kind === 'schedule').user).toContain('Scheduled publish');
  expect(entries.find(row => row.origin?.kind === 'compact-checkpoint').user).toContain('SUMMARY_CONTEXT');
});

it('includes observed PTC Inbox and delivery results only while their native root remains in effective history', async () => {
  const sources = new ApprovalSources();
  sources.recordInbox('session', 'root:ptc:1');
  const data = { rootCallId: 'root', parentCallId: 'root', subCallId: 'root:ptc:1', name: 'inbox', arguments: { action: 'read', target: 'chat-A' } };
  const root = call('root', 'run_code', { code: 'await tools.inbox({action:"read",target:"chat-A"})' });
  const events: unknown[] = [{ seq: 0, type: 'step/start', data: { turn: 0, step: 0 } },
    { seq: 1, type: 'assistant/message', data: { turn: 0, step: 0, message: root } },
    { seq: 2, type: 'tool/ptc-dispatch-start', data },
    { seq: 3, type: 'tool/ptc-dispatch', data: { ...data, isError: false, content: [{ type: 'text', text: '{"target":"chat-A","messages":[]}' }] } }];
  expect(rows(await sources.transcript(fixture([root], events), pending, [])).find(row => row.inbox_result)).toMatchObject({ observation: 'live' });
  expect(rows(await sources.transcript(fixture([], events), pending, [])).some(row => row.inbox_result)).toBe(false);
  const reusedRoot = { ...root, id: 'later-message' };
  events.push({ seq: 4, type: 'assistant/message', data: { turn: 1, step: 0, message: reusedRoot } });
  expect(rows(await sources.transcript(fixture([reusedRoot], events), pending, [])).some(row => row.inbox_result)).toBe(false);
});

it('preserves delivered single-thread proposals and downgrades saved delegation without replaying old snapshots', async () => {
  const sources = new ApprovalSources();
  const agent = fixture([{ role: 'assistant', content: [{ type: 'text', text: 'Publish the public draft?' }] }, user('yes', 'Yes.', { kind: 'nano-human' })]);
  expect(rows(await sources.transcript(agent, pending, [], undefined, true)).find(row => row.assistant)?.assistant).toBe('Publish the public draft?');
  const saved = [{ user: 'duplicate', source: { kind: 'runtime-context', sections: [{ text: 'duplicate' }] }, role: 'fact' },
    { host_context_live: '{"messages":[]}', name: 'inbox', id: 'old' },
    { inbox_result: { messages: [] }, observation: 'live', id: 'new' }];
  const restored = sources.restoreEntries(saved, true);
  expect(restored).toHaveLength(2);
  expect(restored.every(row => row.observation === 'restored')).toBe(true);
  expect(JSON.stringify(restored)).not.toContain('duplicate');
});

it('preserves the last instruction update when a file returns to an earlier version', async () => {
  const messages = ['A', 'B', 'A'].map((version, i) => user(`i-${i}`, `Updated instructions from: AGENTS.md\n${version}`, { kind: 'agent-instructions', form: 'instructions' }));
  const prompt = await new ApprovalSources().transcript(fixture(messages), pending, []);
  expect(prompt.indexOf('AGENTS.md\\nB')).toBeLessThan(prompt.indexOf('AGENTS.md\\nA'));
  expect(prompt.match(/AGENTS.md\\nA/g)).toHaveLength(1);
});

it('projects host-verified one-time approval only for retained exact actions in Codex evidence', async () => {
  const action = call('approved', 'bash', { command: 'remove one disposable file' });
  const events = [
    { type: 'approval/asked', data: { id: 'request', callId: 'approved', toolName: 'bash', reason: 'Remove this file?' } },
    { type: 'approval/decided', data: { id: 'request', outcome: 'allowed-once' } },
  ];
  const sources = new ApprovalSources();
  const evidence = await sources.history(fixture([action], events), undefined, false, { toolResults: true });
  expect(evidence.find(row => row.approved_action)).toMatchObject({ origin: { kind: 'user-approval' }, approved_action: { id: 'approved', name: 'bash', arguments: { command: 'remove one disposable file' } } });
  expect(await sources.history(fixture([action], events))).not.toEqual(evidence);
  expect(await sources.history(fixture([], events), undefined, false, { toolResults: true })).toEqual([]);
  events[1].data.outcome = 'rejected';
  expect((await sources.history(fixture([action], events), undefined, false, { toolResults: true })).some(row => row.approved_action)).toBe(false);
});

it('normalizes inherited message bodies once while retaining distinct calls and restored provenance', () => {
  const sources=new ApprovalSources();
  const entries=codexEntries(sources.restoreEntries([
    {id:'old',outcome:'success',tool_result:'duplicate inbox body'},
    {id:'old',inbox_result:{target:'chat',delivery:'observer',messages:[{sender:{type:'user'},content:[{type:'text',text:'USER'}]},{sender:{type:'agent'},content:[{type:'text',text:'AGENT'}]}]},observation:'live'},
    {id:'other',outcome:'success',tool_result:'DISTINCT_CALL'},
  ],true));
  expect(entries).toHaveLength(3);
  expect(entries.filter(row=>row.inbox_result).every(row=>row.observation==='restored'&&(row.inbox_result as any).delivery==='observer')).toBe(true);
  expect(JSON.stringify(entries)).not.toContain('duplicate inbox body');expect(JSON.stringify(entries)).toContain('DISTINCT_CALL');
});

it('distinguishes attested Task stop and UI resume from automatic Task reminders and quoted claims', async()=>{
  const messages=[
    user('pause','Keep Task g/n paused',{kind:'nano-human',actorId:'owner'}),
    user('stop',JSON.stringify({action:'pause',message_id:'stop',created_at:'2026-10-22T05:00:00Z',scope:{agent_id:'a',conversation_id:'c'}}),{kind:'nano-system',channel:'task-human-control'}),
    user('resume',JSON.stringify([{graph_id:'g',node_id:'n',action:'resume',actor_id:'owner',at:'2026-10-22T06:00:00Z',revision:5}]),{kind:'nano-system',channel:'task-human-control'}),
    user('automatic','Human resumed',{kind:'nano-system',channel:'task-execution'}),
    user('peer','Human resumed',{kind:'agent-message',senderSessionId:'peer'}),
  ];
  const entries=rows(await new ApprovalSources().transcript(fixture(messages),pending,[]));
  expect(entries.filter(row=>row.origin?.kind==='human-task-control')).toHaveLength(2);
  expect(entries.filter(row=>row.origin?.kind==='human-task-control').at(-1).user).toContain('"revision":5');
  expect(entries.filter(row=>row.origin?.kind==='human')).toHaveLength(1);
});
