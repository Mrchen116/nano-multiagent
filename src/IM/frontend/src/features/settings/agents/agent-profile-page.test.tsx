import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AgentProfilePage } from "./agent-profile-page";
import { NewChatModal } from "../../chat/components/new-chat-modal";
import { NewGroupModal } from "../../chat/components/new-group-modal";
import { useAuthStore } from "../../auth/auth-store";
import { setLanguage } from "../../../i18n";

vi.mock("../../../realtime/user-stream", () => ({ subscribeUserStream: () => () => {} }));

const visitor = {id:"visitor",username:"visitor",display_name:"Visitor",owner_id:"visitor",locale:"en",default_entry_node_id:null,owned_node_ids:[],created_at:""};
const contact = {user_id:"agent-user",kind:"agent",agent_id:"colleague-agent",owner_id:"colleague",owner_display_name:"Colleague",display_name:"Muse",node_name:"Workstation",status:"online",work_mode:"global"};
function response(data: unknown) { return new Response(JSON.stringify(data), {headers:{"Content-Type":"application/json"}}); }
function view(element: React.ReactNode, path = "/settings/agents/colleague-agent") {
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/settings/agents/:agentId" element={element} /><Route path="/chat/:conversationId" element={<p>New private chat</p>} /></Routes></MemoryRouter></QueryClientProvider>);
}
beforeEach(async () => {
  await act(async () => setLanguage("en"));
  useAuthStore.getState().setSession({user:visitor,access_token:"visitor-token",refresh_token:"refresh"});
});
afterEach(() => { vi.unstubAllGlobals(); useAuthStore.getState().clear(); });

it("opens another person's global Agent Work without requesting management configuration", async () => {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input); calls.push(url);
    if (url.includes("/contacts?")) return response({items:[contact],next_cursor:null});
    if (url.endsWith("/conversations")) return response({items:[]});
    if (url.endsWith("/work")) return response({root_agent_id:contact.agent_id,main_session_id:null,revision:1,node_connection_state:"online",main_execution:"idle",latest_main_usage:null,other_executions:[],turns:[],next_cursor:null});
    return new Response(null,{status:404});
  }));
  view(<AgentProfilePage />);
  expect(await screen.findByRole("heading",{name:"Muse"})).toBeVisible();
  expect(screen.queryByRole("button",{name:"Config"})).toBeNull();
  await userEvent.click(screen.getByRole("button",{name:"View Work"}));
  await waitFor(() => expect(calls.some(url=>url.endsWith("/agents/colleague-agent/work"))).toBe(true));
  expect(calls.some(url => /\/config|\/capabilities|\/nodes/.test(url))).toBe(false);
});

it("allows an account with no Gateway to message someone else's Agent using its public identity", async () => {
  const bodies: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/contacts?")) return response({items:[contact],next_cursor:null});
    if (url.endsWith("/conversations") && init?.method === "POST") { bodies.push(JSON.parse(String(init.body))); return response({id:"my-dm"}); }
    return response({items:[]});
  }));
  view(<AgentProfilePage />);
  await userEvent.click(await screen.findByRole("button",{name:"Message"}));
  expect(await screen.findByText("New private chat")).toBeVisible();
  expect(bodies).toEqual([{title:"Muse",type:"direct",participants:[{type:"user",id:"visitor"},{type:"agent",id:"colleague-agent"}]}]);
});

it("finds a person on a later contacts page and keeps mixed group actors distinct", async () => {
  const chosen = vi.fn(async () => {});
  const human = {user_id:"person-b",kind:"human",display_name:"Bo"};
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input),"http://localhost");
    return response(url.searchParams.has("cursor") ? {items:[human],next_cursor:null} : {items:[contact],next_cursor:"page-two"});
  }));
  const modal = view(<NewChatModal onClose={() => {}} onSelect={chosen} />);
  await userEvent.click(await screen.findByRole("button",{name:/Bo/}));
  expect(chosen).toHaveBeenCalledWith(human);
  modal.unmount();
  const create = vi.fn();
  render(<NewGroupModal agents={[{agent_id:"person-b",display_name:"Bo",kind:"human"},{agent_id:"own-agent",display_name:"Iris",kind:"agent"}]} onClose={()=>{}} onCreate={create}/>);
  await userEvent.click(screen.getByLabelText("Bo"));
  await userEvent.click(screen.getByLabelText("Iris"));
  await userEvent.click(screen.getByRole("button",{name:/Create group/}));
  expect(create).toHaveBeenCalledWith({agentIds:["own-agent"],userIds:["person-b"],name:"Bo, Iris"});
});
