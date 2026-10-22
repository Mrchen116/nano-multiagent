import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { setLanguage } from "../../i18n";
import { TEST_ACCESS_TOKEN, TEST_AUTH_USER } from "../../test/render-router";
import { useAuthStore } from "../auth/auth-store";
import { TaskEditor } from "./task-editor";
import type { TaskGraph, TaskNode } from "./task-graphs-api";

const root: TaskNode = { id: "n1", container_id: null, title: "Release", description: "Original", mode: "dag", status: "todo", result: "", derived_from_id: null, selected_candidate_id: null, selection_reason: "", links: [], order: 0, created_at: "2026-10-12", updated_at: "2026-10-12", updated_by: "Owner", last_chat_id: "group", last_chat_title: "Team", assignee: {type:"agent",id:"a"}, can_edit: true };
const graph: TaskGraph = { schema_version:2, graph_id:"tg_test", root_node_id:"n1", revision:9, nodes:[root], dependencies:[], created_at:"2026-10-12", updated_at:"2026-10-12", updated_by:"Owner", relative_url:"/tasks/tg_test", conversation:{id:"group",title:"Team",visibility:"public",is_member:true,can_write:true,dissolved_at:null} };
const members = { participants: [{type:"user",id:"u",display_name:"Human"},{type:"agent",id:"a",display_name:"Agent A"},{type:"agent",id:"stale",display_name:"Stale",is_stale:true}] };
let writes: Record<string, any>[];
let rejectFirst: boolean;
beforeEach(() => {
  setLanguage("en");
  useAuthStore.getState().setSession({ access_token:TEST_ACCESS_TOKEN, user:TEST_AUTH_USER });
  writes=[]; rejectFirst=false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      writes.push(JSON.parse(init.body as string));
      if (rejectFirst && writes.length === 1) return Response.json({detail:{code:"version_conflict",message:"Conflict"}},{status:409});
      return Response.json({graph_id:"tg_test",revision:11});
    }
    if (url.includes("/task-graphs/")) return Response.json({...graph,revision:10,nodes:[{...root,description:"A teammate changed this",assignee:{type:"user",id:"u"}}]});
    if (url.endsWith("/conversations")) return Response.json({items:[{id:"group",title:"Team",can_write:true},{id:"readonly",title:"Read only",can_write:false}]});
    return Response.json(members);
  }));
});
afterEach(() => vi.unstubAllGlobals());
function renderEditor(target: Parameters<typeof TaskEditor>[0]["target"]) {
  const saved=vi.fn();
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><TaskEditor target={target} onClose={vi.fn()} onSaved={saved}/></QueryClientProvider>);
  return saved;
}
it("keeps the draft after a revision conflict and retries only after reading and explicit confirmation", async () => {
  rejectFirst=true;
  const saved=renderEditor({graph,node:root});
  await userEvent.clear(screen.getByLabelText("Purpose and description"));
  await userEvent.type(screen.getByLabelText("Purpose and description"),"My draft");
  await userEvent.click(screen.getByRole("button",{name:"Save"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("draft is kept");
  expect(screen.getByLabelText("Purpose and description")).toHaveValue("My draft");
  expect(screen.getByRole("button",{name:"Save"})).toBeDisabled();
  expect(writes).toHaveLength(1);
  await userEvent.click(screen.getByRole("button",{name:"Read latest record"}));
  await screen.findByText("A teammate changed this");
  expect(screen.getByLabelText("Purpose and description")).toHaveValue("My draft");
  expect(writes).toHaveLength(1);
  await userEvent.click(screen.getByRole("button",{name:"Confirm and retry"}));
  await waitFor(()=>expect(saved).toHaveBeenCalledWith("tg_test"));
  expect(writes[0].base_revision).toBe(9);
  expect(writes[1].base_revision).toBe(10);
  expect(writes[1].request_key).not.toBe(writes[0].request_key);
  expect(writes[1].operations).toContainEqual({op:"update_task",node_id:"n1",patch:expect.objectContaining({description:"My draft"})});
});
it("creates a child unassigned without inheriting its parent's owner and only offers current members", async () => {
  const saved=renderEditor({graph,parent:root});
  await userEvent.type(screen.getByLabelText("Title"),"Check deployment");
  await screen.findByRole("option",{name:"Human"});
  const owners=screen.getByLabelText("Assignee");
  expect(owners).toHaveValue("");
  expect(within(owners).queryByRole("option",{name:"Stale"})).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(saved).toHaveBeenCalled());
  expect(writes[0].operations).toContainEqual(expect.objectContaining({op:"add_task",container_id:"n1",assignee:null,title:"Check deployment"}));
});
it("offers only writable conversations for a root and sends its fixed ownership and member assignment", async () => {
  renderEditor({});
  await screen.findByRole("option",{name:"Team"});
  expect(screen.queryByRole("option",{name:"Read only"})).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Owning conversation"),"group");
  await screen.findByRole("option",{name:"Human"});
  await userEvent.selectOptions(screen.getByLabelText("Assignee"),"user:u");
  await userEvent.type(screen.getByLabelText("Title"),"New goal");
  await userEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({conversation_id:"group",title:"New goal",assignee:{type:"user",id:"u"},mode:"dag"});
});
it("requires a rework reason when claiming completed work", async () => {
  renderEditor({graph,node:{...root,status:"done"},claim:true});
  await userEvent.click(screen.getByRole("button",{name:"Save"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("rework reason");
  expect(writes).toHaveLength(0);
  await userEvent.type(screen.getByLabelText("Latest change"),"Validation failed");
  await userEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({change_note:"Validation failed",operations:expect.arrayContaining([{op:"claim_task",node_id:"n1"}])});
});

it("preserves an existing wait when saving other fields without offering a new wait", async () => {
  const waiting = {...root, status: "waiting" as const, wait: {reason:"Await budget approval, then purchase",schedule_id:"s",owner_agent_id:"a",session_id:"main",next_check_at:"2026-10-22T12:00:00Z"}};
  renderEditor({graph,node:waiting});
  expect(screen.getByLabelText("Status")).toHaveValue("waiting");
  await userEvent.clear(screen.getByLabelText("Title"));
  await userEvent.type(screen.getByLabelText("Title"),"Budget check");
  await userEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(writes).toHaveLength(1));
  expect(writes[0].operations[0].patch).toMatchObject({title:"Budget check",status:"waiting"});
  expect(writes[0].operations[0].patch).not.toHaveProperty("wait");
});
it("does not offer waiting for a new task", async () => {
  renderEditor({graph,parent:root});
  expect(within(screen.getByLabelText("Status")).queryByRole("option",{name:"Waiting"})).not.toBeInTheDocument();
});
