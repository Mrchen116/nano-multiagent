import * as imApi from "./im-chat-api";
import * as mockApi from "./mock-chat-api";

const rawMode = import.meta.env.VITE_CHAT_API_MODE;
const chatApiMode = rawMode ?? (import.meta.env.MODE === "test" ? "mock" : "im");
const useMockApi = chatApiMode !== "im";

export const listConversations = useMockApi ? mockApi.listConversations : imApi.listConversations;
export const getConversation = useMockApi ? mockApi.getConversation : imApi.getConversation;
export const sendMessage = useMockApi ? mockApi.sendMessage : imApi.sendMessage;
export const streamConversationEvents = useMockApi
  ? mockApi.streamConversationEvents
  : imApi.streamConversationEvents;
