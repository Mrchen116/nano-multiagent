import { expect, it } from 'vitest';
import { decodeAgentPublication, decodeChatStream } from '@nano/product-contracts';
import { messageInput, sendPrincipal } from '../src/message-input.js';

it('checks stable chat fields without normalizing dynamic content or original wire bytes', () => {
  const input={vendor:{z:'中文😀',a:[false,null]},kind:'tool_call_completed',message_id:'message',process_seq:7,
    tool_call:{id:'call',input:['native',null],output:false,detail:{nested:{z:1,a:2}},vendor:'untouched'}};
  const bytes=JSON.stringify(input);
  expect(decodeChatStream(input)).toBe(input);
  expect(JSON.stringify(input)).toBe(bytes);
  const completion={kind:'message_completed',message_id:'message',token_usage:null,kernel_message_id:null,elapsed_ms:null};
  expect(decodeChatStream(completion)).toBe(completion);
  expect(decodeChatStream({kind:'run_terminal_reconcile',run_id:'run'})).toEqual({kind:'run_terminal_reconcile',run_id:'run'});
  const publication={from_session_id:'agent|tool_call:call',to:'conversation:chat',text:'  原正文  ',custom:[1,2],interactive:{anything:'owned by existing interactive decoder'}};
  expect(decodeAgentPublication(publication)).toBe(publication);
});

it('retains authenticated identity and rejects malformed HTTP attachment fields before normalizing references', () => {
  const principal={id:'user',username:'alice',membership_status:'active'};
  expect(sendPrincipal(principal)).toBe(principal);
  const input={sender_user_id:'user',content:'  body  ',attachments:[{url:'/im/file',file_name:'a.txt',custom:{z:2,a:1}}]};
  expect(messageInput(input)).toBe(input);
  expect(()=>messageInput({...input,attachments:[{url:{bad:true}}]})).toThrow('url');
  expect(()=>decodeChatStream({kind:'message_completed',message_id:'message',token_usage:{context_used:{bad:true}}})).toThrow('context_used');
});
