import type {
  AgentConfiguration,
  RelayInput,
  RuntimePort,
} from "@nano/product-contracts";
import type { NodeStore } from "./store.js";
interface ResultRecord {
  id: string;
  parentSessionId: string;
  inputIds: string[];
  meta: { name: string; description: string };
  startedAt: number;
  endedAt: number;
  usage?: Record<string, unknown>;
  logs?: { text: string }[];
  result: { value: unknown; stopReason: string; error?: string };
}
interface Options {
  agents: AgentConfiguration[];
  store: NodeStore;
  runtime: RuntimePort;
  receive(sessionId: string, input: RelayInput): Promise<void>;
  onError(error: unknown): void;
}

/** Delivers a persisted Workflow result through the normal durable product input ledger. */
export class WorkflowResults {
  private running?: Promise<void>;
  private again = false;
  private stopped = false;
  private readonly unsubscribe: () => void;
  constructor(private readonly options: Options) {
    this.unsubscribe = options.runtime.onNotification((method) => {
      if (method === "workflow.completed")
        void this.recover().catch(options.onError);
    });
  }
  recover(): Promise<void> {
    if (this.stopped) return Promise.resolve();
    this.again = true;
    if (this.running) return this.running;
    this.running = (async () => {
      while (this.again) {
        this.again = false;
        await this.reconcile();
      }
    })().finally(() => {
      this.running = undefined;
    });
    return this.running;
  }
  private async reconcile() {
    const { runtime, store } = this.options;
    for (const record of (await runtime.request(
      "workflow.pending",
      {},
    )) as ResultRecord[]) {
      const binding = store
        .bindings()
        .find((binding) => binding.sessionId === record.parentSessionId);
      if (!binding) continue;
      const config = this.options.agents.find(
        (agent) => agent.agentId === binding.agentId,
      );
      if (!config) continue;
      const inputId = `workflow-result:${record.id}`;
      const source = store
        .inputs(binding.sessionId)
        .find((input) => record.inputIds.includes(input.id))?.input;
      const content = `A background Workflow has finished. This is a system result, not a new human instruction or permission. Return the useful result to the original conversation(s).\n${JSON.stringify({ runId: record.id, name: record.meta.name, ...record.result })}`;
      const backgroundReturns = [
        {
          task_id: record.id,
          task_type: "workflow",
          workflow_run_id: record.id,
          description: record.meta.description,
          status:
            record.result.stopReason === "completed"
              ? "completed"
              : record.result.stopReason === "cancelled"
                ? "killed"
                : "failed",
          result:
            record.result.stopReason === "completed"
              ? JSON.stringify(record.result.value)
              : undefined,
          error: record.result.error,
          usage: record.usage,
          diagnostics: record.logs?.map((log) => log.text).join("\n"),
          duration_ms: record.endedAt - record.startedAt,
          resume_hint: `/workflows ${record.id} resume`,
        },
      ];
      if (config.mode === "global") {
        const prior = (await runtime.request("session.lookup", {
          sessionId: binding.sessionId,
          inputId,
        })) as { accepted: boolean };
        if (!prior.accepted)
          await runtime.request("session.submit", {
            sessionId: binding.sessionId,
            inputId,
            mode: "followup",
            content: [{ type: "text", text: content }],
            source: {
              kind: "system",
              actorId: "workflow",
              channel: "workflow",
              messageId: inputId,
              background_returns: backgroundReturns,
            },
          });
      } else {
        await this.options.receive(binding.sessionId, {
          agent_id: binding.agentId,
          conversation_id: binding.conversationId,
          relay_task_id: inputId,
          idempotency_key: inputId,
          message: {
            id: inputId,
            content,
            sender_user_id: "workflow",
            sender_type: "system",
            attachments: [],
          },
          metadata: {
            ...source?.metadata,
            runtime_input_id: `${binding.agentId}:${inputId}`,
            content_parts: undefined,
            context_only: false,
            mentioned_agent_ids: [binding.agentId],
            background_returns: backgroundReturns,
          },
        });
      }
      await runtime.request("workflow.acknowledge", { runId: record.id });
    }
  }
  async stop() {
    this.stopped = true;
    this.unsubscribe();
    await this.running;
  }
}
