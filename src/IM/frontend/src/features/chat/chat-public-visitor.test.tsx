import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import { ChatWorkspacePage } from "./chat-workspace-page";

vi.mock("../../realtime/user-stream", () => ({ subscribeUserStream: () => () => {} }));
afterEach(() => { vi.unstubAllGlobals(); useAuthStore.getState().clear(); });

it.each([false, true])("refreshes read-only timelines and clears revoked owner observations (observer=%s)", async observer => {
  await act(async () => setLanguage("en"));
  useAuthStore.getState().setSession({access_token:TEST_ACCESS_TOKEN,user:TEST_AUTH_USER});
  const conversation = {id:"room",title:"Public work",participants:[],participant_ids:[],type:"group",owner_id:"other",creator_id:"other",is_pinned:false,is_muted:false,unread_count:0,created_at:"2026-09-09T00:00:00Z",visibility:"public",is_member:false,can_write:false};
  if (observer) Object.assign(conversation, {title:"Atlas ↔ Scout",type:"direct",direct_kind:"agent-agent",visibility:"private",is_observer:true,participants:[{type:"agent",id:"atlas",display_name:"Atlas"},{type:"agent",id:"scout",display_name:"Scout"}]});
  let revoked = false;
  let resolveOlder: ((response: Response) => void) | undefined;
  const message = (id: string, content: string) => ({id,conversation_id:"room",sender:{id:observer ? "atlas" : "other",type:observer ? "agent" : "user",display_name:observer ? "Atlas" : "Other"},sender_user_id:observer ? "atlas" : "other",sender_type:observer ? "agent" : "user",content,permission_requests:observer ? [{request_id:"approval",tool_name:"bash",question:"Review deployment command",tool_input:{command:"deploy --check"},agent_id:"atlas",status:"pending",options:[{id:"allow_once",label:"Allow once",description:"Allow"},{id:"deny",label:"Deny",description:"Deny"}]}] : [],attachments:[],delivery_status:"completed",created_at:"2026-09-09T00:00:00Z"});
  let messages = [message("m1", "Initial public message")];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (observer && url.includes("before_message_id=")) return new Promise<Response>(resolve => { resolveOlder = resolve; });
    if (revoked && url.includes("/conversations/room")) return new Response("not accessible", {status:404});
    const data = url.includes("/room/messages") ? {items:messages,next_before_message_id:observer ? "older" : null}
      : url.endsWith("/conversations/room") ? conversation
      : url.endsWith("/conversations") ? {items:observer && !revoked ? [conversation] : []} : [];
    return new Response(JSON.stringify(data), {status:200,headers:{"Content-Type":"application/json"}});
  }));
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const router = createMemoryRouter([{path:"/chat/:conversationId?",element:<ChatWorkspacePage />}], {initialEntries:["/chat/room"]});
  const view = render(<QueryClientProvider client={client}><RouterProvider router={router}/></QueryClientProvider>);
  try {
    await screen.findByText("Initial public message");
    if (observer) {
      expect(screen.queryByRole("button", {name:"Join group"})).toBeNull();
      expect(screen.queryByRole("textbox")).toBeNull();
      expect(screen.queryByRole("button", {name:"Send"})).toBeNull();
      expect(screen.queryByRole("button", {name:"Config"})).toBeNull();
      expect(screen.getByText("Agent collaboration · read only")).toBeVisible();
      expect(screen.getByText("Review deployment command")).toBeVisible();
      expect(screen.getByText(/deploy --check/)).toBeVisible();
      expect(screen.queryByRole("button", {name:/Allow once|Deny/})).toBeNull();
    } else expect(screen.getByRole("button", {name:"Join group"})).toBeInTheDocument();
    messages = [...messages, message("m2", "A new task collaboration notice")];
    await waitFor(() => expect(screen.getByText("A new task collaboration notice")).toBeInTheDocument(), {timeout:4500});
    if (observer) {
      const pane = document.querySelector(".chat-pane-messages")!;
      Object.defineProperties(pane, {scrollHeight:{configurable:true,value:1200},clientHeight:{configurable:true,value:300},scrollTop:{configurable:true,writable:true,value:0}});
      fireEvent.scroll(pane);
      await waitFor(() => expect(resolveOlder).toBeDefined());
      revoked = true;
      await waitFor(() => expect(router.state.location.pathname).toBe("/chat"), {timeout:4500});
      expect(screen.queryByText("Initial public message")).toBeNull();
      expect(screen.queryByText("A new task collaboration notice")).toBeNull();
      await act(async () => resolveOlder?.(new Response(JSON.stringify({items:[message("late", "Late forbidden history")],next_before_message_id:null}), {status:200})));
      expect(screen.queryByText("Late forbidden history")).toBeNull();
      expect(client.getQueryData(["chat","messages","room"])).toBeUndefined();
      expect(screen.getByText("This conversation is no longer accessible.")).toBeVisible();
    } else expect(screen.getByRole("button", {name:"Join group"})).toBeInTheDocument();
  } finally { view.unmount(); client.clear(); }
}, 15000);
