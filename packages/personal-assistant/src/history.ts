import type {
  AgentConfiguration,
  RuntimePort,
  SessionBinding,
} from "@nano/product-contracts";
import type { NodeStore } from "./store.js";

interface Source {
  conversation_id: string;
  source_agent_id: string;
  external_source?: string;
  external_chat_id?: string;
}
interface Options {
  store: NodeStore;
  runtime: RuntimePort;
  agents: AgentConfiguration[];
  externalConversation?(
    agentId: string,
    source: string,
    chatId: string,
  ): string | undefined;
}
const text = (value: unknown) =>
  typeof value === "string" ? value.trim() : "";
const error = (error_code: string, message: string) => ({
  error_code,
  message,
});

/** Resolves trusted IM controls to node-owned bindings; never runs a distillation itself. */
export class ConversationHistory {
  constructor(private readonly options: Options) {}
  private source(value: Source): SessionBinding | undefined {
    const direct = this.options.store.bindingFor(
      value.source_agent_id,
      value.conversation_id,
    );
    if (direct) return direct;
    const external =
      value.external_source &&
      value.external_chat_id &&
      this.options.externalConversation?.(
        value.source_agent_id,
        value.external_source,
        value.external_chat_id,
      );
    return external
      ? this.options.store.bindingFor(value.source_agent_id, external)
      : undefined;
  }
  async fork(
    payload: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const agentId = text(payload.agent_id);
    const destination = text(payload.new_conversation_id);
    const messageId = text(
      (payload.fork_point as { message_id?: unknown } | undefined)?.message_id,
    );
    if (!agentId || !destination || !messageId)
      return { ok: false, error: "Invalid fork request" };
    const source = this.source({
      conversation_id: text(payload.source_conversation_id),
      source_agent_id: agentId,
      external_source: text(payload.source_external_source),
      external_chat_id: text(payload.source_external_chat_id),
    });
    if (!source)
      return {
        ok: false,
        error:
          "Native source session is unavailable; legacy history cannot be forked",
      };
    try {
      const { conversationId: _, ...binding } = source;
      await this.options.runtime.request("session.ensure", binding);
      const result = (await this.options.runtime.request("session.fork", {
        sessionId: source.sessionId,
        messageId,
        operationId: `fork:${agentId}:${destination}`,
      })) as {
        sessionId: string;
        revision: string;
        idMap: Record<string, string>;
      };
      const actual = this.options.store.bind({
        ...source,
        sessionId: result.sessionId,
        revision: result.revision,
        conversationId: destination,
      });
      if (actual.sessionId !== result.sessionId)
        throw new Error("Destination conversation already has another session");
      return {
        ok: true,
        new_session_id: result.sessionId,
        id_map: result.idMap,
      };
    } catch (cause) {
      return { ok: false, error: String(cause) };
    }
  }
  async distill(
    payload: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const agentId = text(payload.execution_agent_id);
    const scope = text(payload.target_scope);
    if (
      !agentId ||
      !["agent", "global"].includes(scope) ||
      !Array.isArray(payload.sources) ||
      !payload.sources.length
    )
      return error(
        "invalid_request",
        "Distill request requires an execution Agent, scope and sources",
      );
    const config = this.options.agents.find(
      (agent) => agent.agentId === agentId,
    );
    if (!config)
      return error("execution_unavailable", "Execution Agent is unavailable");
    const capabilities = (await this.options.runtime.request(
      "configuration.selection",
      { agentId, cwd: config.workspace },
    )) as { tools: string[]; skills: { name: string }[] };
    if (
      !capabilities.skills.some(
        (skill) => skill.name === "conversation-skill-distiller",
      )
    )
      return error(
        "distiller_unavailable",
        "Execution Agent lacks the selected distiller Skill",
      );
    if (!capabilities.tools.includes("skill"))
      return error(
        "skill_view_unavailable",
        "Execution Agent lacks the native skill tool",
      );
    const paths: string[] = [];
    for (const item of payload.sources) {
      if (!item || !text(item.conversation_id) || !text(item.source_agent_id))
        return error("invalid_request", "Distill source is invalid");
      const binding = this.source(item as Source);
      if (!binding)
        return error(
          "source_unavailable",
          "Native source binding is unavailable; legacy history cannot be distilled",
        );
      try {
        const exported = (await this.options.runtime.request("session.export", {
          sessionId: binding.sessionId,
        })) as { path: string };
        paths.push(exported.path);
      } catch {
        return error(
          "source_unavailable",
          "Source history export is unavailable",
        );
      }
    }
    return {
      prompt: [
        "/skill:conversation-skill-distiller",
        "source_jsonl_paths:",
        ...paths.map((path) => `  ${path}`),
        `execution_agent_id: ${agentId}`,
        `target_scope: ${scope}`,
        "",
        `请基于上述会话 transcript，总结我反复使用且值得复用的工作方式，直接生成并写入一个 ${scope} 级 skill。重点关注：`,
        "- 触发这个 skill 的场景",
        "- 应遵循的步骤/检查点",
        "- 失败或边界情况",
        "如果这些会话不足以形成稳定模式，请说明原因，不要创建 skill。",
      ].join("\n"),
    };
  }
}
