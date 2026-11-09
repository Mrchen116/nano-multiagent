import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider, useLocation, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setLanguage } from "../../../i18n";
import { AgentWorkPanel } from "./agent-work-panel";
import type { WorkFocus, WorkView } from "./agent-work-api";

const mocks = vi.hoisted(() => ({ fetch: vi.fn(), subscribe: vi.fn() }));
vi.mock("../../auth/auth-fetch", () => ({ authFetch: mocks.fetch }));
vi.mock("../../../realtime/user-stream", () => ({ subscribeUserStream: mocks.subscribe }));
vi.mock('./agent-trajectory', () => ({AgentTrajectory: () => <p>Native trajectory</p>}));
let view: WorkView;
let focus: WorkFocus | null;
const focusPath = (url: string) => url.includes("/work/focus?");
const reply = (turn = view.turns[0], newer_turn_id: string | null = null): WorkFocus => ({turn, newer_turn_id});
function ChatTarget() { const location = useLocation(); const navigate = useNavigate(); return <div><p>Real chat route</p><button onClick={() => navigate(location.state.workReturnUrl)}>Return to work</button></div>; }
function renderWork(entry = "/settings/agents/global?view=work") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/settings/agents/global", element: <div className="im-agent-panel"><AgentWorkPanel agentId="global" /></div> }, { path: "/chat/:id", element: <ChatTarget /> }, { path: "/tasks/:id", element: <p>Task graph route</p> }], { initialEntries: [entry] });
  return { ...render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>), router };
}
beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {configurable:true, value: vi.fn(() => ({matches:false}))});
  setLanguage("zh");
  sessionStorage.clear(); mocks.subscribe.mockReset(); mocks.subscribe.mockReturnValue(() => {}); mocks.fetch.mockReset();
  focus = null;
  view = { root_agent_id: "global", main_session_id: "main", revision: 1, node_connection_state: "online", main_execution: "running", latest_main_usage: null, other_executions: [], next_cursor: null, turns: [{ session_id: "main", turn_id: "turn", seq: 1, status: "running", origin: "user", trigger: { kind: "inbox" }, model_id: "fixture", usage: null, next_items_cursor: null, items: [{ item_id: "tool:read", seq: 1, kind: "tool", payload: { id: "read", name: "inbox", status: "running", input: { action: "read", target: "group-a" }, detail: { action: "read", target: "group-a" } } }] }] };
  mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: []} : focusPath(url) ? {focus} : view), { status: 200 }));
});

describe("Agent work view", () => {
  it("opens and scrolls to the reply's recorded wake, including a different reply in the same Agent", async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    const items = view.turns[0].items;
    const newer = {...view.turns[0], seq: 21, turn_id: 'new-turn', items: [], items_deferred: true};
    const older = {...newer, seq: 13, turn_id: 'old-turn'};
    view = {...view, turns: [newer], next_cursor: 'new-turn'};
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(
      url === '/im/v1/conversations' ? {items: []}
        : url.includes('/items?') ? {items, next_cursor: null}
        : focusPath(url) ? {focus: url.includes('message_id=older') ? reply(older, 'new-turn') : reply(newer)}
        : view
    )));
    sessionStorage.setItem('agent-work:global', JSON.stringify({selected: 'stale-child', expanded: {}, scroll: 999}));
    const {router} = renderWork('/settings/agents/global?view=work&message_id=older');
    await waitFor(() => expect(document.getElementById('work-turn-main-old-turn')).toHaveAttribute('open'));
    expect(document.getElementById('work-turn-main-new-turn')).toBeInTheDocument();
    expect(document.getElementById('work-turn-main-new-turn')).not.toHaveAttribute('open');
    expect(screen.queryByText('中间轮次尚未加载')).not.toBeInTheDocument();
    expect(document.getElementById('work-turn-main-old-turn')?.nextElementSibling).toBe(screen.getByRole('button', {name: '更早轮次'}));
    expect(await screen.findByRole('button', {name: /inbox/})).toBeVisible();
    await waitFor(() => expect(scroll).toHaveBeenCalled());
    expect(screen.queryByRole('button', {name: '关闭子轨迹'})).not.toBeInTheDocument();
    await act(() => router.navigate('/settings/agents/global?view=work&message_id=newer'));
    await waitFor(() => expect(document.getElementById('work-turn-main-new-turn')).toHaveAttribute('open'));
    await act(() => router.navigate('/settings/agents/global?view=work&message_id=older'));
    await waitFor(() => expect(document.getElementById('work-turn-main-old-turn')).toHaveAttribute('open'));
    expect(mocks.fetch.mock.calls.some(([url]) => String(url).includes('/turns/old-turn/items?'))).toBe(true);
  });

  it('jumps to old replies while keeping the ordinary pages and their next cursor', async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const turn = (id: number) => ({...view.turns[0], turn_id: String(id), seq: id * 5, items: [], items_deferred: true});
    const requested: Array<string | null> = [];
    mocks.fetch.mockImplementation(async (url: string) => {
      const params = new URL(url, 'http://nano.test').searchParams;
      if (url === '/im/v1/conversations') return new Response(JSON.stringify({items: []}));
      if (url.includes('/items?')) return new Response(JSON.stringify({items: [{item_id: 'body', seq: 1, kind: 'message', payload: {text: 'Saved body'}}], next_cursor: null}));
      if (focusPath(url)) {
        const id = params.get('message_id') === 'A' ? 7 : 3;
        return new Response(JSON.stringify({focus: reply(turn(id), String(id + 1))}));
      }
      const before = params.get('before_turn');
      requested.push(before);
      const newest = before ? Number(before) - 1 : 12;
      return new Response(JSON.stringify({...view, turns: [turn(newest), turn(newest - 1)], next_cursor: newest > 2 ? String(newest - 1) : null}));
    });
    const {router} = renderWork('/settings/agents/global?view=work&message_id=A');
    const card = (id: number) => document.getElementById(`work-turn-main-${id}`);
    const earlier = () => screen.getByRole('button', {name: '更早轮次'});
    const gaps = () => screen.queryAllByText('中间轮次尚未加载');
    await waitFor(() => expect(card(7)).toHaveAttribute('open'));
    expect(requested).toEqual([null]);
    expect(card(11)?.nextElementSibling).toBe(earlier());
    fireEvent.click(earlier());
    await waitFor(() => expect(card(9)).toBeInTheDocument());
    expect(requested).toEqual([null, '11']);
    expect(gaps()).toHaveLength(1); // The one missing turn is 8, even though sequence positions are sparse.
    expect(earlier().nextElementSibling).toBe(gaps()[0]);

    await act(() => router.navigate('/settings/agents/global?view=work&message_id=B'));
    await waitFor(() => expect(card(3)).toHaveAttribute('open'));
    expect(card(7)).toBeInTheDocument();
    expect(card(9)).toBeInTheDocument();
    expect(gaps()).toHaveLength(2);
    await act(() => router.navigate('/settings/agents/global?view=work&message_id=A'));
    await waitFor(() => expect(card(7)).toHaveAttribute('open'));
    expect(requested).toEqual([null, '11']);

    fireEvent.click(earlier());
    await waitFor(() => expect(card(8)).toBeInTheDocument());
    expect(gaps()).toHaveLength(1);
    expect(card(7)?.nextElementSibling).toBe(earlier());
    fireEvent.click(earlier());
    await waitFor(() => expect(card(5)).toBeInTheDocument());
    fireEvent.click(earlier());
    await waitFor(() => expect(card(4)).toBeInTheDocument());
    expect(gaps()).toHaveLength(0);
    expect(requested).toEqual([null, '11', '9', '7', '5']);
    expect(document.querySelectorAll('#work-turn-main-3')).toHaveLength(1);
    fireEvent.click(earlier());
    await waitFor(() => expect(card(1)).toBeInTheDocument());
    expect(requested.at(-1)).toBe('3');
  });

  it.each([3, 4])('uses the current page boundary when a once-newest cached anchor falls behind turn %s', async (latest) => {
    Element.prototype.scrollIntoView = vi.fn();
    const turn = (id: number) => ({...view.turns[0], turn_id: String(id), seq: id * 5});
    view = {...view, turns: [turn(1)]};
    focus = reply(turn(1));
    const {router} = renderWork('/settings/agents/global?view=work&message_id=A');
    const card = (id: number) => document.getElementById(`work-turn-main-${id}`);
    await waitFor(() => expect(card(1)).toHaveAttribute('open'));
    await act(() => router.navigate('/settings/agents/global?view=work'));
    view = {...view, turns: [turn(latest), turn(latest - 1)], next_cursor: String(latest - 1), next_turn_id: String(latest - 2)};
    act(() => mocks.subscribe.mock.calls[0][0].onEvent({eventType: 'agent.work.updated', payload: {agent_id: 'global'}}));
    await waitFor(() => expect(card(latest)).toBeInTheDocument());

    expect(card(latest - 1)).toBeInTheDocument();
    expect(card(1)).toHaveAttribute('open');
    expect(mocks.fetch.mock.calls.filter(([url]) => focusPath(String(url)))).toHaveLength(1);
    const earlier = screen.getByRole('button', {name: '更早轮次'});
    const gap = screen.queryByText('中间轮次尚未加载');
    if (latest === 3) {
      expect(gap).not.toBeInTheDocument();
      expect(earlier.previousElementSibling).toBe(card(1));
    } else {
      expect(earlier.previousElementSibling).toBe(card(3));
      expect(earlier.nextElementSibling).toBe(gap);
      expect(card(1)?.previousElementSibling).toBe(gap);
    }
  });

  it('places ordinary pagination in the historical execution on a narrow screen', async () => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(window.matchMedia).mockReturnValue({matches: true} as MediaQueryList);
    const turn = (id: number) => ({...view.turns[0], session_id: 'retired', turn_id: String(id), seq: id * 5, items: []});
    view = {...view, other_executions: [{session_id: 'retired', scope: 'global_main'}]};
    mocks.fetch.mockImplementation(async (url: string) => {
      const data = url === '/im/v1/conversations' ? {items: []}
        : focusPath(url) ? {focus: reply(turn(1), '2')}
        : url.includes('before_turn=3') ? {turns: [turn(2), turn(1)], next_cursor: null}
        : url.includes('/sessions/retired/turns?') ? {turns: [turn(4), turn(3)], next_cursor: '3'}
        : view;
      return new Response(JSON.stringify(data));
    });
    renderWork('/settings/agents/global?view=work&message_id=old-reply');
    await waitFor(() => expect(document.getElementById('work-turn-retired-1')).toHaveAttribute('open'));
    expect(document.getElementById('work-turn-main-turn')).toBeInTheDocument();
    const child = screen.getByRole('button', {name: '关闭子轨迹'}).closest('aside')!;
    const gap = await within(child).findByText('中间轮次尚未加载');
    const earlier = within(child).getByRole('button', {name: '更早轮次'});
    expect(earlier.nextElementSibling).toBe(gap);
    fireEvent.click(earlier);
    await waitFor(() => expect(document.getElementById('work-turn-retired-2')).toBeInTheDocument());
    expect(within(child).queryByText('中间轮次尚未加载')).not.toBeInTheDocument();
  });

  it('retains manual folding and reading position across native-view switches after applying a reply anchor', async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    focus = reply();
    const {container} = renderWork('/settings/agents/global?view=work&message_id=reply');
    const scroller = container.querySelector<HTMLElement>('.im-agent-panel')!;
    scroller.scrollTo = vi.fn((options?: ScrollToOptions | number) => {if (typeof options === 'object') scroller.scrollTop = options.top ?? 0;});
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByText('Inbox 唤醒'));
    expect(screen.getByText('Inbox 唤醒').closest('details')).not.toHaveAttribute('open');
    scroller.scrollTop = 320;
    fireEvent.click(screen.getByRole('tab', {name: '原生轨迹'}));
    expect(await screen.findByText('Native trajectory')).toBeVisible();
    fireEvent.click(screen.getByRole('tab', {name: '工作记录'}));
    await waitFor(() => expect(scroller.scrollTop).toBe(320));
    expect(screen.getByText('Inbox 唤醒').closest('details')).not.toHaveAttribute('open');
    expect(scroll).toHaveBeenCalledTimes(1);
  });

  it('waits for the deferred body before scrolling and does not pull readers back on refresh', async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    let finishItems!: (response: Response) => void;
    const body = new Promise<Response>(resolve => {finishItems = resolve;});
    view = {...view, turns: [{...view.turns[0], items: [], items_deferred: true}]};
    focus = reply();
    mocks.fetch.mockImplementation(async (url: string) => url.includes('/items?') ? body.then(response => response.clone()) : new Response(JSON.stringify(url === '/im/v1/conversations' ? {items: []} : focusPath(url) ? {focus} : view)));
    renderWork('/settings/agents/global?view=work&message_id=reply');
    await waitFor(() => expect(screen.getByText('Inbox 唤醒').closest('details')).toHaveAttribute('open'));
    expect(scroll).not.toHaveBeenCalled();
    finishItems(new Response(JSON.stringify({items: [{item_id: 'body', seq: 1, kind: 'message', payload: {text: 'Actual deferred body'}}], next_cursor: null})));
    expect(await screen.findByText('Actual deferred body')).toBeVisible();
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByText('Inbox 唤醒'));
    act(() => mocks.subscribe.mock.calls[0][0].onEvent({eventType: 'agent.work.updated', payload: {agent_id: 'global'}}));
    await waitFor(() => expect(mocks.fetch.mock.calls.filter(([url]) => String(url).includes('?view=summary')).length).toBeGreaterThan(1));
    expect(screen.getByText('Inbox 唤醒').closest('details')).not.toHaveAttribute('open');
    expect(scroll).toHaveBeenCalledTimes(1);
  });

  it("does not guess a wake for an unavailable reply and can retry after sync", async () => {
    const {router} = renderWork('/settings/agents/global?view=work&message_id=missing');
    expect(await screen.findByText('该回复的工作记录尚未同步或不可用。')).toBeVisible();
    expect(screen.getByText('Inbox 唤醒').closest('details')).not.toHaveAttribute('open');
    focus = reply();
    act(() => mocks.subscribe.mock.calls[0][0].onEvent({eventType: 'agent.work.updated', payload: {agent_id: 'global'}}));
    await waitFor(() => expect(screen.getByText('Inbox 唤醒').closest('details')).toHaveAttribute('open'));
    fireEvent.click(screen.getByRole('button', {name: '查看最新轮次'}));
    await waitFor(() => expect(router.state.location.search).toBe('?view=work'));
  });
  it('drops the cached anchor when a refresh denies access', async () => {
    Element.prototype.scrollIntoView = vi.fn();
    let denied = false;
    focus = reply({...view.turns[0], turn_id: 'old', seq: 0}, 'turn');
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(
      url === '/im/v1/conversations' ? {items: []} : focusPath(url) ? {focus} : view
    ), {status: denied && focusPath(url) ? 403 : 200}));
    renderWork('/settings/agents/global?view=work&message_id=old');
    await waitFor(() => expect(document.getElementById('work-turn-main-old')).toHaveAttribute('open'));
    denied = true;
    act(() => mocks.subscribe.mock.calls[0][0].onEvent({eventType: 'agent.work.updated', payload: {agent_id: 'global'}}));
    expect(await screen.findByText('该回复的工作记录尚未同步或不可用。')).toBeVisible();
    expect(document.getElementById('work-turn-main-old')).not.toBeInTheDocument();
    expect(document.getElementById('work-turn-main-turn')).toBeInTheDocument();
  });

  it("loads a deferred turn only when opened and retains its complete tool details", async () => {
    const items = view.turns[0].items;
    view = {...view, turns: [{...view.turns[0], items: [], items_deferred: true, tool_count: 1}]};
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: []} : url.includes('/items?') ? {items, next_cursor: null} : view), {status: 200}));
    renderWork();
    await screen.findByText("Inbox 唤醒");
    expect(mocks.fetch.mock.calls.some(([url]) => String(url).includes('/items?'))).toBe(false);
    fireEvent.click(screen.getByText("Inbox 唤醒"));
    expect(await screen.findByRole("button", {name: /inbox/})).toBeVisible();
    expect(mocks.fetch.mock.calls.some(([url]) => String(url).includes('/items?after_seq=0'))).toBe(true);
  });
  it("opens a task link from Agent prose within the current application", async () => {
    view = { ...view, turns: [{ ...view.turns[0], items: [{ item_id: "graph-reply", seq: 1, kind: "assistant_message", payload: { content: `[Saved task](${window.location.origin}/tasks/tg_one?scope=root&node=A)` } }] }] };
    const { router } = renderWork();
    fireEvent.click(await screen.findByText("Inbox 唤醒"));
    fireEvent.click(screen.getByRole("link", { name: "Saved task" }));
    expect(await screen.findByText("Task graph route")).toBeVisible();
    expect(router.state.location.search).toBe("?scope=root&node=A");
  });

  it("distinguishes child execution from receiving a background result", async () => {
    view = { ...view, turns: [
      { ...view.turns[0], turn_id: "child-execution", description: "Explain the joke", scope: "subagent", origin: "background_task", trigger: undefined, items: [] },
      { ...view.turns[0], turn_id: "child-return", scope: "subagent", origin: "background_task", trigger: undefined, items: [{ item_id: "return", seq: 2, kind: "background_return", payload: { task_type: "agent", result: "Nested child result" } }] }
    ] };
    renderWork();
    expect(await screen.findByText("Explain the joke")).toBeVisible();
    expect(screen.getByText("收到子 Agent 结果")).toBeVisible();
    expect(screen.queryByText("收到后台结果")).not.toBeInTheDocument();
  });

  it("keeps background result titles when the summary defers their items", async () => {
    view = {...view, turns: [{...view.turns[0], scope: 'subagent', origin: 'background_task', trigger: undefined, items: [], items_deferred: true, has_background_returns: true, background_task_type: 'bash'}]};
    renderWork();
    expect(await screen.findByText('收到后台 Bash 结果')).toBeVisible();
  });

  it("updates the same tool row from durable refresh and retains expansion after real Chat navigation", async () => {
    const { router } = renderWork();
    fireEvent.click(await screen.findByText("Inbox 唤醒"));
    fireEvent.click(await screen.findByRole("button", { name: /inbox/ }));
    expect(screen.queryByText("没有匹配记录")).not.toBeInTheDocument();
    view = { ...view, revision: 2, turns: [{ ...view.turns[0], items: [{ ...view.turns[0].items[0], payload: { ...view.turns[0].items[0].payload, status: "completed", detail: { action: "read", target: "group-a", has_more: false, messages: [{ message_id: "m-a", sender: { name: "Alice" }, content: [{ type: "text", text: "Actual message" }], source: { conversation_id: "group-a" } } ] } } }] }] };
    act(() => mocks.subscribe.mock.calls[0][0].onEvent({ eventType: "agent.work.updated", payload: { agent_id: "global", revision: 2 } }));
    expect(await screen.findByText("Actual message")).toBeInTheDocument();
    expect(screen.getAllByTestId("process-item")).toHaveLength(1);
    fireEvent.click(screen.getByRole("link", { name: "原消息" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/chat/group-a"));
    expect(router.state.location.search).toBe("?message_id=m-a");
    fireEvent.click(screen.getByRole("button", { name: "Return to work" }));
    expect(await screen.findByText("Actual message")).toBeVisible();
  });

  it("shows actual background results and opens only the linked child session", async () => {
    view = { ...view, other_executions: [{ session_id: "child-session", scope: "subagent", parent_session_id: "main", child_agent_id: "researcher", description: "Research child" }], turns: [{ ...view.turns[0], items: [{ item_id: "message:result", seq: 2, kind: "assistant_message", payload: { content: "Parent response", background_returns: [{ task_id: "task-a", task_type: "agent", agent_id: "researcher", status: "completed", description: "Research child", result: "Actual child result" }] } }] }] };
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: []} : url.includes("/sessions/") ? { turns: [], next_cursor: null } : view), { status: 200 }));
    renderWork();
    fireEvent.click(await screen.findByText("Inbox 唤醒"));
    expect(screen.getByRole("button", { name: "查看关联执行 · Research child" })).toBeVisible();
    fireEvent.click(screen.getByTestId("process-background-return-toggle"));
    expect(screen.getByText("Actual child result")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "查看关联执行 · Research child" }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("/im/v1/agents/global/work/sessions/child-session/turns?view=summary", expect.objectContaining({signal: expect.any(AbortSignal)})));
    expect(screen.getByRole("button", { name: "关闭子轨迹" })).toBeVisible();
  });

  it("opens each consecutive return and agent message from its own message card", async () => {
    const sources = ["child-a", "child-b", "child-a"];
    view = { ...view, other_executions: [
      { session_id: "child-a", scope: "subagent", description: "Research" },
      { session_id: "child-b", scope: "subagent", description: "Review" }
    ], turns: [{ ...view.turns[0], items: sources.map((source, index) => ({
      item_id: `message:${index}`, seq: index + 1, kind: "assistant_message",
      payload: { content: `Result ${index}`, source_kind: index === 2 ? "agent-message" : "subagent-settled", source_session_id: source }
    })) }] };
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(
      url === "/im/v1/conversations" ? { items: [] } : url.includes("/sessions/") ? { turns: [], next_cursor: null } : view
    )));
    renderWork();
    fireEvent.click(await screen.findByText("Inbox 唤醒"));
    for (const [index, source] of sources.entries()) {
      const card = screen.getByText(`Result ${index}`).closest(".im-work-assistant")!;
      fireEvent.click(within(card as HTMLElement).getByRole("button", { name: "查看关联执行" }));
      await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(
        `/im/v1/agents/global/work/sessions/${source}/turns?view=summary`,
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      ));
      expect(await screen.findByRole("heading", { name: source === "child-a" ? "Research" : "Review" })).toBeVisible();
      fireEvent.click(screen.getByRole("button", { name: "关闭子轨迹" }));
    }
  });

  it("shows a repeated background source once while retaining distinct task returns", async () => {
    const result = { task_id: "task-a", task_type: "agent", agent_id: "researcher", status: "completed", result: "Shared result" };
    view = { ...view, turns: [{ ...view.turns[0], items: [
      { item_id: "message:first", seq: 1, kind: "assistant_message", payload: { content: "Reasoning result", background_returns: [result] } },
      { item_id: "message:second", seq: 2, kind: "assistant_message", payload: { content: "Delivery result", background_returns: [result] } },
      { item_id: "message:third", seq: 3, kind: "assistant_message", payload: { content: "Other task", background_returns: [{ ...result, task_id: "task-b" }] } }
    ] }] };
    renderWork();
    fireEvent.click(await screen.findByText("Inbox 唤醒"));
    expect(screen.getAllByTestId("process-background-return-toggle")).toHaveLength(2);
  });

  it.each([["manual", "Cron · 手动执行"], ["scheduled", "Cron · 定时执行"], [undefined, "Cron"]])("shows %s Cron metadata and actual session delivery with navigation", async (trigger, label) => {
    view = { ...view, other_executions: [{ session_id: "cron-session", scope: "cron", job_id: "report", trigger }] };
    const page = { turns: [{ ...view.turns[0], session_id: "cron-session", turn_id: "cron-turn", scope: "cron", job_id: "report", origin: "model", trigger: { kind: "cron", source: trigger }, items: [] }], next_cursor: null, control_items: [
      { item_id: "cron-trigger", kind: "cron_trigger", seq: 4, payload: { job_id: "report", trigger } },
      { item_id: "cron-delivery", kind: "cron_delivery", seq: 5, payload: { conversation_id: "target-chat", message_id: "sent-message", text: "Actual scheduled report" } }
    ] };
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: []} : url.includes("/sessions/") ? page : view), { status: 200 }));
    const { router } = renderWork();
    fireEvent.click(await screen.findByText("关联执行 · 1"));
    fireEvent.click(screen.getByRole("button", { name: `${label} · report cron-session` }));
    await screen.findByText("执行记录");
    expect(screen.getAllByText(`${label} · report`).length).toBeGreaterThanOrEqual(3);
    if (!trigger) expect(screen.queryByText(/Cron · (手动|定时)执行/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("执行记录"));
    expect(screen.getByText("Actual scheduled report")).toBeVisible();
    fireEvent.click(screen.getByRole("link", { name: "投递聊天 · 原消息" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/chat/target-chat"));
    expect(router.state.location.search).toBe("?message_id=sent-message");
  });

  it("labels a registered workflow execution using its real scope", async () => {
    view = { ...view, other_executions: [{ session_id: "workflow-session", scope: "workflow", title: "workflow:raw-title" }] };
    const page = { turns: [{ ...view.turns[0], session_id: "workflow-session", scope: "workflow", origin: "model", trigger: null, items: [] }], next_cursor: null, control_items: [] };
    mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: []} : url.includes("/sessions/") ? page : view), { status: 200 }));
    renderWork();
    fireEvent.click(await screen.findByText("关联执行 · 1"));
    fireEvent.click(screen.getByRole("button", { name: "Workflow 执行 workflow-session" }));
    await waitFor(() => expect(screen.getAllByText("Workflow 执行").length).toBeGreaterThanOrEqual(3));
    expect(screen.queryByText("workflow:raw-title")).not.toBeInTheDocument();
  });

  it("keeps unavailable statistics unknown and disables offline permissions", async () => {
    view = { ...view, node_connection_state: "offline", main_execution: "unknown", turns: [{ ...view.turns[0], status: "waiting_permission", items: [{ item_id: "permission:p", seq: 2, kind: "permission", payload: { request_id: "p", tool_name: "bash", tool_input: { command: "pwd" }, question: "Allow execution?", status: "pending", options: [{ id: "allow_once", label: "Allow", description: "" }] } }] }] };
    renderWork();
    fireEvent.click(await screen.findByText("Inbox 唤醒"));
    expect(screen.getAllByText("Token 未报告").length).toBeGreaterThan(0);
    expect(screen.getByText(/节点离线，正在显示已保存记录/)).toBeInTheDocument();
    const allow = await screen.findByRole("button", { name: /Allow once|允许一次|允许/ });
    expect(allow).toBeDisabled();
  });
});

it("renders named targets and hides lifecycle noise", async () => {
  view.turns[0].items.push(
    {item_id: "config", seq: 2, kind: "runtime_config_applied", payload: {model: "private-config"}},
    {item_id: "status", seq: 3, kind: "run_status", payload: {status: "completed"}},
    {item_id: "sent", seq: 4, kind: "tool", payload: {id: "sent", name: "send_message", status: "completed", input: {to: "group-a", text: "Delivery"}, detail: {target: "group-a", status: "ok", text: "Delivery"}}}
  );
  mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: [{id: "group-a", title: "Project A"}]} : view)));
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  fireEvent.click(await screen.findByRole("button", {name: /inbox.*Project A/}));
  expect(screen.queryByRole("link", {name: "Project A"})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: /send_message.*Project A/}));
  expect(screen.getByRole("link", {name: "Project A"})).toHaveAttribute("href", "/chat/group-a");
  expect(screen.queryByText("运行配置已应用")).not.toBeInTheDocument();
  expect(screen.queryByText("run_status")).not.toBeInTheDocument();
  expect(screen.queryByText("private-config")).not.toBeInTheDocument();
});

it("switches UI language without translating agent content", async () => {
  view.turns[0].items.push({item_id: "text", seq: 2, kind: "assistant_message", payload: {content: "原始正文"}});
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  act(() => setLanguage("en"));
  expect(await screen.findByText("Inbox wake-up")).toBeInTheDocument();
  expect(screen.getByText("Agent response")).toBeInTheDocument();
  expect(screen.getByText("原始正文")).toBeInTheDocument();
});

it("shows empty and failed views with retry", async () => {
  view.turns = [];
  const result = renderWork();
  expect(await screen.findByText(/暂无工作记录/)).toBeInTheDocument();
  result.unmount();
  mocks.fetch.mockResolvedValue(new Response("Unavailable", {status: 503}));
  renderWork();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByRole("button", {name: "重试"})).toBeEnabled();
});

it("loads a newly available process page, refreshes its tools and restores it after Chat", async () => {
  let lateStatus = "running";
  mocks.fetch.mockImplementation(async (url: string) => new Response(JSON.stringify(
    url === "/im/v1/conversations" ? {items:[]} : url.includes("/items?") ? {items:[{item_id:"late",seq:101,kind:"tool",payload:{id:"late",name:"inbox",status:lateStatus,input:{action:"read",target:"group-b"},detail:{action:"read",target:"group-b",messages:[{message_id:"late-message",content:[{type:"text",text:"Later page message"}],source:{conversation_id:"group-b"}}]}}}],next_cursor:null} : view
  ),{status:200}));
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  expect(screen.queryByRole("button",{name:"加载更多过程"})).not.toBeInTheDocument();
  view = {...view,revision:2,turns:[{...view.turns[0],next_items_cursor:"100",items:Array.from({length:100},(_,i)=>({item_id:`initial-${i}`,seq:i+1,kind:"thinking",payload:{text:`Thought ${i}`}}))}]};
  act(()=>mocks.subscribe.mock.calls[0][0].onEvent({eventType:"agent.work.updated",payload:{agent_id:"global"}}));
  fireEvent.click(await screen.findByRole("button",{name:"加载更多过程"}));
  fireEvent.click(await screen.findByRole("button",{name:/inbox.*group-b/}));
  expect(screen.queryByText("Later page message")).not.toBeInTheDocument();
  lateStatus = "completed";
  act(()=>mocks.subscribe.mock.calls[0][0].onEvent({eventType:"agent.work.updated",payload:{agent_id:"global"}}));
  expect(await screen.findByText("Later page message")).toBeVisible();
  fireEvent.click(screen.getByRole("link",{name:"原消息"}));
  fireEvent.click(await screen.findByRole("button",{name:"Return to work"}));
  expect(await screen.findByText("Later page message")).toBeVisible();
});

it("lets the online Gateway validate an unresolved permission after IM recovery", async () => {
  view = {...view,main_execution:"unknown",turns:[{...view.turns[0],status:"unknown",items:[{item_id:"permission:p",seq:1,kind:"permission",payload:{request_id:"p",tool_name:"bash",tool_input:{command:"pwd"},question:"Allow execution?",status:"pending",options:[{id:"allow_once",label:"Allow",description:""}]}}]}]};
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  expect(screen.getByRole("button",{name:"允许"})).toBeEnabled();
});

it("shows repeated reasoning from one model output once while retaining its body and tool", async () => {
  view.turns[0].items = [
    { item_id: "event:first", seq: 1, kind: "assistant_message", payload: { run_id: "run", group_id: "group", message_id: "m1", content: "", reasoning_content: "Calculate dinner budget" } },
    { item_id: "event:second", seq: 2, kind: "assistant_message", payload: { run_id: "run", group_id: "group", message_id: "m2", content: "I will ask the budget agent.", reasoning_content: "Calculate dinner budget" } },
    { item_id: "tool:send", seq: 3, kind: "tool", payload: { id: "send", name: "send_message", status: "completed", input: { to: "budget", text: "Please calculate" } } }
  ];
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  expect(screen.getAllByText("Calculate dinner budget")).toHaveLength(1);
  expect(screen.getByText("I will ask the budget agent.")).toBeVisible();
  expect(screen.getByText("send_message")).toBeVisible();
});

it("keeps new reasoning and identical wording from different model outputs", async () => {
  view.turns[0].items = [
    { item_id: "a", seq: 1, kind: "assistant_message", payload: { run_id: "run", group_id: "group", reasoning_content: "Check budget." } },
    { item_id: "b", seq: 2, kind: "assistant_message", payload: { run_id: "run", group_id: "group", reasoning_content: "Check budget. Then ask the planner." } },
    { item_id: "c", seq: 3, kind: "assistant_message", payload: { run_id: "run", group_id: "other", reasoning_content: "Check budget." } }
  ];
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  expect(screen.getAllByText("Check budget.")).toHaveLength(2);
  expect(screen.getByText("Then ask the planner.")).toBeInTheDocument();
});


it.each([
  ['online', 'catching_up', '工作记录正在补齐，当前显示已保存内容。'],
  ['online', undefined, '当前显示已保存记录，最新进度尚未确认。'],
  ['online', 'unknown', '当前显示已保存记录，最新进度尚未确认。'],
  ['online', 'current', undefined],
  ['offline', 'catching_up', '节点离线，正在显示已保存记录。活动执行状态未知，授权暂不可处理。'],
] as const)('shows saved-record completeness for %s / %s without changing reported usage', async (connection, state, text) => {
  view={...view,node_connection_state:connection,record_sync_state:state,latest_main_usage:{turn_id:'turn',context_used:42,output:7}};
  const result=renderWork();
  await screen.findByText('最近已报告的主上下文');
  const callouts=result.container.querySelectorAll('.im-work-callout');
  expect(callouts).toHaveLength(text?1:0);
  if(text)expect(callouts[0]).toHaveTextContent(text);
  expect(result.container.querySelector('.im-work-latest')).toHaveTextContent('42');
});

it("refreshes only the separate head and opened active detail, and fills a new history gap on demand", async () => {
  const turn = (id: number, status = "completed", session = "main") => ({
    ...view.turns[0], session_id: session, turn_id: String(id), seq: id * 5, status,
    items: [], items_deferred: true,
  });
  const requested: string[] = [];
  let newest = 10;
  let revision = 20;
  let main = "main";
  mocks.fetch.mockImplementation(async (url: string) => {
    if (url === "/im/v1/conversations") return new Response(JSON.stringify({items: []}));
    requested.push(url);
    const q = new URL(url, "http://nano.test").searchParams;
    if (url.includes("/items?")) {
      const delta = q.has("after_revision");
      const older = q.get("after_seq") === "1";
      const item = (second: boolean, changed = false) => ({
        item_id: second ? "second" : "first", seq: second ? 2 : 1, revision: changed ? 21 : second ? 20 : 19,
        kind: "message", payload: {text: changed ? "Updated same item" : second ? "Original second item" : "First item"},
      });
      return new Response(JSON.stringify(delta ? {items: revision > 20 && q.get("after_revision") === "20" ? [item(true, true)] : [], revision, next_cursor: null}
        : {items: [item(older)], revision: 20, next_cursor: older ? null : "1"}));
    }
    if (url.endsWith("/sessions/main")) return new Response(JSON.stringify({session_id: "main", scope: "global_main"}));
    const retired = url.includes("/sessions/main/");
    const id = retired ? "main" : main;
    const before = q.get("before_turn");
    const head = before ? Number(before) - 1 : retired ? 16 : newest;
    return new Response(JSON.stringify({
      ...view, catalog: "separate", main_session_id: id, revision,
      turns: [turn(head, head === 10 ? "running" : "completed", id), turn(head - 1, "completed", id)],
      next_cursor: String(head - 1), next_turn_id: String(head - 2),
    }));
  });
  renderWork();
  const card = (id: number, session = "main") => document.getElementById(`work-turn-${session}-${id}`);
  const notify = () => act(() => mocks.subscribe.mock.calls[0][0].onEvent({eventType: "agent.work.updated", payload: {agent_id: "global"}}));
  await waitFor(() => expect(card(10)).toBeInTheDocument());
  fireEvent.click(card(10)!.querySelector("summary")!);
  expect(await screen.findByText("First item")).toBeVisible();
  fireEvent.click(screen.getByRole("button", {name: "加载更多过程"}));
  expect(await screen.findByText("Original second item")).toBeVisible();

  for (const id of [8, 6, 4]) {
    fireEvent.click(screen.getByRole("button", {name: "更早轮次"}));
    await waitFor(() => expect(card(id)).toBeInTheDocument());
  }
  const oldRequests = () => requested.filter(url => url.includes("before_turn=") || url.includes("after_seq=")).length;
  const originalReadCount = oldRequests();
  revision = 21;
  notify();
  expect(await screen.findByText("Updated same item")).toBeVisible();
  expect(screen.queryByText("Original second item")).not.toBeInTheDocument();
  expect(oldRequests()).toBe(originalReadCount);

  newest = 16;
  notify();
  await waitFor(() => expect(card(16)).toBeInTheDocument());
  expect(card(10)).toHaveAttribute("open");
  expect(card(4)).toBeInTheDocument();
  expect(await screen.findByText("中间轮次尚未加载")).toBeInTheDocument();
  expect(oldRequests()).toBe(originalReadCount);
  fireEvent.click(screen.getByRole("button", {name: "更早轮次"}));
  await waitFor(() => expect(card(14)).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", {name: "更早轮次"}));
  await waitFor(() => expect(card(12)).toBeInTheDocument());
  expect(screen.queryByText("中间轮次尚未加载")).not.toBeInTheDocument();
  expect(requested.filter(url => url.includes("before_turn=")).every(url => url.includes("/sessions/main/turns?"))).toBe(true);

  main = "replacement";
  newest = 10;
  notify();
  await waitFor(() => expect(card(10, "replacement")).toBeInTheDocument());
  expect(card(10)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: "更早轮次"}));
  await waitFor(() => expect(card(8, "replacement")).toBeInTheDocument());
  expect(requested.at(-1)).toContain("/sessions/replacement/turns?");
});

it("opens a separate execution directly, without looking it up in the catalog", async () => {
  const calls: string[] = [];
  view = {...view, catalog: "separate", turns: [{...view.turns[0], items: [], items_deferred: true}]};
  mocks.fetch.mockImplementation(async (url: string) => {
    calls.push(url);
    return new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: []}
      : url.includes("/items?") ? {items: [{item_id: "sender", seq: 5, kind: "message", payload: {text: "Child message", source_session_id: "old-direct-child"}}], revision: 5, next_cursor: null}
      : url.includes("/sessions/old-direct-child/turns") ? {turns: [], next_cursor: null}
      : url.endsWith("/sessions/old-direct-child") ? {session_id: "old-direct-child", scope: "subagent", description: "A deeply archived execution"}
      : view));
  });
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  fireEvent.click(await screen.findByRole("button", {name: "查看关联执行"}));
  expect(await screen.findByText("A deeply archived execution")).toBeVisible();
  expect(calls.some(url => url.includes("/sessions/old-direct-child/turns?view=summary&catalog=separate"))).toBe(true);
  expect(calls.some(url => url.includes("/work/sessions?"))).toBe(false);
});

it("reads final item revisions after an older active request completes", async () => {
  let status = "running";
  let revision = 20;
  let release!: () => void;
  let deltas = 0;
  const item = (text: string, rev: number) => ({item_id: "result", seq: 1, revision: rev, kind: "message", payload: {text}});
  mocks.fetch.mockImplementation(async (url: string) => {
    if (url === "/im/v1/conversations") return new Response(JSON.stringify({items: []}));
    if (url.includes("after_revision=")) {
      if (++deltas === 1) {
        await new Promise<void>(resolve => { release = resolve; });
        return new Response(JSON.stringify({items: [], next_cursor: null, revision: 20}));
      }
      return new Response(JSON.stringify({items: [item("Final result after pending fetch",22)], next_cursor: null, revision: 22}));
    }
    if (url.includes("/items?"))
      return new Response(JSON.stringify({items: [item("Old running result",20)], next_cursor: null, revision: 20}));
    return new Response(JSON.stringify({...view, catalog:"separate", revision, main_execution:status,
      turns:[{...view.turns[0], status, items:[], items_deferred:true}]}));
  });
  renderWork();
  const card = () => document.getElementById("work-turn-main-turn")!;
  const notify = () => act(() => mocks.subscribe.mock.calls[0][0].onEvent({eventType:"agent.work.updated",payload:{agent_id:"global"}}));
  await waitFor(() => expect(card()).toBeInTheDocument());
  fireEvent.click(card().querySelector("summary")!);
  expect(await screen.findByText("Old running result")).toBeVisible();
  revision=21;notify();
  await waitFor(() => expect(deltas).toBe(1));
  status="completed";revision=22;notify();
  await waitFor(() => expect(card().querySelector("summary")).toHaveTextContent("已完成"));
  release();
  expect(await screen.findByText("Final result after pending fetch")).toBeVisible();
  expect(deltas).toBe(2);
});

it("finds a late exact child on demand for an already loaded tool", async () => {
  const calls: string[] = [];
  view = {...view, catalog: "separate", turns: [{...view.turns[0], items: [], items_deferred: true}]};
  mocks.fetch.mockImplementation(async (url: string) => {
    calls.push(url);
    return new Response(JSON.stringify(url === "/im/v1/conversations" ? {items: []}
      : url.includes("/items?") ? {items: [{item_id: "tool:read", seq: 5, kind: "tool", payload: {id:"read", name:"read", status:"completed"}}], revision: 5}
      : url.includes("/work/sessions?") ? {sessions: [{session_id:"late-child"}], match_mode:"exact"}
      : url.includes("/sessions/late-child/turns") ? {turns: [], next_cursor: null}
      : url.endsWith("/sessions/late-child") ? {session_id:"late-child", scope:"subagent", description:"Late exact child"}
      : view));
  });
  renderWork();
  fireEvent.click(await screen.findByText("Inbox 唤醒"));
  fireEvent.click(await screen.findByRole("button", {name: /read.*调用完成/}));
  expect(calls.some(url => url.includes("/work/sessions?"))).toBe(false);
  fireEvent.click(screen.getByRole("button", {name: "查看子执行"}));
  expect(await screen.findByText("Late exact child")).toBeVisible();
  expect(calls.find(url => url.includes("/work/sessions?"))).toContain("tool_call_id=read");
});
