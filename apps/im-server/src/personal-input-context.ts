import type { DatabaseSync } from 'node:sqlite';
type Row=Record<string,any>;
/** Select source evidence at the original message's stable position, never at review time.
 *
 * Args:
 *   db: Server message store.
 *   messageId: Authenticated binding's source message.
 *   allowed: Current per-message access check, including source exclusions.
 *   evidence: Existing trusted sender and conversation projection.
 * Returns:
 *   Full current message, the previous twenty accessible messages and one direct reply target.
 */
export function personalInputContext(db:DatabaseSync,messageId:string,allowed:(message:Row)=>boolean,evidence:(message:Row)=>Row):Row {
 const current=db.prepare('SELECT rowid AS sequence,* FROM messages WHERE id=?').get(messageId) as Row|undefined;
 if(!current||!allowed(current))throw new Error('Input review source is not accessible');
 const history=db.prepare('SELECT rowid AS sequence,* FROM messages WHERE conversation_id=? AND rowid<? ORDER BY rowid DESC LIMIT 21')
  .all(current.conversation_id,current.sequence) as Row[];
 const omissions:Row[]=[];
 if(history.length>20)omissions.push({reason:'history_window',limit:20});
 const previous=history.slice(0,20).reverse().filter(row=>{
  if(allowed(row))return true;omissions.push({reason:'history_unavailable',message_id:row.id});return false;
 });
 const reply=current.interaction_reply_json?JSON.parse(current.interaction_reply_json):undefined;
 const replyId=reply?.source_message_id;
 let replyTarget:Row|undefined;
 if(typeof replyId==='string'&&replyId!==current.id&&!previous.some(row=>row.id===replyId)) {
  const row=db.prepare('SELECT rowid AS sequence,* FROM messages WHERE id=?').get(replyId) as Row|undefined;
  if(row&&row.sequence<current.sequence&&allowed(row))replyTarget=evidence(row);
  else omissions.push({reason:'reply_target_unavailable',message_id:replyId});
 }
 return {current:evidence(current),previous:previous.map(evidence),...(replyTarget?{reply_target:replyTarget}:{}),omissions};
}
