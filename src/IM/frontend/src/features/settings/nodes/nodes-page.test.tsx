import userEvent from "@testing-library/user-event";
import { screen, within, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../app/router";
import { renderRouter } from "../../../test/render-router";

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as typeof fetch;

afterEach(() => fetchMock.mockReset());

describe("nodes page", () => {
  it("offers creation only on online nodes and saves an alias through the node API", async () => {
    const user = userEvent.setup();
    const nodes: import("../im-settings-api").NodeSettingsProfile[] = [
      {
        node_id: "node-app-01",
        owner_id: "owner-1",
        node_name: "node-app-01",
        status: "online",
        last_heartbeat_at: "2026-03-13T10:00:00Z",
        agent_count: 4,
        version: "1.8.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: null
      },
      {
        node_id: "node-app-02",
        owner_id: "owner-1",
        node_name: "node-app-02",
        status: "offline",
        last_heartbeat_at: "2026-03-13T09:00:00Z",
        agent_count: 1,
        version: "1.8.2",
        relay_enabled: true,
        reporting_enabled: true,
        alias: null,
        last_error: "gateway disconnected"
      }
    ];
    const patchedNode = { ...nodes[0], alias: "node-app-01-prod" };
    let patchCall: RequestInit | undefined;
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/im/v1/nodes/node-app-01/config" && init?.method === "PATCH") {
        patchCall = init;
        nodes[0] = patchedNode;
        return Promise.resolve(jsonResponse(patchedNode));
      }
      if (url === "/im/v1/nodes") return Promise.resolve(jsonResponse(nodes));
      if (url === "/im/v1/agents") return Promise.resolve(jsonResponse({ items: [] }));
      if (url === "/im/v1/sync") return Promise.resolve(jsonResponse({ items: [], max_event_id: 0 }));
      if (url === "/im/v1/conversations") return Promise.resolve(jsonResponse({ items: [] }));
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    renderRouter({ routes: appRoutes, initialEntries: ["/settings/nodes"] });

    await user.click(await screen.findByRole("button", { name: "View node-app-01 details" }));
    expect(await screen.findByRole("link", { name: "Create assistant" })).toHaveAttribute(
      "href",
      "/settings/nodes/node-app-01/agents/new"
    );
    expect(screen.queryByTestId("nodes-card-new-agent-node-app-02")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Rename" }));
    const alias = await screen.findByLabelText("Computer name");
    await user.clear(alias);
    await user.type(alias, "node-app-01-prod");
    await user.click(screen.getByRole("button", { name: "Save name" }));

    await waitFor(() => expect(within(screen.getByRole("dialog")).getByRole("heading", { name: "node-app-01-prod" })).toBeInTheDocument());
    expect(JSON.parse(String(patchCall?.body))).toEqual({
      alias: "node-app-01-prod",
      relay_enabled: true,
      reporting_enabled: true
    });
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

it('keeps an alias draft after rejected saving and changes the list only on success', async () => {
  const user = userEvent.setup();
  let reject = true;
  let node = { node_id: 'rename-pc', owner_id: 'user-1', node_name: 'Study computer', alias: null as string | null,
    status: 'online', last_heartbeat_at: '', version: '1.0.0', agent_count: 0, relay_enabled: true, reporting_enabled: true, last_error: null };
  fetchMock.mockImplementation((input, init) => {
    const url = String(input);
    if (url === '/im/v1/nodes/rename-pc/config' && init?.method === 'PATCH') {
      if (reject) return Promise.resolve(new Response(JSON.stringify({ detail: 'gateway unreachable' }), { status: 503 }));
      node = { ...node, alias: JSON.parse(String(init.body)).alias }; return Promise.resolve(jsonResponse(node));
    }
    if (url === '/im/v1/nodes') return Promise.resolve(jsonResponse([node]));
    if (url === '/im/v1/onboarding') return Promise.resolve(jsonResponse({ agents: [], install: { available: false } }));
    return Promise.resolve(jsonResponse({ items: [], max_event_id: 0 }));
  });
  renderRouter({ routes: appRoutes, initialEntries: ['/settings/nodes'] });
  await user.click(await screen.findByRole('button', { name: 'View Study computer details' }));
  await user.click(screen.getByRole('button', { name: 'Rename' }));
  await user.clear(screen.getByLabelText('Computer name'));
  await user.click(screen.getByRole('button', { name: 'Save name' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/Enter a computer name/);
  await user.type(screen.getByLabelText('Computer name'), 'Work computer');
  await user.click(screen.getByRole('button', { name: 'Save name' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/Your name is kept/);
  expect(screen.getByLabelText('Computer name')).toHaveValue('Work computer');
  expect(screen.getByRole('heading', { name: 'Study computer' })).toBeInTheDocument();
  reject = false;
  await user.click(screen.getByRole('button', { name: 'Save name' }));
  expect(await screen.findByRole('heading', { name: 'Work computer' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Back to computers' }));
  expect(screen.getByRole('heading', { name: 'Work computer' })).toBeVisible();
});

it('copies this service installation command and exposes manual copy when clipboard fails', async () => {
  const user = userEvent.setup();
  const command = 'curl -fsSL https://my-im.example/install.sh | sh';
  fetchMock.mockImplementation(input => {
    if (String(input) === '/im/v1/nodes') return Promise.resolve(jsonResponse([]));
    if (String(input) === '/im/v1/onboarding') return Promise.resolve(jsonResponse({ agents: [], install: { available: true, command, origin: 'https://my-im.example' } }));
    return Promise.resolve(jsonResponse({ items: [], max_event_id: 0 }));
  });
  renderRouter({ routes: appRoutes, initialEntries: ['/settings/nodes'] });
  await user.click((await screen.findAllByRole('button', { name: 'Connect computer' }))[0]);
  await user.click(await screen.findByRole('button', { name: 'Install manually' }));
  const copy = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
  await user.click(screen.getByRole('button', { name: 'Copy command' }));
  expect(copy).toHaveBeenCalledWith(command);
  expect(screen.getByRole('button', { name: 'Copied' })).toBeVisible();
  copy.mockRejectedValue(new Error('Permission denied'));
  await user.click(screen.getByRole('button', { name: 'Ask a local agent' }));
  await user.click(screen.getByRole('button', { name: 'Copy instructions' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/copy it manually/);
  expect(screen.getByText(/https:\/\/my-im.example/, { selector: 'code' })).toBeVisible();
});
