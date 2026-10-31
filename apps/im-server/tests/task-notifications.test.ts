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
