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

export const getChatBootstrapState = useMockApi ? mockApi.getChatBootstrapState : imApi.getChatBootstrapState;
export const confirmBindToken = useMockApi ? mockApi.confirmBindToken : imApi.confirmBindToken;
export const getChatStarter = useMockApi ? mockApi.getChatStarter : imApi.getChatStarter;
export const listConversations = useMockApi ? mockApi.listConversations : imApi.listConversations;
export const getConversation = useMockApi ? mockApi.getConversation : imApi.getConversation;
export const sendMessage = useMockApi ? mockApi.sendMessage : imApi.sendMessage;
export const uploadAttachment = useMockApi ? mockApi.uploadAttachment : imApi.uploadAttachment;
export const getUsageMetrics = useMockApi ? mockApi.getUsageMetrics : imApi.getUsageMetrics;
export const resolveSendAvailability = imApi.resolveSendAvailability;
export const streamConversationEvents = useMockApi
  ? mockApi.streamConversationEvents
  : imApi.streamConversationEvents;
export const resetChatBootstrapState = useMockApi ? mockApi.resetChatBootstrapState : imApi.resetChatBootstrapState;
