import { WorkNavigationContext } from "./work-thread-link";
import { beforeEach } from "vitest";
import { setLanguage } from "../../../i18n";
beforeEach(() => setLanguage("zh"));
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { ToolCall } from "../chat-types";
import { ConversationToolCard } from "./conversation-tool-card";
import { ToolDetailBody } from "./tool-detail-renderers";

const call: ToolCall = { id: "read", name: "inbox", status: "running", input: { action: "read", target: "group-a", limit: 20 }, detail: { action: "read", target: "group-a", limit: 20 } };
const page = { action: "read", target: "group-a", has_more: false, messages: [{ message_id: "message-a", sender: { name: "Alice" }, source_time: "2026-09-09", source: { conversation_id: "group-a" }, content: [{ type: "text", text: "The actual constraint" }], complete_message: true }] };

describe("conversation tool presentation", () => {
  it("shows parameters during execution, actual page after end, and no invented consumption", () => {
    const result = render(<MemoryRouter><ToolDetailBody call={call} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "group-a" })).toHaveAttribute("href", "/chat/group-a");
    expect(screen.queryByText("没有匹配记录")).not.toBeInTheDocument();
    expect(screen.queryByText("当前页面已返回")).not.toBeInTheDocument();
    result.rerender(<MemoryRouter><ToolDetailBody call={{ ...call, status: "completed", detail: page }} /></MemoryRouter>);
    expect(screen.getByText("The actual constraint")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "原消息" })).toHaveAttribute("href", "/chat/group-a?message_id=message-a");
    expect(screen.queryByText(/已.*摄取/)).not.toBeInTheDocument();
  });

  it("distinguishes history failure from an empty successful page", () => {
    const result = render(<MemoryRouter><ToolDetailBody call={{ ...call, name: "conversations", status: "failed", detail: { ...call.detail, error: "target_not_accessible" } }} /></MemoryRouter>);
    expect(screen.getByText("target_not_accessible")).toBeInTheDocument();
    expect(screen.queryByText("没有匹配记录")).not.toBeInTheDocument();
    result.rerender(<MemoryRouter><ToolDetailBody call={{ ...call, name: "conversations", status: "completed", detail: { ...page, messages: [] } }} /></MemoryRouter>);
    expect(screen.getByText("没有匹配记录")).toBeInTheDocument();
    expect(screen.getByText("聊天历史查询 · 不推进收件箱")).toBeInTheDocument();
  });
});

it("renders wire mentions with participant names in the actual inbox card", () => {
  const detail = {...page, messages: [{...page.messages[0], content: [{type:"text",text:'<mention type="user" target_id="planner"/> 改成8人'}]}]};
  render(<MemoryRouter><WorkNavigationContext.Provider value={{returnUrl:"/work",beforeLeave(){},people:{planner:"小策"}}}><ToolDetailBody call={{...call,status:"completed",detail}}/></WorkNavigationContext.Provider></MemoryRouter>);
  expect(screen.getByText("@小策")).toBeInTheDocument();
  expect(screen.queryByText(/<mention/)).not.toBeInTheDocument();
});

it("keeps the compact inbox focused on messages and actionable pagination", () => {
  const detail = { ...page, messages: [{ ...page.messages[0], sender: { id: "opaque-sender-id" } }] };
  const result = render(<MemoryRouter><ConversationToolCard call={{...call,status:"completed",detail}} compact /></MemoryRouter>);
  expect(screen.getByText("The actual constraint")).toBeInTheDocument();
  expect(screen.getByRole("link", {name:"原消息"})).toHaveAttribute("href", "/chat/group-a?message_id=message-a");
  for (const label of ["收件箱消息页", "目标：", "当前页面已返回", "opaque-sender-id"]) expect(screen.queryByText(label)).not.toBeInTheDocument();
  result.rerender(<MemoryRouter><ConversationToolCard call={{...call,status:"completed",detail:{...detail,has_more:true}}} compact /></MemoryRouter>);
  expect(screen.getByText("还有后续页面")).toBeInTheDocument();
});

it("renders native Inbox identifiers and presenter output without a per-tool renderer", () => {
  const result = render(<MemoryRouter><ToolDetailBody call={{...call,status:"completed",detail:{messages:[{id:"native-message",target:"native-chat",sender:{name:"Alice"},time:"2026-10-10",content:[{type:"text",text:"Native constraint"}]}]}}}/></MemoryRouter>);
  expect(screen.getByText("Native constraint")).toBeInTheDocument();
  expect(screen.getByRole("link",{name:"原消息"})).toHaveAttribute("href","/chat/native-chat?message_id=native-message");
  result.rerender(<MemoryRouter><ToolDetailBody call={{id:"native",name:"owner_tool",input:{},status:"completed",detail:{native_call:{card:"generic",title:"Read sample",rawInput:"sample.txt"},native_view:{card:"generic",content:[{type:"text",text:"Frozen native result"}]}}}}/></MemoryRouter>);
  expect(screen.getByText("Read sample")).toBeInTheDocument();
  expect(screen.getByText("sample.txt")).toBeInTheDocument();
  expect(screen.getByText("Frozen native result")).toBeInTheDocument();
});

it.each(['read', 'search', 'web', 'generic'])('keeps full %s result visible when its native card omits body text', card => {
  render(<ToolDetailBody call={{id:'native',name:'custom',input:{},status:'completed',output:'Short summary',detail:{native_call:{card:'generic',title:'Operation'},native_view:{card},content:'Complete result body'}}}/>);
  expect(screen.getByText('Complete result body')).toBeVisible();
  expect(screen.queryByText('Short summary')).not.toBeInTheDocument();
});

it("renders native cursor and attachment image fields", () => {
  render(<MemoryRouter><ConversationToolCard call={{...call,status:"completed",detail:{next_cursor:"next",messages:[{id:"photo",sender:{name:"Alice"},content:[{type:"attachment",content_type:"image/png",url:"/photo.png",file_name:"Photo"}]}]}}} /></MemoryRouter>);
  expect(screen.getByText("还有后续页面")).toBeVisible();
  expect(screen.getByRole("img",{name:"Photo"})).toHaveAttribute("src","/photo.png");
});
