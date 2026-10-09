import {
  freezeMessage,
  MessageId,
  type UserMessage,
} from "@deepseek-ai/dsh-llm";
import type { Context } from "@deepseek-ai/cordis";
import type { NanoWorkflowEngine } from "./engine.js";
import type { WorkflowMeta } from "@deepseek-ai/dsh-workflow";
import type { AgentConfiguration } from "../index.js";

declare module "@deepseek-ai/dsh-llm" {
  interface MessageSourceMap {
    "nano-workflow-invocation": {
      kind: "nano-workflow-invocation";
      form: "instructions";
      name: string;
    };
  }
}

/** The only model-facing Workflow launch path; selection uses native tools scopes. */
export function registerWorkflowTool(
  ctx: Context,
  engine: NanoWorkflowEngine,
  configuration: (
    agent: import("@deepseek-ai/dsh-agent").Agent,
  ) => AgentConfiguration,
) {
  const instructions =
    "Only launch a Workflow when the human explicitly requests multi-agent orchestration or an application reminder confirms Ultracode is on. A trusted human +500k or +2m sets the shared parent/child output-token target for this logical turn. Run JavaScript orchestration in the background. Provide meta {name,description} and script (top-level await and return), or name/scriptPath, or resumeFromRunId. Primitives: await agent(prompt,{label?,phase?,provider?,model?,reasoningEffort?,schema?}); await parallel([()=>agent(...)]); await pipeline(items,...stages), stages get (previous,item,index) and advance independently; await phase(title); await log(text); await workflow(nameOrPath,args) allows one nesting level; await budget.spent()/remaining() (null means unlimited). Omit reasoningEffort to inherit the parent selection; never invent an unsupported effort. Child failure returns null; inspect action read calls[].error for its diagnostic before retrying. Host/cap errors fail the workflow. parallel preserves input order. A child cannot launch agents or workflows. Max 8 concurrent and 1000 total agents, 4096 items per combinator. Returns runId immediately; use action read/control to inspect, pause/resume/stop or restart_child/stop_child by ordinal. Resume of a terminal run creates a new run and reuses its matching completed prefix; completed side effects are not undone. Saving definitions uses action save with project/personal scope.";
  ctx.on("agent/pre-step", async ({ agent, messages }, next) => {
    const decision = await next();
    if (decision.kind === "reject" || !ctx.tools.get("workflow", agent))
      return decision;
    const inputs = [
      ...messages
        .filter((message) => message.source.kind === "nano-human")
        .map((message) => ({
          id: message.id as string,
          text: message.content
            .filter((block) => block.type === "text")
            .map((block) => block.text)
            .join("\n"),
        })),
      ...ctx.nanoApproval.sources.humanInputs(agent),
    ];
    const seen = new Set(
      agent.session
        .snapshotEvents()
        .flatMap((event) =>
          event.type === "user/message" ? [event.data.id as string] : [],
        ),
    );
    const additions: UserMessage[] = [];
    for (const input of inputs) {
      const match =
        /^(?:\[[^\]]*\]\s*)*\/([a-z0-9][a-z0-9:._-]*)(?:\s+([\s\S]*))?$/.exec(
          input.text.trim(),
        );
      if (
        !match ||
        ["new", "stop", "workflows", "effort", "compact"].includes(match[1]!)
      )
        continue;
      const definition = (await engine.catalog(agent).list()).find(
        (item) => item.name === match[1],
      );
      if (!definition) continue;
      const id = `nano-workflow:${input.id}:${definition.name}`;
      if (seen.has(id)) continue;
      seen.add(id);
      let args: unknown = match[2] ?? null;
      try {
        args = JSON.parse(match[2]!);
      } catch {}
      additions.push(
        freezeMessage({
          id: MessageId(id),
          role: "user",
          source: {
            kind: "nano-workflow-invocation",
            form: "instructions",
            name: definition.name,
          },
          content: [
            {
              type: "text",
              text: `The human explicitly selected a saved Workflow. Launch it once through the workflow tool with ${JSON.stringify({ name: definition.name, args })}. Preserve normal approval and background-result handling.`,
            },
          ],
        }),
      );
    }
    return additions.length
      ? { ...decision, messages: [...decision.messages, ...additions] }
      : decision;
  });
  ctx.tools.register({
    name: "workflow",
    description: instructions,
    parameters: {
      type: "object",
      properties: {
        action: {
          type: "string",
          enum: ["launch", "read", "control", "list", "save"],
        },
        script: { type: "string" },
        scriptPath: { type: "string" },
        name: { type: "string" },
        meta: {
          type: "object",
          properties: {
            name: { type: "string" },
            description: { type: "string" },
            whenToUse: { type: "string" },
          },
          required: ["name", "description"],
          additionalProperties: true,
        },
        args: {},
        resumeFromRunId: { type: "string" },
        runId: { type: "string" },
        control: {
          type: "string",
          enum: ["pause", "resume", "stop", "restart_child", "stop_child"],
        },
        ordinal: { type: "integer", minimum: 1 },
        scope: { type: "string", enum: ["project", "personal"] },
      },
      additionalProperties: false,
    },
    output: {
      schema: { type: "object", additionalProperties: true },
      render: (_args, result) => [
        { type: "text", text: JSON.stringify(result) },
      ],
    },
    execute: async (raw, exec) => {
      const args = raw as {
        action?: string;
        script?: string;
        scriptPath?: string;
        name?: string;
        meta?: WorkflowMeta;
        args?: unknown;
        resumeFromRunId?: string;
        runId?: string;
        control?: string;
        ordinal?: number;
        scope?: "project" | "personal";
      };
      const parent = exec.agent!;
      if (args.action === "list")
        return { definitions: await engine.catalog(parent).list() };
      if (args.action === "read")
        return { runs: await engine.read(parent, args.runId) };
      if (args.action === "control")
        return engine.control(parent, args.runId!, args.control!, args.ordinal);
      if (args.action === "save")
        return engine
          .catalog(parent)
          .save(args.meta!, args.script!, args.scope!);
      let script = args.script;
      let meta = args.meta;
      let input = args.args;
      if (args.resumeFromRunId) {
        const previous = (await engine.read(parent, args.resumeFromRunId))[0]!;
        script ??= previous.script;
        meta ??= previous.meta;
        if (input === undefined) input = previous.args;
      }
      if (args.name || args.scriptPath) {
        const definition = await engine
          .catalog(parent)
          .resolve(args.scriptPath ?? args.name!);
        script = definition.script;
        meta = definition.meta;
      }
      exec.signal.throwIfAborted();
      const run = await engine.launch({
        parent,
        script: script!,
        meta: meta!,
        args: input,
        resumeFromRunId: args.resumeFromRunId,
        outputTokenTarget: configuration(parent).workflow?.outputTokenTarget,
      });
      return { runId: run.id, status: "running", name: run.meta.name };
    },
  });
  ctx.systemPrompt.section({
    name: "nano-workflow-activation",
    order: 806,
    text: ({ scope, agent }) => {
      if (!agent || !ctx.tools.get("workflow", scope)) return "";
      if (ctx.nanoModels.ultracode(agent))
        return "Ultracode is on: use Workflow for every substantive task and optimize for exhaustive correctness. Solo work is appropriate for conversational turns and trivial edits. This standing opt-in does not grant child tools additional permissions.";
      return ctx.nanoApproval.sources
        .humanText(agent)
        .toLowerCase()
        .includes("ultracode")
        ? "The human included ultracode in the current input, opting this turn into multi-agent orchestration. Use the workflow tool to fulfill the request."
        : "";
    },
  });
  ctx.systemPrompt.section({
    name: "nano-workflow",
    order: 805,
    text: ({ scope, agent }) =>
      ctx.tools.get("workflow", scope)
        ? instructions +
          (agent
            ? ` Size guideline: ${configuration(agent).workflow?.sizeGuideline ?? "medium"} (small: under 5 agents; medium: under 15; large: under 50; unrestricted: no size guidance). This is guidance, not an admission limit.`
            : "")
        : "",
  });
}
