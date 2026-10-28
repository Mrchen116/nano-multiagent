import type { ChatEvent, ChatMessage } from '@nano/product-contracts';
import type { MessageRecord, MessageRecords } from '../src/message-records.js';
import type { MessageInput, SendMessageCommand } from '../src/message-input.js';
declare const row:MessageRecord;
declare const records:MessageRecords;
declare const view:ChatMessage;
// @ts-expect-error SQL JSON columns cannot substitute for a public message.
const badView:ChatMessage=row;
// @ts-expect-error A public projection cannot substitute for a storage record.
const badRecord:MessageRecord=view;
// @ts-expect-error Stable events associate their payload with their event type.
const badEvent:ChatEvent={type:'message.delta',data:{tool_call:{id:'call'}}};
// @ts-expect-error Transport data does not authorize a send.
const noPrincipal:SendMessageCommand={conversationId:'chat',key:null,input:{content:'text'}};
// @ts-expect-error HTTP input is distinct from server-controlled insert metadata.
const metadata:MessageInput={content:'text',publish:false};
records.chatEvent('chat','message',{type:'message.completed',data:{content:'done',token_usage:null}});
void badView;void badRecord;void badEvent;void noPrincipal;void metadata;
