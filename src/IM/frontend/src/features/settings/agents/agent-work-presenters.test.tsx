import {MemoryRouter} from "react-router-dom";
import {render,screen,fireEvent} from "@testing-library/react";
import {beforeEach,expect,it} from "vitest";
import {setLanguage} from "../../../i18n";
import {WorkTool,WorkUsage,WorkBackground} from "./agent-work-presenters";
beforeEach(()=>setLanguage("en"));
it("keeps denied and in-band failures distinct from completed calls",()=>{
 const call={id:"bash",name:"bash",status:"failed" as const,input:{},approval:"user_deny",reason:"denied"};
 const result=render(<ul><WorkTool call={call}/></ul>);
 expect(screen.getByText("Denied")).toBeInTheDocument();
 expect(screen.getByText("Not executed")).toBeInTheDocument();
 expect(screen.queryByText("Completed")).not.toBeInTheDocument();
 result.rerender(<ul><WorkTool call={{id:"custom",name:"custom",status:"completed",input:{},detail:{success:false}}}/></ul>);
 expect(screen.getByText("Call failed")).toBeInTheDocument();
});
it("does not invent usage or cache values and keeps context separate from cumulative output",()=>{
 const result=render(<WorkUsage value={null}/>);
 expect(screen.getByText("Tokens not reported")).toBeInTheDocument();
 result.rerender(<WorkUsage value={{context_used:1200,output:800,total:2000,context_window:10000}}/>);
 fireEvent.click(screen.getByText("Turn statistics"));
 expect(screen.getByText("12%")).toBeInTheDocument();
 expect(screen.getByText("800")).toBeVisible();
 expect(screen.getByText("Not reported")).toBeVisible();
 expect(screen.queryByText("2,000")).not.toBeInTheDocument();
});

it("shows send errors and background failure details and terminal states",()=>{
 const result=render(<MemoryRouter><ul><WorkTool expanded call={{id:"send",name:"send_message",status:"completed",input:{to:"a",text:"hello"},detail:{status:"target_not_accessible"}}}/></ul></MemoryRouter>);
 expect(screen.getByText("target_not_accessible")).toBeVisible();
 result.rerender(<ul><WorkBackground expanded value={{task_id:"b",task_type:"subagent",description:"Budget",status:"killed",error:"worker terminated"}}/></ul>);
 expect(screen.getByText("worker terminated")).toBeVisible();
 expect(screen.getByText("Killed")).toBeVisible();
});


it("shows native inbox sources when expanded and treats actual sent delivery as successful",()=>{
 setLanguage("zh");
 const result=render(<MemoryRouter><ul><WorkTool expanded call={{id:"check",name:"inbox",status:"completed",input:{action:"check"},detail:{sources:[{target:"chat-global",name:"全局",unread:3,requires_attention:true}]}}}/></ul></MemoryRouter>);
 expect(screen.getByRole("link",{name:"全局"})).toHaveAttribute("href","/chat/chat-global");
 expect(screen.getByText("3 条待读")).toBeVisible();
 result.rerender(<MemoryRouter><ul><WorkTool expanded call={{id:"check",name:"inbox",status:"completed",input:{action:"check"},detail:{sources:[]}}}/></ul></MemoryRouter>);
 expect(screen.getByText("没有匹配记录")).toBeVisible();
 result.rerender(<MemoryRouter><ul><WorkTool expanded call={{id:"send",name:"send_message",status:"completed",input:{target:"chat-global",text:"已收到"},detail:{status:"sent",message_id:"delivered-message"}}}/></ul></MemoryRouter>);
 expect(screen.getByText("调用完成")).toBeVisible();
 expect(screen.queryByText("调用失败")).not.toBeInTheDocument();
 expect(screen.getByText("已收到")).toBeVisible();
});

it("keeps native terminal command and working directory visible after its title changes",()=>{
 setLanguage("zh");
 render(<ul><WorkTool expanded call={{id:"bash",name:"bash",status:"failed",reason:"interrupted",input:{command:"pwd"},detail:{native_view:{card:"terminal",title:"Interrupted",output:"partial output"},native_call:{card:"terminal",title:"pwd",cwd:"/workspace"}}}}/></ul>);
 expect(screen.getByText("已中断")).toBeVisible();
 expect(screen.getByText("pwd",{selector:".chat-tool-detail-term-cmd"})).toBeVisible();
 expect(screen.getByText("/workspace")).toBeVisible();
 expect(screen.getByText("partial output")).toBeVisible();
 expect(screen.getAllByText("pwd")).toHaveLength(1);
 expect(screen.queryByText(/"command"/)).not.toBeInTheDocument();
});

it("shows the retained native subagent prompt before its result",()=>{
 setLanguage("zh");
 render(<ul><WorkTool expanded call={{id:"child",name:"subagent",status:"completed",input:{description:"测试子 agent 调用",prompt:"计算 17 × 23。"},detail:{content:"17 × 23 = 391。",child_session_id:"child-session"}}}/></ul>);
 const prompt=screen.getByText("计算 17 × 23。"),result=screen.getByText("17 × 23 = 391。");
 expect(prompt).toBeVisible();expect(result).toBeVisible();
 expect(prompt.compareDocumentPosition(result)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
 expect(screen.queryByText("child_session_id")).not.toBeInTheDocument();
});
