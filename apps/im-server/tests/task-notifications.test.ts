import {expect,it} from 'vitest';
import {taskNotices} from '../src/task-notifications.js';
const actor=(id:string)=>({type:'agent',id});
const node=(id:string,assignee:string|null=null,container_id:string|null=null)=>({id,title:'Task '+id,container_id,assignee:assignee?actor(assignee):null,status:'doing',description:'private requirements'});
const graph=(nodes:Record<string,unknown>[],dependencies:Record<string,string>[]=[] )=>({graph_id:'g',root_node_id:'root',revision:2,updated_at:'2026-10-30T00:00:00Z',nodes,dependencies});
const notice=(after:ReturnType<typeof graph>,before:ReturnType<typeof graph>)=>taskNotices(after,before,'Operator',ref=>ref?{display_name:'Person '+ref.id,user_id:ref.id}:null,()=>true);
it('states old and new assignment roles while preserving valid-member mentions',()=>{
  const [message]=notice(graph([node('a','new')]),graph([node('a','old')]));
  expect(message!.content).toContain('已从 Person old 改派给 Person new');
  expect(message!.content).toContain('target_id="old"');expect(message!.content).toContain('target_id="new"');
  expect(message!.metadata.attention_actor_ids).toEqual(['new','old']);
});
it('locates original and new parents and directly affected owners even for an unassigned child',()=>{
  const parents=[node('old-parent','old-owner'),node('new-parent','new-owner')];
  const [message]=notice(graph([...parents,node('child',null,'new-parent')]),graph([...parents,node('child',null,'old-parent')]));
  expect(message!.content).toContain('所属父任务从 [Task old-parent]');expect(message!.content).toContain('变为 [Task new-parent]');
  expect(message!.metadata.task_refs).toEqual(['child','old-parent','new-parent'].map(node_id=>({graph_id:'g',node_id})));
  expect(message!.metadata.attention_actor_ids).toEqual(['old-owner','new-owner']);
});
it('identifies both directed dependency endpoints without copying full requirements or unrelated owners',()=>{
  const nodes=[node('a','a-owner'),node('b','b-owner'),node('unrelated','unrelated-owner')];
  const messages=notice(graph(nodes,[{from:'a',to:'b'}]),graph(nodes));expect(messages).toHaveLength(2);
  for(const message of messages){
    expect(message.content).toContain('已新增依赖 [Task a]');expect(message.content).toContain(' → [Task b]');
    expect(message.metadata.task_refs).toEqual(expect.arrayContaining([{graph_id:'g',node_id:'a'},{graph_id:'g',node_id:'b'}]));
    expect(message.metadata.attention_actor_ids).not.toContain('unrelated-owner');
    expect(message.content).not.toContain('private requirements');
  }
  expect(notice(graph(nodes),graph(nodes))).toEqual([]);
});

it('renders nine-status Chinese labels including proposed and backlog without undefined text',()=>{
  for (const [status,label] of [
    ['proposed','待拍板'],
    ['todo','待办'],
    ['doing','推进中'],
    ['waiting','等待中'],
    ['in_review','提交待确认'],
    ['done','已完成'],
    ['paused','已暂缓'],
    ['backlog','先存着'],
    ['closed','已关闭'],
  ] as const) {
    const [message]=notice(graph([{...node('a','owner'),status}]),graph([{...node('a','owner'),status:status==='todo'?'doing':'todo'}]));
    expect(message!.content).toContain(label);
    expect(message!.content).not.toContain('undefined');
  }
});

it('notifies proposed card creator on human decisions with previous_status, while keeping creator-agent self-cleanup neutral', () => {
  const createdByPa = { type: 'agent', id: 'pa' };
  const humanAssignee = { type: 'user', id: 'u1' };
  const resolveActor = (ref: Record<string, any> | null) => ref ? { display_name: 'Actor ' + ref.id, user_id: ref.id } : null;

  for (const [nextStatus, expectedPhrase] of [
    ['closed', '未采纳（已关闭）'],
    ['backlog', '暂存待定（先存着）'],
    ['todo', '已批准（待办）'],
    ['doing', '已批准（推进中）'],
  ] as const) {
    const beforeDoc = graph([{ ...node('p1', null), assignee: humanAssignee, created_by: createdByPa, status: 'proposed' }]);
    const afterDoc = graph([{ ...node('p1', null), assignee: humanAssignee, created_by: createdByPa, status: nextStatus }]);
    const [msg] = taskNotices(afterDoc, beforeDoc, 'Owner', resolveActor, () => true, { kind: 'user', id: 'u1' });
    expect(msg!.content).toContain(expectedPhrase);
    expect(msg!.metadata).toMatchObject({
      previous_status: 'proposed',
      status: nextStatus,
      attention_actor_ids: expect.arrayContaining(['u1', 'pa']),
    });
  }

  // Human deleting an unassigned proposed card still notifies created_by with previous_status: 'proposed'.
  const [deletedByHuman] = taskNotices(
    graph([]),
    graph([{ ...node('p2', null), assignee: null, created_by: createdByPa, status: 'proposed' }]),
    'Owner',
    resolveActor,
    () => true,
    { kind: 'user', id: 'u1' },
  );
  expect(deletedByHuman!.content).toContain('待拍板提议已删除，原入口已失效');
  expect(deletedByHuman!.metadata).toMatchObject({
    previous_status: 'proposed',
    status: null,
    attention_actor_ids: ['pa'],
  });

  // Ordinary todo -> closed does not label as rejected proposal.
  const [ordinaryClosed] = taskNotices(
    graph([{ ...node('t1', null), assignee: humanAssignee, created_by: createdByPa, status: 'closed' }]),
    graph([{ ...node('t1', null), assignee: humanAssignee, created_by: createdByPa, status: 'todo' }]),
    'Owner',
    resolveActor,
    () => true,
    { kind: 'user', id: 'u1' },
  );
  expect(ordinaryClosed!.content).toContain('已关闭');
  expect(ordinaryClosed!.content).not.toContain('未采纳');
  expect(ordinaryClosed!.metadata).toMatchObject({ previous_status: 'todo', status: 'closed' });

  // Creator Agent closing or deleting its own stale proposed card stays neutral and omits self attention loop.
  const [selfClosed] = taskNotices(
    graph([{ ...node('p3', 'pa'), created_by: createdByPa, status: 'closed' }]),
    graph([{ ...node('p3', 'pa'), created_by: createdByPa, status: 'proposed' }]),
    'Assistant',
    resolveActor,
    () => true,
    { kind: 'agent', id: 'pa' },
  );
  expect(selfClosed!.content).toContain('过期提议已收起（已关闭）');
  expect(selfClosed!.content).not.toContain('未采纳');
  expect(selfClosed!.metadata).toMatchObject({
    previous_status: 'proposed',
    status: 'closed',
    attention_actor_ids: [],
  });

  const [selfDeleted] = taskNotices(
    graph([]),
    graph([{ ...node('p4', 'pa'), created_by: createdByPa, status: 'proposed' }]),
    'Assistant',
    resolveActor,
    () => true,
    { kind: 'agent', id: 'pa' },
  );
  expect(selfDeleted!.content).toContain('过期提议已收起（已删除，原入口已失效）');
  expect(selfDeleted!.metadata.attention_actor_ids).toEqual([]);
});
