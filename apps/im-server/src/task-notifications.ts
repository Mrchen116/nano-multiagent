import type { Row } from './context.js';
const same = (a: Row | null, b: Row | null) => a?.type === b?.type && a?.id === b?.id;
const escape = (value: string) => value.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replace(/[\[\]()*_`]/g, '\\$&');

/** Describe real business changes once per node, using only current member mentions. */
export function taskNotices(doc: Row, before: Row | null, actorName: string,
  resolve: (ref: Row | null) => Row | null, canMention: (user: string) => boolean): Row[] {
  const messages: Row[] = [];
  const ids = new Set<string>([...doc.nodes, ...(before?.nodes ?? [])].map((n:Row) => n.id));
  for (const id of ids) {
    const n = doc.nodes.find((n:Row) => n.id === id), old = before?.nodes.find((n:Row) => n.id === id);
    const changes:string[] = [], kinds:string[] = [], attention = new Map<string,Row>(), refs=new Set<string>([id]);
    const person=(ref:Row) => escape(resolve(ref)?.display_name??ref.id);
    const task=(nodeId:string|null|undefined) => {
      if(!nodeId)return '无';
      refs.add(nodeId);
      const current=doc.nodes.find((node:Row)=>node.id===nodeId), previous=before?.nodes.find((node:Row)=>node.id===nodeId);
      const title=escape((current??previous)?.title??nodeId);
      return current?'['+title+'](/tasks/'+doc.graph_id+'?scope='+(current.container_id??doc.root_node_id)+'&node='+nodeId+')':title+'（原标识 '+escape(nodeId)+'，已删除）';
    };
    const add = (ref:Row | null | undefined) => { if(ref)attention.set(ref.type + ':' + ref.id,ref); };
    const note = (kind:string, text:string) => { kinds.push(kind);changes.push(text); };
    add(n?.assignee);add(old?.assignee);
    if(!n) {
      note('deleted','已删除，原入口已失效');
      add(before?.nodes.find((p:Row) => p.id === old.container_id)?.assignee);
    } else {
      if(!old)note('created','已创建');
      if(!same(old?.assignee ?? null,n.assignee))note('assignment',!n.assignee?'已取消原负责人 '+person(old.assignee)+' 的分配':old?.assignee?'已从 '+person(old.assignee)+' 改派给 '+person(n.assignee):'已分配给 '+person(n.assignee));
      if(old && old.title !== n.title)note('title','标题已更新');
      if(old && old.description !== n.description)note('requirements','正文要求已更新，请读取最新正文');
      if(old && old.result !== n.result)note('result','结果已更新');
      if(old?.status !== n.status) {
        const status:Row = {todo:'待办',doing:'进行中',waiting:'等待',in_review:'提交待确认',done:'完成',paused:'暂缓',closed:'关闭'};
        note('status',status[n.status]);
        if(['done','in_review'].includes(n.status)){add(n.created_by);add(doc.nodes.find((p:Row) => p.id === n.container_id)?.assignee);}
        if(['paused','closed'].includes(n.status))for(const child of doc.nodes.filter((p:Row) => p.container_id===n.id&&p.assignee?.type==='agent'))add(child.assignee);
      }
      if(old && JSON.stringify(old.wait) !== JSON.stringify(n.wait))note('wait','等待条件或下次检查时间已更新');
      for(const field of ['container_id','derived_from_id','selected_candidate_id'])if(old && old[field]!==n[field]) {
        const labels:Record<string,string>={container_id:'所属父任务',derived_from_id:'派生来源',selected_candidate_id:'选定的替代任务'};
        note('relationship',labels[field]+'从 '+task(old[field])+' 变为 '+task(n[field]));
        for(const nodeId of [old[field],n[field]])add([...doc.nodes,...(before?.nodes??[])].find((p:Row)=>p.id===nodeId)?.assignee);
      }
      const edges = (d:Row|null) => (d?.dependencies ?? []).filter((e:Row) => e.from===id||e.to===id);
      if(old && JSON.stringify(edges(before)) !== JSON.stringify(edges(doc))) {
        const sameEdge=(a:Row,b:Row)=>a.from===b.from&&a.to===b.to;
        const describe=(edge:Row)=>task(edge.from)+' → '+task(edge.to);
        const added=edges(doc).filter((edge:Row)=>!edges(before).some((prior:Row)=>sameEdge(edge,prior)));
        const removed=edges(before).filter((edge:Row)=>!edges(doc).some((next:Row)=>sameEdge(edge,next)));
        note('dependencies',[...removed.map((edge:Row)=>'已移除依赖 '+describe(edge)),...added.map((edge:Row)=>'已新增依赖 '+describe(edge))].join('；'));
        for(const edge of [...edges(before),...edges(doc)])for(const nodeId of [edge.from,edge.to])add([...doc.nodes,...(before?.nodes??[])].find((p:Row)=>p.id===nodeId)?.assignee);
      }
    }
    if(!changes.length)continue;
    const node=n??old, mentioned=new Set<string>();
    const labels=[...attention.values()].map(ref=>resolve(ref)).filter((actor):actor is Row => !!actor).map(actor=>{
      if(!actor.user_id||!canMention(actor.user_id)||mentioned.has(actor.user_id))return escape(actor.display_name);
      mentioned.add(actor.user_id);return '<mention type="user" target_id="'+actor.user_id+'"/>';
    });
    const title=escape(node.title), link='/tasks/'+doc.graph_id+'?scope='+(node.container_id??doc.root_node_id)+'&node='+id;
    messages.push({content:escape(actorName)+'：'+(n?'['+title+']('+link+')':title)+'，'+changes.join('；')+(labels.length?'。'+labels.join(' '):''),
      metadata:{kind:'task_graph',graph_id:doc.graph_id,node_id:id,scope_id:node.container_id??doc.root_node_id,
        revision:doc.revision,event_time:doc.updated_at,task_refs:[...refs].map(node_id=>({graph_id:doc.graph_id,node_id})),change_kinds:kinds,
        attention_actor_ids:[...attention.values()].map(ref=>ref.id)}});
  }
  return messages;
}
