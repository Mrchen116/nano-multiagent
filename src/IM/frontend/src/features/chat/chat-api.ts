import * as imApi from "./im-chat-api";
import * as mockApi from "./mock-chat-api";

export function resolveChatApiMode(input: {
  runtimeMode: string;
  explicitMode?: string;
}): "mock" | "im" {
  if (input.explicitMode === "im") {
    return "im";
  }
  if (input.explicitMode === "mock") {
    return "mock";
  }
  return input.runtimeMode === "test" ? "mock" : "im";
}

const chatApiMode = resolveChatApiMode({
  runtimeMode: import.meta.env.MODE,
  explicitMode: import.meta.env.VITE_CHAT_API_MODE
});
const useMockApi = chatApiMode === "mock";

export const listConversations = useMockApi ? mockApi.listConversations : imApi.listConversations;
export const getConversation = useMockApi ? mockApi.getConversation : imApi.getConversation;
export const sendMessage = useMockApi ? mockApi.sendMessage : imApi.sendMessage;
export const streamConversationEvents = useMockApi
  ? mockApi.streamConversationEvents
  : imApi.streamConversationEvents;
