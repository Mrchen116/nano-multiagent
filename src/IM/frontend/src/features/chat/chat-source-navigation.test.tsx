import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { setLanguage } from "../../i18n";
import { useAuthStore } from "../auth/auth-store";
import { ChatWorkspacePage } from "./chat-workspace-page";
import { WorkThreadLink } from "./components/work-thread-link";

vi.mock("../../realtime/user-stream", () => ({ subscribeUserStream: () => () => {} }));

afterEach(() => {
  vi.unstubAllGlobals();
  useAuthStore.getState().clear();
});

it("moves the original-message highlight when another work source opens in the same chat", async () => {
  await act(async () => setLanguage("en"));
  useAuthStore.getState().setSession({access_token:"token",refresh_token:"refresh",user:{id:"u-self",username:"self",display_name:"You",owner_id:"owner",locale:"en",default_entry_node_id:null,owned_node_ids:[],created_at:"2026-09-09T00:00:00Z"}});
  const conversation = {id:"room",title:"Team",participants:[{id:"u-self",type:"user",display_name:"You"},{id:"u-other",type:"user",display_name:"Other"}],participant_ids:["u-self","u-other"],type:"group",direct_kind:null,owner_id:"owner",creator_id:"u-self",is_pinned:false,is_muted:false,unread_count:0,last_message_preview:null,last_message_at:null,created_at:"2026-09-09T00:00:00Z",run_state:"idle"};
  const messages = ["m1","m2"].map(id => ({id,conversation_id:"room",sender:{id:"u-other",type:"user",display_name:"Other"},sender_user_id:"u-other",sender_type:"user",content:`Message ${id}`,attachments:[],delivery_status:"completed",created_at:"2026-09-09T00:00:00Z"}));
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const data = url.includes("/room/messages") ? {items:messages,next_before_message_id:null}
      : url.endsWith("/conversations") ? {items:[conversation]} : [];
    return new Response(JSON.stringify(data), {status:200,headers:{"Content-Type":"application/json"}});
  }));
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const router = createMemoryRouter([{path:"/chat/:conversationId",element:<ChatWorkspacePage />}], {initialEntries:["/chat/room?message_id=m1"]});
  const view = render(<QueryClientProvider client={client}><RouterProvider router={router}/></QueryClientProvider>);
  const highlightedIds = () => Array.from(view.container.querySelectorAll<HTMLElement>(".im-work-message-target")).map(node => node.dataset.messageId);
  await waitFor(() => expect(highlightedIds()).toEqual(["m1"]));
  await act(async () => { await router.navigate("/chat/room?message_id=m2"); });
  await waitFor(() => expect(highlightedIds()).toEqual(["m2"]));
  await act(async () => { await router.navigate("/chat/room"); });
  await waitFor(() => expect(highlightedIds()).toEqual([]));
  client.clear();
});

it.each([["en", "Location unavailable"], ["zh", "暂不可定位"]] as const)("localizes unavailable source links in %s", async (locale, label) => {
  await act(async () => setLanguage(locale));
  render(<MemoryRouter><WorkThreadLink conversationId="local:pending">External chat</WorkThreadLink></MemoryRouter>);
  expect(screen.getByText(`External chat · ${label}`)).toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
