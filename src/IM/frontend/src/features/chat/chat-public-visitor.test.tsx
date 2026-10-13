import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import { ChatWorkspacePage } from "./chat-workspace-page";

vi.mock("../../realtime/user-stream", () => ({ subscribeUserStream: () => () => {} }));
afterEach(() => { vi.unstubAllGlobals(); useAuthStore.getState().clear(); });

it("refreshes a visible public visitor timeline without a member WebSocket", async () => {
  await act(async () => setLanguage("en"));
  useAuthStore.getState().setSession({access_token:TEST_ACCESS_TOKEN,user:TEST_AUTH_USER});
  const conversation = {id:"room",title:"Public work",participants:[],participant_ids:[],type:"group",owner_id:"other",creator_id:"other",is_pinned:false,is_muted:false,unread_count:0,created_at:"2026-09-09T00:00:00Z",visibility:"public",is_member:false,can_write:false};
  const message = (id: string, content: string) => ({id,conversation_id:"room",sender:{id:"other",type:"user",display_name:"Other"},sender_user_id:"other",sender_type:"user",content,attachments:[],delivery_status:"completed",created_at:"2026-09-09T00:00:00Z"});
  let messages = [message("m1", "Initial public message")];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const data = url.includes("/room/messages") ? {items:messages,next_before_message_id:null}
      : url.endsWith("/conversations/room") ? conversation
      : url.endsWith("/conversations") ? {items:[]} : [];
    return new Response(JSON.stringify(data), {status:200,headers:{"Content-Type":"application/json"}});
  }));
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const router = createMemoryRouter([{path:"/chat/:conversationId",element:<ChatWorkspacePage />}], {initialEntries:["/chat/room"]});
  const view = render(<QueryClientProvider client={client}><RouterProvider router={router}/></QueryClientProvider>);
  try {
    await screen.findByText("Initial public message");
    expect(screen.getByRole("button", {name:"Join group"})).toBeInTheDocument();
    messages = [...messages, message("m2", "A new task collaboration notice")];
    await waitFor(() => expect(screen.getByText("A new task collaboration notice")).toBeInTheDocument(), {timeout:4500});
    expect(screen.getByRole("button", {name:"Join group"})).toBeInTheDocument();
  } finally { view.unmount(); client.clear(); }
}, 10000);
