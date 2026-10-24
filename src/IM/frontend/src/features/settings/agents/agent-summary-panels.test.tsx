import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {MemoryRouter} from "react-router-dom";
import {beforeEach, expect, it, vi} from "vitest";
import {setLanguage} from "../../../i18n";
import type {Conversation} from "../../chat/chat-types";
import {AgentSessionsPanel} from "./agent-summary-panels";

const api = vi.hoisted(() => ({listConversations: vi.fn()}));
vi.mock("../../chat/chat-api", () => api);

function conversation(id: string, patch: Partial<Conversation> = {}): Conversation {
  return {id, title: id, participants: [], participant_ids: [], type: "direct", direct_kind: "agent",
    owner_id: "owner", creator_id: "owner", is_pinned: false, is_muted: false, unread_count: 0,
    last_message_preview: null, last_message_at: null, created_at: "2026-10-24T00:00:00Z", ...patch};
}

function mount() {
  return render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}>
    <MemoryRouter><AgentSessionsPanel agentId="agent-a" /></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => {setLanguage("en"); vi.resetAllMocks();});

it("lists only this Agent's visible conversations, resolves mentions, and searches titles", async () => {
  api.listConversations.mockResolvedValue([
    conversation("direct", {title: "Planning", participants: [{type: "agent", id: "agent-a", user_id: "a-user", display_name: "Planner"}], last_message_preview: '<mention type="user" target_id="a-user"/> done'}),
    conversation("channel", {title: "Project channel", source_agent_id: "agent-a"}),
    conversation("other", {participants: [{type: "agent", id: "agent-b"}]}),
    conversation("user-collision", {participants: [{type: "user", id: "agent-a"}]}),
  ]);
  mount();
  expect(await screen.findByRole("link", {name: /Planning/})).toHaveAttribute("href", "/chat/direct");
  expect(screen.getByText("@Planner done")).toBeInTheDocument();
  expect(screen.getByRole("link", {name: /Project channel/})).toBeInTheDocument();
  expect(screen.queryByRole("link", {name: /other|user-collision/})).not.toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox"), "PROJECT");
  expect(screen.queryByRole("link", {name: /Planning/})).not.toBeInTheDocument();
  expect(screen.getByRole("link", {name: /Project channel/})).toBeInTheDocument();
});

it("keeps a failed read distinct from an empty list and retries explicitly", async () => {
  api.listConversations.mockRejectedValueOnce(new Error("Offline")).mockResolvedValueOnce([]);
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load conversations");
  expect(screen.queryByText("No conversations yet")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", {name: "Retry"}));
  expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
  expect(api.listConversations).toHaveBeenCalledTimes(2);
});
