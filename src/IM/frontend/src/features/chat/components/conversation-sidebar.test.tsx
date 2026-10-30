import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { i18n } from "../../../i18n";
import type { Conversation } from "../chat-types";
import { ConversationSidebar } from "./conversation-sidebar";

function conv(over: Partial<Conversation>): Conversation {
  return {
    id: "c?",
    title: "?",
    participants: [],
    participant_ids: [],
    type: "direct",
    direct_kind: "agent",
    owner_id: "user-1",
    creator_id: "user-1",
    is_pinned: false,
    is_muted: false,
    unread_count: 0,
    last_message_preview: null,
    last_message_at: null,
    created_at: "2026-01-01T00:00:00Z",
    run_state: "idle",
    source_agent_id: null,
    source_node_id: null,
    ...over
  };
}

const CONVS: Conversation[] = [
  conv({
    id: "c1",
    title: "Assistant",
    type: "direct",
    direct_kind: "agent",
    unread_count: 2,
    last_message_preview: "Hi",
    participants: [{ type: "user", id: "u1" }, { type: "agent", id: "a1" }]
  }),
  conv({ id: "c2", title: "Sprint Planning", type: "group", direct_kind: null,
    participants: [{ type: "user", id: "u1" }, { type: "agent", id: "a1" }] }),
  conv({ id: "c3", title: "Deploy: agent network", type: "group", direct_kind: null,
    participants: [{ type: "agent", id: "a1" }, { type: "agent", id: "a2" }] }),
  conv({ id: "c4", title: "Planner", type: "direct", direct_kind: "agent" })
];

describe("ConversationSidebar", () => {
  it('shows message matches alongside conversations, pages and opens the original', async () => {
    const user = userEvent.setup(), select = vi.fn();
    const searchMessages = vi.fn(async (_q:string, _kind:string, cursor?:string) => cursor
      ? {messages:[{message_id:'m2',conversation_id:'c2',conversation_name:'Sprint Planning',sender_name:'Bob',created_at:'2026-01-01T00:00:00Z',snippet:'plan older'}]}
      : {messages:[{message_id:'m1',conversation_id:'c2',conversation_name:'Sprint Planning',sender_name:'Alice',created_at:'2025-02-01T00:00:00Z',snippet:'plan approved'}],next_cursor:'next'});
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} searchMessages={searchMessages} onSelectMessage={select} />);
    await user.type(screen.getByRole('searchbox'), 'plan');
    expect(await screen.findByText(/Alice: plan approved/)).toBeVisible();
    expect(screen.getByRole('button', {name:/Alice: plan approved/})).toHaveTextContent('2025');
    expect(screen.getByText('Conversations')).toBeVisible();
    await user.click(screen.getByRole('button', {name:'Load more'}));
    expect(await screen.findByText(/Bob: plan older/)).toBeVisible();
    await user.click(screen.getByRole('button', {name:/Alice: plan approved/}));
    expect(select).toHaveBeenCalledWith('c2','m1');
    await user.click(screen.getByRole('tab', {name:'Group'}));
    await waitFor(() => expect(searchMessages).toHaveBeenLastCalledWith('plan', 'group', undefined, expect.any(AbortSignal)));
  });

  it('restores a search and category after the sidebar is remounted', async () => {
    const user = userEvent.setup();
    let saved: {query:string; filter:'all' | 'group'; pages:number; scrollTop:number} = {query:'',filter:'all',pages:1,scrollTop:0};
    const searchMessages = vi.fn(async (_query:string, _kind:string, cursor?:string) => cursor
      ? {messages:[{message_id:'m2',conversation_id:'c2',conversation_name:'Team',sender_name:'Bob',created_at:'2025-01-01',snippet:'plan second'}]}
      : {messages:[{message_id:'m1',conversation_id:'c2',conversation_name:'Team',sender_name:'Alice',created_at:'2025-01-01',snippet:'plan first'}],next_cursor:'next'});
    const props = {conversations:CONVS, activeConversationId:null, onSelect:() => {}, onNewGroup:() => {}, searchMessages};
    const view = render(<ConversationSidebar {...props} onSearchChange={state => { if (state.filter === 'all' || state.filter === 'group') saved = {...state, filter:state.filter}; }} />);
    await user.type(screen.getByRole('searchbox'), 'plan');
    await user.click(screen.getByRole('tab', {name:'Group'}));
    await user.click(await screen.findByRole('button', {name:'Load more'}));
    expect(await screen.findByText(/Bob: plan second/)).toBeVisible();
    view.unmount();
    render(<ConversationSidebar {...props} initialSearch={saved} />);
    expect(screen.getByRole('searchbox')).toHaveValue('plan');
    expect(screen.getByRole('tab', {name:'Group'})).toHaveAttribute('aria-selected','true');
    expect(await screen.findByText(/Bob: plan second/)).toBeVisible();
    await waitFor(() => expect(searchMessages).toHaveBeenLastCalledWith('plan','group','next',expect.any(AbortSignal)));
  });

  it('distinguishes a failed search from an empty result and retries', async () => {
    const user = userEvent.setup();
    const searchMessages = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({messages:[]});
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} searchMessages={searchMessages} />);
    await user.type(screen.getByRole('searchbox'), 'missing');
    expect(await screen.findByRole('alert')).toHaveTextContent('Search failed');
    expect(screen.queryByText('No matching messages')).toBeNull();
    await user.click(screen.getByRole('button', {name:'Retry'}));
    expect(await screen.findByText('No matching messages')).toBeVisible();
  });

  it("renders all conversations under the default 'all' filter", () => {
    render(
      <ConversationSidebar
        conversations={CONVS}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: /Assistant/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sprint Planning/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Deploy: agent network/ })).toBeInTheDocument();
    expect(within(screen.getByTestId("conv-avatar-c2")).getByRole("img", { name: "Group" })).toBeVisible();
    expect(within(screen.getByTestId("conv-avatar-c1")).queryByRole("img", { name: "Group" })).toBeNull();
  });

  it("filters by kind when a tab is selected", async () => {
    const user = userEvent.setup();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    await user.click(screen.getByRole("tab", { name: "Group" }));
    expect(screen.queryByRole("button", { name: /Assistant/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sprint Planning/ })).toBeInTheDocument();
    // agent-network excluded under Group
    expect(screen.queryByRole("button", { name: /Deploy: agent network/ })).not.toBeInTheDocument();
  });

  it("includes two-Agent directs in Network alongside Agent groups", async () => {
    const user = userEvent.setup();
    const observed = conv({id:"observation",title:"Atlas ↔ Scout",direct_kind:"agent-agent",is_observer:true,can_write:false,participants:[{type:"agent",id:"atlas"},{type:"agent",id:"scout"}]});
    render(<ConversationSidebar conversations={[...CONVS,observed]} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    await user.click(screen.getByRole("tab", {name:"Network"}));
    expect(screen.getByRole("button", {name:/Atlas ↔ Scout/})).toBeVisible();
    expect(screen.getByRole("button", {name:/Deploy: agent network/})).toBeVisible();
    expect(screen.queryByRole("button", {name:/Assistant/})).toBeNull();
  });

  it("filters by search query against title + preview", async () => {
    const user = userEvent.setup();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    await user.type(screen.getByRole("searchbox"), "plan");
    expect(screen.getByRole("button", { name: /Sprint Planning/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Planner/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Assistant/ })).not.toBeInTheDocument();
  });

  it("invokes onSelect with the clicked conversation id", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={onSelect} onNewGroup={() => {}} />);
    await user.click(screen.getByRole("button", { name: /Assistant/ }));
    expect(onSelect).toHaveBeenCalledWith("c1");
  });

  it("opens chat or group creation from one menu", async () => {
    const user = userEvent.setup();
    const onNewGroup = vi.fn();
    const onNewChat = vi.fn();
    const onDiscover = vi.fn();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}}
      onNewGroup={onNewGroup} onNewChat={onNewChat} onDiscover={onDiscover} />);
    const trigger = screen.getByRole("button", { name: "New conversation" });
    expect(screen.queryByRole("menu")).toBeNull();
    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", { name: "New chat" }));
    expect(onNewChat).toHaveBeenCalledOnce();
    expect(onNewGroup).not.toHaveBeenCalled();
    expect(screen.queryByRole("menu")).toBeNull();
    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", { name: "Create group" }));
    expect(onNewGroup).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.queryByRole("button", {name:"Discover public groups"})).not.toBeInTheDocument();
    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", {name:"Discover public groups"}));
    expect(onDiscover).toHaveBeenCalledOnce();
    expect(trigger).toHaveFocus();
  });

  it("supports keyboard navigation and dismisses the creation menu", async () => {
    const user = userEvent.setup();
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}}
      onNewGroup={() => {}} onNewChat={() => {}} />);
    const trigger = screen.getByRole("button", { name: "New conversation" });
    await user.click(trigger);
    expect(screen.getByRole("menuitem", { name: "New chat" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Create group" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger).toHaveFocus();
    await user.click(trigger);
    await user.click(screen.getByRole("searchbox"));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("does not show run-state labels before skill distill mode", () => {
    render(
      <ConversationSidebar
        conversations={[
          conv({ id: "running", title: "Running chat", run_state: "running" })
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
      />
    );

    expect(screen.queryByText("Running")).not.toBeInTheDocument();
  });

  it("shows checkboxes in skill distill mode and disables running conversations", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <ConversationSidebar
        conversations={[
          conv({
            id: "idle",
            title: "Idle chat",
            run_state: "idle",
            source_agent_id: "a1",
            source_node_id: "node-a"
          }),
          conv({
            id: "running",
            title: "Running chat",
            run_state: "running",
            source_agent_id: "a1",
            source_node_id: "node-a"
          })
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
        distillMode
        selectedDistillConversationIds={new Set()}
        selectedDistillEligibleCount={0}
        onToggleDistillConversation={onToggle}
        onEnterDistillMode={() => {}}
        onCancelDistillMode={() => {}}
        onStartDistill={() => {}}
      />
    );

    const idleCheckbox = screen.getByRole("checkbox", { name: /Idle chat/ });
    const runningCheckbox = screen.getByRole("checkbox", { name: /Running chat/ });
    expect(idleCheckbox).toBeEnabled();
    expect(runningCheckbox).toBeDisabled();
    expect(screen.getByText("Running")).toBeInTheDocument();

    await user.click(idleCheckbox);
    expect(onToggle).toHaveBeenCalledWith("idle");
  });

  it("disables sources hosted by a different Gateway after the first selection", () => {
    render(
      <ConversationSidebar
        conversations={[
          conv({ id: "same", title: "Same Gateway", source_agent_id: "a1", source_node_id: "node-a" }),
          conv({ id: "other", title: "Other Gateway", source_agent_id: "a2", source_node_id: "node-b" }),
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
        distillMode
        selectedDistillConversationIds={new Set(["same"])}
        selectedDistillSourceNodeId="node-a"
        selectedDistillEligibleCount={1}
        onToggleDistillConversation={() => {}}
        onEnterDistillMode={() => {}}
        onCancelDistillMode={() => {}}
        onStartDistill={() => {}}
      />
    );

    expect(screen.getByRole("checkbox", { name: /Same Gateway/ })).toBeEnabled();
    expect(screen.getByRole("checkbox", { name: /Other Gateway/ })).toBeDisabled();
    expect(screen.getByText("Different Gateway")).toBeInTheDocument();
  });

  it("does not render disabled rows as selected even if their ids are present in selection state", () => {
    render(
      <ConversationSidebar
        conversations={[
          conv({
            id: "missing-transcript",
            title: "Missing transcript",
            run_state: "idle",
            source_agent_id: null,
            source_node_id: null
          })
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
        distillMode
        selectedDistillConversationIds={new Set(["missing-transcript"])}
        selectedDistillEligibleCount={0}
        onToggleDistillConversation={() => {}}
        onEnterDistillMode={() => {}}
        onCancelDistillMode={() => {}}
        onStartDistill={() => {}}
      />
    );

    const checkbox = screen.getByRole("checkbox", { name: /Missing transcript/ }) as HTMLInputElement;
    expect(checkbox).toBeDisabled();
    expect(checkbox.checked).toBe(false);
    expect(screen.getByRole("button", { name: "Distill to skill" })).toBeDisabled();
  });

  it("opens a right-click menu entry that enters skill distill multi-select", async () => {
    const user = userEvent.setup();
    const onEnter = vi.fn();
    render(
      <ConversationSidebar
        conversations={[
          conv({
            id: "idle",
            title: "Idle chat",
            run_state: "idle",
            source_agent_id: "a1",
            source_node_id: "node-a"
          })
        ]}
        activeConversationId={null}
        onSelect={() => {}}
        onNewGroup={() => {}}
        onEnterDistillMode={onEnter}
      />
    );

    await user.pointer({ keys: "[MouseRight]", target: screen.getByRole("button", { name: /Idle chat/ }) });
    const menu = await screen.findByRole("menu", { name: /Conversation actions/i });
    await user.click(within(menu).getByRole("menuitem", { name: /Distill to skill/i }));

    expect(onEnter).toHaveBeenCalledWith("idle");
  });

  it("shows unread badge on the conversation row when unread_count > 0", () => {
    render(<ConversationSidebar conversations={CONVS} activeConversationId={null} onSelect={() => {}} onNewGroup={() => {}} />);
    const row = screen.getByRole("button", { name: /Assistant/ });
    expect(within(row).getByText("2")).toBeInTheDocument();
  });
});

it.each([false, true])("resolves agent/user mentions in preview and search (distill=%s)", async (distillMode) => {
  const conversations = [conv({ id: "mention-chat", title: "Dinner", type: "group", direct_kind: null,
    participants: [{ type: "agent", id: "planner", display_name: "小策" }, { type: "user", id: "u1", display_name: "小陈" }],
    last_message_preview: '<mention type="user" target_id="planner"/> <mention type="user" target_id="u1"/> 准时到。'
  })];
  const props = { conversations, activeConversationId: null, onSelect: () => {}, onNewGroup: () => {}, distillMode };
  const view = render(<ConversationSidebar {...props} />);
  expect(screen.getByText("@小策 @小陈 准时到。")).toBeVisible();
  await userEvent.type(screen.getByRole("searchbox"), "小策");
  expect(screen.getByText("@小策 @小陈 准时到。")).toBeVisible();
  await userEvent.clear(screen.getByRole("searchbox"));
  view.rerender(<ConversationSidebar {...props} conversations={[{ ...conversations[0], participants: [] }]} />);
  expect(screen.getByText("@unknown @unknown 准时到。")).toBeVisible();
  expect(view.container.textContent).not.toContain("<mention");
});


it("renders structured notice previews in the selected language and updates after a normal message", async () => {
  const conversation = conv({id:"notice-chat",title:"Notices",last_message_preview:"· background self-evolution review: skills updated",
    last_message_system_notice:{kind:"self_evolution_review",source_agent_id:"a",source_agent_display_name:"Assistant",updated_targets:["skills"]}});
  const props = {conversations:[conversation],activeConversationId:null,onSelect:()=>{},onNewGroup:()=>{}};
  try {
    await act(async()=>{await i18n.changeLanguage("zh");});
    const view=render(<ConversationSidebar {...props} />);
    expect(screen.getByText("· 后台自进化：技能已更新")).toBeVisible();
    await act(async()=>{await i18n.changeLanguage("en");});
    expect(screen.getByText("· Background self-evolution: skills updated")).toBeVisible();
    view.rerender(<ConversationSidebar {...props} conversations={[{...conversation,last_message_preview:"New user message",last_message_system_notice:null}]} />);
    expect(screen.getByText("New user message")).toBeVisible();
    expect(screen.queryByText("· Background self-evolution: skills updated")).not.toBeInTheDocument();
  } finally {await act(async()=>{await i18n.changeLanguage("en");});}
});
