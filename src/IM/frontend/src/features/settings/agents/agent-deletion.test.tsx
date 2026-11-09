import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { setLanguage } from "../../../i18n";
import { AgentDeletionControls, useAgentDeletion } from "./agent-deletion";

function Surface() {
  return <AgentDeletionControls name="Atlas" deletion={useAgentDeletion("atlas", true)} online />;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it.each([false, true])("requires confirmation and sends a workspace witness only when selected (%s)", async includeWorkspace => {
  setLanguage("en");
  const view = { agent_id: "atlas", eligible: true, revision: 3, profile_version: 8, workspace: { path: "/owner/atlas", witness: "seen-directory" } };
  const writes: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      writes.push(JSON.parse(String(init.body)));
      return Response.json({ ...view, eligible: false, operation: { operation_id: "delete-atlas", state: "deleted", delete_workspace: includeWorkspace } });
    }
    return Response.json(view);
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/settings/agents/atlas"]}>
    <Routes>
      <Route path="/settings/agents/atlas" element={<Surface />} />
      <Route path="/settings/agents" element={<h1>Agent list</h1>} />
    </Routes>
  </MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const entry = await screen.findByRole("button", { name: "Permanently delete Agent" });
  await user.click(entry);
  let dialog = screen.getByRole("dialog", { name: "Permanently delete Agent" });
  expect(within(dialog).getByText("Atlas")).toBeVisible();
  expect(within(dialog).queryByText("/owner/atlas")).not.toBeInTheDocument();
  const workspaceOption = within(dialog).getByRole("checkbox");
  expect(workspaceOption).not.toBeChecked();
  await user.click(workspaceOption);
  expect(within(dialog).getByText("/owner/atlas")).toBeVisible();
  await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(writes).toHaveLength(0);
  await user.click(entry);
  dialog = screen.getByRole("dialog", { name: "Permanently delete Agent" });
  const reopenedWorkspaceOption = within(dialog).getByRole("checkbox");
  expect(reopenedWorkspaceOption).not.toBeChecked();
  if (includeWorkspace) await user.click(reopenedWorkspaceOption);
  await user.click(within(dialog).getByRole("button", { name: "Confirm permanent deletion" }));
  expect(await screen.findByRole("heading", { name: "Agent list" })).toBeVisible();
  expect(writes).toEqual([{
    request_id: expect.any(String),
    expected_revision: 3,
    expected_profile_version: 8,
    ...(includeWorkspace ? { workspace_witness: "seen-directory" } : {}),
  }]);
});
