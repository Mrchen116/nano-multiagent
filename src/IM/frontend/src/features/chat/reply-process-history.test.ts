import { expect, it } from "vitest";
import { applyWsEvent, emptyConversationState, toChatWsEvent } from "./chat-stream-reducer";
import { mergeMessageWithExisting } from "./chat-workspace-page";

it("restores process-only history, deduplicates replay, and preserves terminal state across stale REST", () => {
  const created = toChatWsEvent("message.created", {conversation_id:"c1",message_id:"m1",sender_user_id:"agent:a",sender_type:"agent",content:"",tool_calls:[],token_usage:null,delivery_status:"running",created_at:"2026-09-09T00:00:00Z"})!;
  let state = applyWsEvent({...emptyConversationState, conversation_id:"c1"}, created);
  const update = toChatWsEvent("reply_process.updated", {conversation_id:"c1",message_id:"m1",reply_process:[{item_id:"r1",kind:"revalidation",run_id:"run",seq:0,status:"running",source_messages:[]}]})!;
  state = applyWsEvent(applyWsEvent(state, update), update);
  const stale = state.messages[0]!;
  state = applyWsEvent(state, {type:"message.completed",conversation_id:"c1",message_id:"m1",content:"",token_usage:null,delivery_status:"failed"});
  const merged = mergeMessageWithExisting(stale, state.messages[0]);
  expect(merged.reply_process).toHaveLength(1);
  expect(merged.reply_process?.[0]?.status).toBe("failed");
  expect(merged.content).toBe("");
  expect(merged.delivery_status).toBe("failed");
  expect(mergeMessageWithExisting(state.messages[0]!, stale).reply_process?.[0]?.status).toBe("failed");
  const live = { ...merged,
    tool_calls: [{ id: "tool-live", name: "bash", status: "completed" as const, input: {}, output: "live result" }],
    thinking: [{ seq: 1, text: "live thinking" }] };
  const summarized = mergeMessageWithExisting({ ...merged, tool_calls: [], thinking: [], process_summary: {
    tool_count: 1, thinking_count: 1, background_return_count: 0, reply_process_counts: {},
    has_running_tool: false, approval_allow_count: 0, approval_deny_count: 0
  } }, live);
  expect(summarized.tool_calls).toEqual(live.tool_calls);
  expect(summarized.thinking).toEqual(live.thinking);
});
