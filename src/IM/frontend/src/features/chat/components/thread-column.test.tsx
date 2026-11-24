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
  sender_user_id: "peer", content: id, created_at: "2026-11-24T09:30:00Z", attachments: [], permission_requests: [], delivery_status: "completed"
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
  await screen.findByText(first.content);
  const target = document.getElementById(`thread-message-${first.id}`)!;
  expect(target.querySelector("time")).toHaveAttribute("datetime", first.created_at);
  expect(target.querySelector(".chat-avatar")).toBeVisible();
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

it("restores the draft and quote only in their original topic", async () => {
  const client = new QueryClient();
  vi.mocked(authFetchJson).mockResolvedValue({root, following: false, items: []});
  const open = (id: string) => render(<QueryClientProvider client={client}><ThreadColumn
    conversation={group} selfUserId="draft-owner" isMobile={false} rootId={id}
    onSent={() => {}} onClose={() => {}} mentionCandidates={[]}
    renderBody={item => item.content} renderQuote={item => item.content} /></QueryClientProvider>);
  const original = open(root.id);
  const input = await screen.findByRole("textbox");
  expect(input).toHaveFocus();
  fireEvent.click(screen.getByRole("button", {name: /Reply|回复/}));
  fireEvent.change(input, {target: {value: "Half a thought"}});
  original.unmount();

  const other = open("second-topic");
  expect(await screen.findByRole("textbox")).toHaveValue("");
  other.unmount();
  open(root.id);
  expect(await screen.findByRole("textbox")).toHaveValue("Half a thought");
  expect(screen.getByRole("button", {name: /Cancel|取消/})).toBeInTheDocument();
});

it("renders thread_unfollowed system notices with system styling and excludes them from reply count", async () => {
  const reply = message("visible reply");
  const notice: Message = {
    ...message("unfollow-notice"),
    sender: { type: "system", id: "system", display_name: "System" },
    sender_type: "system",
    sender_user_id: "system",
    content: "@E 已取消关注此话题（任务已完成），后续不再自动接收回复；需要时可 @ 提及再次唤醒。",
    system_notice: { kind: "thread_unfollowed", agent_id: "e", reason: "任务已完成" },
  };
  vi.mocked(authFetchJson).mockResolvedValue({ root, following: true, items: [{ message: reply }, { message: notice }] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ThreadColumn conversation={group} selfUserId="me" isMobile={false}
    rootId={root.id} onSent={() => {}} onClose={() => {}} mentionCandidates={[]}
    renderBody={item => item.content} renderQuote={item => item.content} /></QueryClientProvider>);
  const noticeEl = await screen.findByText(notice.content);
  expect(noticeEl).toHaveClass("chat-bubble-system");
  expect(screen.getByRole("separator")).toHaveTextContent(/1\s*(reply|条回复)/);
});
