import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import type { UserStreamSubscriber } from "../../realtime/user-stream/user-stream-runtime";
import { useAuthStore } from "../auth/auth-store";
import type { Conversation } from "./chat-types";
import { useMembershipCache } from "./use-membership-cache";

const { list } = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock("./chat-api", () => ({ listConversations: list }));
let subscriber: UserStreamSubscriber;
vi.mock("../../realtime/user-stream", () => ({
  subscribeUserStream: (value: UserStreamSubscriber) => { subscriber = value; return () => {}; }
}));
const key = ["chat", "conversations"];
function fixture() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook(() => useMembershipCache(), { wrapper });
  return { client, ...hook };
}
function change(id = "removed") {
  act(() => subscriber.onEvent({ eventType: "conversation.membership_changed", payload: { conversation_id: id } }));
}
beforeEach(() => {
  list.mockReset().mockResolvedValue([]);
  useAuthStore.getState().setSession({ access_token: "token", user: {
    id: "owner", username: "owner", display_name: "Owner", owner_id: "owner", locale: "en", default_entry_node_id: null,
    membership_status: "active", is_company_admin: true, owned_node_ids: [], created_at: ""
  } });
});

it("coalesces a replay burst into one authority read and immediately removes message caches", async () => {
  const { client } = fixture();
  client.setQueryData(["chat", "messages", "removed"], ["private"]);
  for (let i = 0; i < 100; i++) change();
  expect(client.getQueryData(["chat", "messages", "removed"])).toBeUndefined();
  await waitFor(() => expect(client.getQueryData(key)).toEqual([]));
  expect(list).toHaveBeenCalledTimes(1);
});

it("discards an in-flight authority response after a newer membership change and waits for fresh recovery", async () => {
  const resolvers: Array<(value: Conversation[]) => void> = [];
  list.mockImplementation(() => new Promise(resolve => resolvers.push(resolve)));
  const { client } = fixture();
  client.setQueryData(key, []);
  change();
  await waitFor(() => expect(resolvers).toHaveLength(1));
  for (let i = 0; i < 100; i++) change();
  const recovery = subscriber.onRecovery!();
  await act(async () => { resolvers[0]!([{ id: "removed" } as Conversation]); });
  await waitFor(() => expect(resolvers).toHaveLength(2));
  expect(client.getQueryData(key)).toEqual([]);
  await act(async () => { resolvers[1]!([]); await recovery; });
  expect(client.getQueryData(key)).toEqual([]);
  expect(list).toHaveBeenCalledTimes(2);
});

it("retries recovery after a failed authority read", async () => {
  list.mockRejectedValueOnce(new Error("offline"));
  const { client } = fixture();
  await expect(subscriber.onRecovery!()).rejects.toThrow("offline");
  await act(async () => { await subscriber.onRecovery!(); });
  expect(client.getQueryData(key)).toEqual([]);
  expect(list).toHaveBeenCalledTimes(2);
});

it("does not publish a late authority response after unmount", async () => {
  let resolve!: (value: Conversation[]) => void;
  list.mockImplementation(() => new Promise(done => { resolve = done; }));
  const { client, unmount } = fixture();
  const recovery = subscriber.onRecovery!();
  await waitFor(() => expect(list).toHaveBeenCalledTimes(1));
  unmount();
  await act(async () => { resolve([{ id: "removed" } as Conversation]); await recovery; });
  expect(client.getQueryData(key)).toBeUndefined();
});
