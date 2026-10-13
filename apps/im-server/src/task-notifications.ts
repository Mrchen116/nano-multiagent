import type { Row } from './context.js';
const same = (a: Row | null, b: Row | null) => a?.type === b?.type && a?.id === b?.id;
const escape = (value: string) => value.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replace(/[\\[\]()*_`]/g, '\\$&');

/** Describe only the agreed collaboration events, with current member mentions. */
export function taskNotices(doc: Row, before: Row | null, actorName: string,
  resolve: (ref: Row | null) => Row | null, canMention: (user: string) => boolean): Row[] {
  const messages: Row[] = [];
  for (const n of doc.nodes) {
    const old = before?.nodes.find((x: Row) => x.id === n.id);
    const changes: string[] = [], mentioned = new Set<string>();
    const mention = (ref: Row | null): string => {
      const actor = resolve(ref);
      if (!actor) return '未分配';
      if (!actor.user_id || !canMention(actor.user_id)) return escape(actor.display_name);
      if (mentioned.has(actor.user_id)) return escape(actor.display_name);
      mentioned.add(actor.user_id);
      return `<mention type="user" target_id="${actor.user_id}"/>`;
    };
    if (!same(old?.assignee ?? null,n.assignee)) {
      if (!old?.assignee) changes.push(`分配给 ${mention(n.assignee)}`);
      else if (!n.assignee) changes.push(`取消 ${mention(old.assignee)} 的分配`);
      else changes.push(`从 ${mention(old.assignee)} 改派给 ${mention(n.assignee)}`);
    }
    if (old?.status !== n.status && ['paused','closed','in_review','done'].includes(n.status)) {
      const status: Row = {paused:'暂缓',closed:'关闭',in_review:'提交待确认',done:'标记完成'};
      const targets = ['paused','closed'].includes(n.status)
        ? doc.nodes.filter((x:Row) => x.container_id===n.id && x.assignee?.type==='agent').map((x:Row)=>x.assignee)
        : [n.created_by, doc.nodes.find((x:Row)=>x.id===n.container_id)?.assignee].filter(Boolean);
      const refs = [...new Map(targets.map((r:Row)=>[`${r.type}:${r.id}`,r])).values()] as Row[];
      const labels = refs.filter(ref=> {const u=resolve(ref);return u?.user_id && !mentioned.has(u.user_id) && canMention(u.user_id);}).map(mention);
      changes.push(`${status[n.status]}${labels.length ? `，${labels.join(' ')}` : ''}`);
    }
    if (!changes.length) continue;
    const link = `/tasks/${doc.graph_id}?scope=${n.container_id ?? doc.root_node_id}&node=${n.id}`;
    messages.push({content:`${escape(actorName)} 将 [${escape(n.title)}](${link}) ${changes.join('；')}`,
      metadata:{kind:'task_graph',graph_id:doc.graph_id,node_id:n.id,scope_id:n.container_id ?? doc.root_node_id}});
  }
  return messages;
}
