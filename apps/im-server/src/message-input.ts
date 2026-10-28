import { chatAttachments, type ChatAttachment } from '@nano/product-contracts';
import { fail } from './context.js';
import type { MessageMetadata } from './message-records.js';

export type SendPrincipal = {kind?:'user';id:string;username:string} | {kind:'gateway';node_id:string;owner_id:string;node_epoch:number};
export interface MessageInput {
  content?:string;
  attachments?:ChatAttachment[]|null;
  sender?:{id?:string;type?:string};
  sender_user_id?:string;sender_type?:string;
  lifecycle_revision?:number|null;timezone?:string|null;suppress_relay?:boolean;
  interactive?:unknown;interaction_contexts?:unknown;
  interaction_reply?:Record<string,unknown>;
  created_at?:string;sender_display_name?:string;sender_source_id?:string;system_notice?:unknown;
  personal_source?:MessageMetadata['personal_source'];
}
export interface SendMessageCommand {principal:SendPrincipal;conversationId:string;agentId?:string;key:string|null;input:MessageInput}
function object(value:unknown):Record<string,unknown> {
  if(!value||typeof value!=='object'||Array.isArray(value))fail(422,'invalid message input');
  return value as Record<string,unknown>;
}
/** Parse the HTTP shape once; interaction schemas remain with Interactions. */
export function messageInput(value:unknown):MessageInput {
  const row=object(value??{});
  for(const key of ['content','sender_user_id','sender_type','created_at','sender_display_name','sender_source_id'])if(row[key]!==undefined&&typeof row[key]!=='string')fail(422,`invalid ${key}`);
  if(row.timezone!=null&&typeof row.timezone!=='string')fail(422,'invalid timezone');
  if(row.lifecycle_revision!=null&&(typeof row.lifecycle_revision!=='number'||!Number.isFinite(row.lifecycle_revision)))fail(422,'invalid lifecycle_revision');
  if(row.suppress_relay!==undefined&&typeof row.suppress_relay!=='boolean')fail(422,'invalid suppress_relay');
  if(row.attachments!=null)try{chatAttachments(row.attachments);}catch(error){fail(422,(error as Error).message);}
  if(row.sender!==undefined){const sender=object(row.sender);for(const key of ['id','type'])if(sender[key]!==undefined&&typeof sender[key]!=='string')fail(422,`invalid sender ${key}`);}
  if(row.interaction_reply!==undefined)object(row.interaction_reply);
  if(row.personal_source!==undefined) {
    const source=object(row.personal_source);
    for(const key of ['binding_id','agent_id','owner_user_id','display_name'])if(typeof source[key]!=='string')fail(422,`invalid personal_source ${key}`);
    if(source.operation_id!=null&&typeof source.operation_id!=='string')fail(422,'invalid personal_source operation_id');
  }
  return row as MessageInput;
}
/** Select insert metadata explicitly, keeping transport/routing fields out of persistence inputs. */
export function messageMetadata(input:MessageInput):MessageMetadata {
  return {created_at:input.created_at,sender_display_name:input.sender_display_name,sender_source_id:input.sender_source_id,
    system_notice:input.system_notice,interactive:input.interactive,personal_source:input.personal_source};
}

/** Retain the authenticated object identity used by the response revocation gate. */
export function sendPrincipal(value:unknown):SendPrincipal {
  const row=object(value);
  const keys=row.kind==='gateway'?['node_id','owner_id']:['id','username'];
  for(const key of keys)if(typeof row[key]!=='string')fail(403,'invalid sender identity');
  return row as SendPrincipal;
}
