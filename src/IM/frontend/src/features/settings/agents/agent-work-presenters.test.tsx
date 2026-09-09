import {render,screen,fireEvent} from "@testing-library/react";
import {beforeEach,expect,it} from "vitest";
import {setLanguage} from "../../../i18n";
import {WorkTool,WorkUsage} from "./agent-work-presenters";
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
