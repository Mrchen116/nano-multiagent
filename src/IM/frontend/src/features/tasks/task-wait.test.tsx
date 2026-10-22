import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { setLanguage } from "../../i18n";
import { TaskAgentRuntime, TaskWaitInfo } from "./task-wait";
import type { TaskWaitHealth } from "./task-graphs-api";

const wait = { reason: "Await budget approval. Resume purchasing once approved.", schedule_id: "s", owner_agent_id: "a", session_id: "main", next_check_at: "2026-10-22T12:00:00Z" };
beforeEach(() => setLanguage("en"));
afterEach(() => vi.unstubAllGlobals());

it.each(["valid", "invalid", "unknown", undefined] as const)("keeps the business wait separate from %s schedule health", state => {
  const health: TaskWaitHealth | undefined = state ? { state, checked_at: "2026-10-22T11:00:00Z" } : undefined;
  render(<TaskWaitInfo wait={wait} health={health} />);
  expect(screen.getByText(wait.reason)).toBeVisible();
  if (state === "valid") {
    expect(screen.getByText(/Next check ·/)).toBeVisible();
    expect(screen.queryByText(/could not be verified/)).not.toBeInTheDocument();
  } else if (state === "invalid") {
    expect(screen.getByText(/Schedule needs attention/)).toBeVisible();
    expect(screen.getByText(/No valid schedule/)).toBeVisible();
  } else {
    expect(screen.getByText(/Schedule could not be verified/)).toBeVisible();
    expect(screen.getByText(/Saved schedule time/)).toBeVisible();
  }
  expect(screen.getByText(/not an execution receipt/)).toBeVisible();
});

it("uses observed Agent state and removes stale running evidence when the node disconnects or reading fails", async () => {
  let response: Response = Response.json({state:"running"});
  vi.stubGlobal("fetch",vi.fn(async()=>response.clone()));
  const client = new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
  render(<QueryClientProvider client={client}><TaskAgentRuntime agentId="a" graphId="g" nodeId="n" /></QueryClientProvider>);
  expect(await screen.findByText("Assignee execution · Running")).toBeVisible();
  response = Response.json({state:"offline"});
  await client.invalidateQueries({queryKey:["task-agent-runtime"]});
  await waitFor(()=>expect(screen.getByText("Assignee execution · Node offline")).toBeVisible());
  response = Response.json({detail:"unavailable"},{status:503});
  await client.invalidateQueries({queryKey:["task-agent-runtime"]});
  await waitFor(()=>expect(screen.getByText("Assignee execution · Could not be verified")).toBeVisible());
});

it("reads the assignee through the Task route for Single Thread and Global Agents alike", async () => {
  const fetch = vi.fn(async(_url: string)=>Response.json({state:"idle"}));
  vi.stubGlobal("fetch",fetch);
  const client = new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
  render(<QueryClientProvider client={client}><TaskAgentRuntime agentId="a" graphId="g" nodeId="n" /></QueryClientProvider>);
  expect(await screen.findByText("Assignee execution · Idle")).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(String(fetch.mock.calls[0][0])).toContain("/task-graphs/g/runtime?node_id=n");
});
