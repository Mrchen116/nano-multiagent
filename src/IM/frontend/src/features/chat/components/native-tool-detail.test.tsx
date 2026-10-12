import {render,screen} from "@testing-library/react";
import {beforeEach,expect,it} from "vitest";
import {setLanguage} from "../../../i18n";
import {ToolDetailBody} from "./tool-detail-renderers";
import type {ToolCall} from "../chat-types";
beforeEach(()=>setLanguage("zh"));
const call=(view: Record<string,unknown>, rest: Partial<ToolCall> = {}):ToolCall=>({id:"native",name:"custom",status:"completed",input:{hiddenArgument:"DO_NOT_REPEAT"},output:"Short summary",detail:{native_call:{card:"generic",title:"Operation"},native_view:view,content:"RAW_FALLBACK"},...rest});
it("renders native read lines and search groups without duplicating raw results",()=>{
 const result=render(<ToolDetailBody call={call({card:"read",path:"a.txt",offset:2,totalLines:8,lines:[{number:2,text:"second line"}]})}/>);
 expect(screen.getByText("2 second line",{exact:false})).toBeVisible();
 expect(screen.queryByText("RAW_FALLBACK")).not.toBeInTheDocument();
 expect(screen.queryByText(/DO_NOT_REPEAT/)).not.toBeInTheDocument();
 result.rerender(<ToolDetailBody call={call({card:"search",shape:"matches",total:7,truncated:true,files:[{path:"b.txt",matches:[{lineNumber:4,line:"found term"}]}]})}/>);
 expect(screen.getByText("b.txt")).toBeVisible();expect(screen.getByText("4 found term",{exact:false})).toBeVisible();
 expect(screen.getByText(/7 匹配/)).toBeVisible();
 result.rerender(<ToolDetailBody call={call({card:"search",shape:"paths",total:1,truncated:false,paths:["found.txt"]})}/>);
 expect(screen.getByText("found.txt")).toBeVisible();
});
it("renders native web sources as links and fetch metadata alongside its body",()=>{
 const result=render(<ToolDetailBody call={call({card:"web",kind:"search",answer:"Native answer",sources:[{url:"https://example.com/source",title:"Primary source",snippet:"Evidence"}],truncated:false})}/>);
 expect(screen.getByRole("link",{name:"Primary source"})).toHaveAttribute("href","https://example.com/source");
 expect(screen.getByText("Native answer")).toBeVisible();expect(screen.queryByText("RAW_FALLBACK")).not.toBeInTheDocument();
 result.rerender(<ToolDetailBody call={call({card:"web",kind:"fetch",url:"https://example.com/page",statusCode:200,truncated:true})}/>);
 expect(screen.getByText(/HTTP 200/)).toBeVisible();expect(screen.getByText("RAW_FALLBACK")).toBeVisible();
});
it("shows a failed edit's error instead of its proposed diff and preserves empty terminal output",()=>{
 const result=render(<ToolDetailBody call={call({card:"diff",diffs:[{path:"file",oldText:"old",newText:"NOT_APPLIED"}]},{status:"failed",detail:{native_view:{card:"diff",diffs:[{path:"file",oldText:"old",newText:"NOT_APPLIED"}]},content:"Write denied"}})}/>);
 expect(screen.getByText("Write denied")).toBeVisible();expect(screen.queryByText(/NOT_APPLIED/)).not.toBeInTheDocument();
 result.rerender(<ToolDetailBody call={call({card:"terminal"},{detail:{native_call:{card:"terminal",title:"true"},native_view:{card:"terminal",output:"",exitCode:0},content:""}})}/>);
 expect(screen.getByText("true")).toBeVisible();expect(screen.getByText("exit 0")).toBeVisible();expect(screen.queryByText("Short summary")).not.toBeInTheDocument();
 result.rerender(<ToolDetailBody call={call({card:"generic"},{status:"failed",detail:{native_call:{card:"terminal",title:"blocked command"},native_view:{card:"generic",content:[{type:"text",text:"```console\nPermission denied\n```"}]}}})}/>);
 expect(screen.getByText("Permission denied")).toBeVisible();expect(screen.queryByText(/```/)).not.toBeInTheDocument();
});
it("preserves unknown-tool inputs and existing memory/skill details",()=>{
 const result=render(<ToolDetailBody call={{id:"custom",name:"custom",status:"completed",input:{question:"Original input"},detail:{answer:"Final answer"}}}/>);
 expect(screen.getByText("调用参数")).toBeInTheDocument();expect(screen.getByText("Original input")).toBeInTheDocument();expect(screen.getByText("Final answer")).toBeVisible();
 result.rerender(<ToolDetailBody call={{id:"m",name:"memory",status:"completed",input:{action:"add",target:"user",content:"Saved preference"},detail:{success:true,target:"user",action:"add"}}}/>);
 expect(screen.getByText("Saved preference")).toBeVisible();
 result.rerender(<ToolDetailBody call={{id:"s",name:"skill_manage",status:"completed",input:{action:"list"},detail:{skills:[{name:"review",description:"Review code"}]}}}/>);
 expect(screen.getByText("review")).toBeVisible();expect(screen.getByText("Review code")).toBeVisible();
});
