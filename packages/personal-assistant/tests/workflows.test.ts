import { expect, it } from "vitest";
import { NodeStore } from "../src/store.js";
import { WorkflowResults } from "../src/workflows.js";
import type { AgentConfiguration, RelayInput } from "@nano/product-contracts";
it("hands persisted results to the original single-thread binding and checkpoints only after durable acceptance", async () => {
  const store = new NodeStore(":memory:", "owner");
  const calls: string[] = [];
  const received: { sessionId: string; input: RelayInput }[] = [];
  const binding = {
    sessionId: "old",
    conversationId: "chat",
    agentId: "a",
    ownerId: "owner",
    cwd: "/tmp",
    revision: "1",
  };
  store.bind(binding);
  store.receive("old", {
    agent_id: "a",
    conversation_id: "chat",
    relay_task_id: "inbound",
    idempotency_key: "inbound",
    metadata: {
      conversation_type: "direct",
      external_reply: "feishu-original",
    },
    message: {
      id: "human",
      content: "research",
      sender_type: "user",
      sender_user_id: "owner",
      attachments: [],
    },
  });
  store.reset(binding, { ...binding, sessionId: "new" }, "reset");
  let acknowledged = false;
  let fail = true;
  const service = new WorkflowResults({
    store,
    agents: [{ agentId: "a", mode: "single_thread" } as AgentConfiguration],
    runtime: {
      onNotification: () => () => {},
      async request(method) {
        calls.push(method);
        if (method === "workflow.pending")
          return acknowledged
            ? []
            : [
                {
                  id: "w",
                  parentSessionId: "old",
                  inputIds: ["a:human"],
                  meta: { name: "research", description: "Research" },
                  usage: { outputTokens: 12 },
                  logs: [{ text: "Finished phase" }],
                  startedAt: 1,
                  endedAt: 5,
                  result: {
                    value: { answer: "done" },
                    stopReason: "completed",
                  },
                },
              ];
        if (method === "workflow.acknowledge") acknowledged = true;
      },
    },
    async receive(sessionId, input) {
      if (fail) {
        fail = false;
        throw new Error("offline");
      }
      received.push({ sessionId, input });
    },
    onError: () => {},
  });
  try {
    await expect(service.recover()).rejects.toThrow("offline");
    expect(acknowledged).toBe(false);
    await service.recover();
    expect(received[0]!.sessionId).toBe("old");
    expect(received[0]!.input.metadata.background_returns).toMatchObject([
      {
        workflow_run_id: "w",
        usage: { outputTokens: 12 },
        diagnostics: "Finished phase",
        result: '{"answer":"done"}',
      },
    ]);
    expect(received[0]!.input.message.sender_type).toBe("system");
    expect(received[0]!.input.metadata.external_reply).toBe("feishu-original");
    expect(acknowledged).toBe(true);
    await service.recover();
    expect(received).toHaveLength(1);
  } finally {
    await service.stop();
    store.close();
  }
});

it("keeps Workflow script and description stable when its background launch returns", async () => {
  const { toolPresentation } = await import("../src/presentation.js");
  const input = {
    script: 'return await agent("review");',
    meta: { name: "review", description: "Review the change" },
  };
  const call = {
    seq: 1,
    time: 10,
    type: "tool/call",
    data: { callId: "wf", name: "workflow", arguments: JSON.stringify(input) },
  };
  const result = {
    seq: 2,
    time: 20,
    type: "tool/result",
    data: {
      message: {
        toolCallId: "wf",
        content: [
          {
            type: "text",
            text: JSON.stringify({ runId: "run", status: "running" }),
          },
        ],
      },
    },
  };
  expect(toolPresentation(call, [call])).toMatchObject({
    output: "Review the change",
    detail: { script_preview: input.script },
  });
  expect(toolPresentation(result, [call, result])).toMatchObject({
    status: "completed",
    output: "Review the change",
    detail: { script_preview: input.script, runId: "run", status: "running" },
  });
});

it("keeps global Workflow result fields in the consumed native input", async () => {
  const {projectWorkEvent} = await import('../src/work-projection.js');
  const store=new NodeStore(':memory:','owner');
  store.bind({sessionId:'main',conversationId:'chat',agentId:'a',ownerId:'owner',cwd:'/tmp',revision:'1'});
  let submitted: any;
  const service=new WorkflowResults({store,agents:[{agentId:'a',mode:'global'} as AgentConfiguration],runtime:{onNotification:()=>()=>{},async request(method,params){
    if(method==='workflow.pending')return [{id:'wf',parentSessionId:'main',inputIds:[],meta:{name:'work',description:'Work'},startedAt:1,endedAt:5,result:{stopReason:'completed',value:'done'}}];
    if(method==='session.lookup')return {accepted:false};
    if(method==='session.submit')submitted=params;
  }},receive:async()=>{throw new Error('Wrong delivery path')},onError:()=>{}});
  try {
    await service.recover();
    const event={seq:2,time:2,type:'user/message',data:{...submitted,source:{...submitted.source,kind:'nano-system'}}};
    const start={seq:1,time:1,type:'turn/start',data:{turn:1}};
    expect(projectWorkEvent('main',event,[start,event])).toMatchObject({type:'injection_consumed',turn:1,payload:{background_returns:[{workflow_run_id:'wf',duration_ms:4,status:'completed',result:'"done"'}]}});
  }finally{await service.stop();store.close();}
});
