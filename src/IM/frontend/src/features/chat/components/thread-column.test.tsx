import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ThreadColumn } from "./thread-column";
import type { Conversation, Message } from "../chat-types";
import { createMessage } from "../chat-api";
import { authFetchJson } from "../../auth/auth-fetch";

vi.mock("../chat-api", () => ({createMessage: vi.fn()}));
vi.mock("../../auth/auth-fetch", () => ({authFetchJson: vi.fn()}));

const message = (id: string): Message => ({
  id, conversation_id: "group", sender: {type: "user", id: "peer"}, sender_type: "user",
  sender_user_id: "peer", content: id, created_at: "", attachments: [], permission_requests: [], delivery_status: "completed"
});
const root = message("proposal");
const group: Conversation = {id: "group", type: "group", title: "Planning", participants: [],
  unread_count: 0, last_message_at: null, last_message_preview: null, participant_ids: [], direct_kind: null,
  owner_id: "me", creator_id: "me", is_pinned: false, is_muted: false, created_at: ""};

it("locates the searched reply, quotes it in the same thread and keeps failed drafts for retry", async () => {
  const first = message("first reply"), second = message("second reply");
  const page = {root, following: false, items: [{message: first}, {message: second}]};
  vi.mocked(authFetchJson).mockResolvedValue(page);
  vi.mocked(createMessage).mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({...message("answer"), thread_root_message_id: root.id});
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const onRead = vi.fn();
  render(<QueryClientProvider client={client}><ThreadColumn conversation={group} selfUserId="me" isMobile={false}
    rootId={root.id} targetId={first.id} onRead={onRead} onSent={() => {}} onClose={() => {}} mentionCandidates={[]}
    renderBody={item => item.content} renderQuote={item => item.content}/></QueryClientProvider>);
  const target = (await screen.findByText(first.content)).closest(".chat-bubble")!;
  expect(target).toHaveFocus();
  expect(screen.getByText(root.content)).toBeVisible();
  fireEvent.click(target.querySelector("button")!);
  const input = screen.getByRole("textbox");
  fireEvent.change(input, {target: {value: "answer"}});
  fireEvent.submit(input.closest("form")!);
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(input).toHaveValue("answer");
  fireEvent.submit(input.closest("form")!);
  await waitFor(() => expect(input).toHaveValue(""));
  expect(createMessage).toHaveBeenLastCalledWith({content: "answer", conversationId: group.id,
    replyToMessageId: first.id, threadRootMessageId: root.id, idempotencyKey: vi.mocked(createMessage).mock.calls[0][0].idempotencyKey});
  expect(onRead).toHaveBeenCalledWith("answer");
});

it("holds the reading position above the bottom and follows new replies at the bottom", async () => {
  const first = {message: message("first")};
  const page = {root, following: true, items: [first]};
  vi.mocked(authFetchJson).mockResolvedValue(page);
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const onRead = vi.fn();
  render(<QueryClientProvider client={client}><ThreadColumn conversation={group} selfUserId="me" isMobile={false}
    rootId={root.id} onRead={onRead} onSent={() => {}} onClose={() => {}} mentionCandidates={[]}
    renderBody={item => item.content} renderQuote={item => item.content}/></QueryClientProvider>);
  const scroller = (await screen.findByText("first")).closest(".chat-pane-messages")!;
  Object.defineProperties(scroller, {clientHeight: {value: 200}, scrollHeight: {value: 800}});
  scroller.scrollTop = 100;
  fireEvent.scroll(scroller);
  const key = ["chat", "thread", group.id, root.id, "me"];
  act(() => { client.setQueryData(key, {...page, items: [first, {message: message("second")}]}); });
  await screen.findByText("second");
  expect(scroller.scrollTop).toBe(100);
  expect(onRead).not.toHaveBeenCalledWith("second");
  scroller.scrollTop = 600;
  fireEvent.scroll(scroller);
  act(() => {client.setQueryData(key, {...page, items: [first, {message: message("second")}, {message: message("third")}]});});
  await screen.findByText("third");
  expect(scroller.scrollTop).toBe(800);
  expect(onRead).toHaveBeenCalledWith("third");
});
