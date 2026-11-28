import { createInterface } from 'node:readline';
import { appendFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { join } from 'node:path';
import { builtinSkillsRoot, GlobalAgent, InboxStore, NodeStore, TaskContext, type ProductCall } from '@nano/personal-assistant';
import { EvaluationChat } from '@nano/im-server/evaluation';
import { NanoDolphinBenchController, type DolphinBenchArm, type DolphinBenchHostOptions } from '@nano/dsh-integration/evaluation';
import type { EvaluationLimits, RelayInput } from '@nano/product-contracts';

function zonedOffsetMs(ms: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(ms));
  const get = (type: string) => Number(parts.find(part => part.type === type)?.value ?? '0');
  const hour = get('hour');
  return Date.UTC(get('year'), get('month') - 1, get('day'), hour === 24 ? 0 : hour, get('minute'), get('second'))
    - Math.floor(ms / 1000) * 1000;
}

function parseIsoMs(raw: string, timeZone: string): number {
  if (raw.length === 10 && /^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const [year, month, day] = raw.split('-').map(Number) as [number, number, number];
    const naive = Date.UTC(year, month - 1, day, 9, 0, 0);
    const first = naive - zonedOffsetMs(naive, timeZone);
    return naive - zonedOffsetMs(first, timeZone);
  }
  const ms = Date.parse(raw);
  if (Number.isNaN(ms)) throw new Error(`Invalid DolphinBench ISO date: ${raw}`);
  return ms;
}

function makeProductFactory(timeZone: string): DolphinBenchHostOptions['createProduct'] {
  return options => {
  const { configuration: config, binding, runtime, directory, deliver, nodeId } = options;
  const identity = config.personal!;
  const chat = new EvaluationChat({
    path: join(directory, 'chat.sqlite'),
    snapshot: options.chatSnapshot,
    nodeId,
    agentId: config.agentId,
    ownerId: identity.ownerId,
    bindingId: identity.bindingId,
    conversationId: identity.conversationId,
    rootSessionId: binding.sessionId,
    startTime: options.startTime,
  });
  const store = new NodeStore(join(directory, 'node.sqlite'), identity.ownerId);
  const inbox = new InboxStore(join(directory, 'inbox.sqlite'));
  store.bind({ ...binding, conversationId: `global:${config.agentId}` });
  const target = identity.conversationId;
  let currentTurnTime = options.startTime;

  const relay: ConstructorParameters<typeof GlobalAgent>[0]['relay'] = {
    ready: true,
    async request(type, args) {
      const ok = (result: unknown = {}) => ({ type: `${type}.result`, payload: { ok: true, result } });
      if (type === 'agent.session.ensure' || type === 'node.delivery_receipt') return ok();
      if (type === 'pa.observations.read') return ok({ items: [], has_more: false });
      if (type === 'pa.incidents.pending') return ok(chat.pendingIncidents());
      if (type === 'pa.sources' && args.action === 'list') return ok(chat.sources());
      if (type === 'pa.source.admit') {
        return ok({
          allowed: args.conversation_id === target,
          is_owner: true,
          delivery: 'participant',
          conversation_type: 'direct',
          channel: 'web',
        });
      }
      if (type === 'agent.message') {
        if (args.to !== `conversation:${target}` || typeof args.text !== 'string') {
          throw new Error('Target is outside the connected owner chat');
        }
        const message = chat.append('assistant', args.text, currentTurnTime);
        await deliver(args.text);
        return { type: 'ack', payload: { message_id: message.id, conversation_id: target } };
      }
      if (type === 'conversation.query') return ok(chat.query(args));
      if (type === 'task.context.sync') return ok(chat.taskContext(args));
      throw new Error(`Operation is unavailable in isolated DolphinBench chat: ${type}`);
    },
  };

  const product = new GlobalAgent({
    nodeId,
    ownerId: identity.ownerId,
    agents: [config],
    store,
    inbox,
    runtime,
    relay,
    image: async () => { throw new Error('This chat has no image attachments'); },
    onError: error => appendFileSync(join(directory, 'product-errors.log'), String(error) + '\n'),
  });
  const taskContext = new TaskContext({
    nodeId,
    ownerId: identity.ownerId,
    agents: [config],
    store,
    inbox,
    runtime,
    relay,
    refreshSources: agentId => product.prepareSystemContext(agentId),
    settlePersonalInputs: (agentId, sessionId) => product.settleSyncedTaskContext(agentId, sessionId),
  });
  product.attachTaskContext(taskContext);

  return {
    importSession: session => chat.importSession(session),
    snapshot: path => chat.snapshot(path),
    async submit(question) {
      currentTurnTime = parseIsoMs(question.date, timeZone);
      const saved = chat.append('user', question.text, currentTurnTime);
      const createdAtIso = new Date(currentTurnTime).toISOString();
      const message: RelayInput['message'] = {
        id: saved.id,
        content: question.text,
        sender_type: 'user',
        sender_user_id: identity.ownerId,
        sender: { display_name: 'Owner' },
        attachments: [],
        created_at: createdAtIso,
      };
      const relayId = randomUUID();
      await product.receive({
        agent_id: config.agentId,
        conversation_id: target,
        relay_task_id: relayId,
        idempotency_key: relayId,
        metadata: { conversation_type: 'direct', conversation_title: 'Personal Assistant', channel: 'web' },
        message,
      });
      return `inbox-wake:${config.agentId}:${inbox.admittedWake(config.agentId)}`;
    },
    call: value => product.call(value as ProductCall),
    taskContext: {
      prepare: value => taskContext.prepare(value as Parameters<TaskContext['prepare']>[0]),
      commit: value => taskContext.commit(value as Parameters<TaskContext['commit']>[0]),
    },
    async close() {
      try { await product.stop(); } finally { inbox.close(); store.close(); chat.close(); }
    },
  };
  };
}

interface InitPayload {
  baseURL: string;
  api: 'anthropic-messages' | 'openai-completions';
  apiKeyEnv: string;
  model: string;
  contextWindow: number;
  reasoningEffort: string;
  timeZone: string;
  mcpToolNames?: string[];
  saveRawRequests?: boolean;
  dreamMinIntervalDays?: number;
}

let controller: NanoDolphinBenchController | undefined;

async function dispatch(method: string, params: Record<string, unknown>): Promise<unknown> {
  if (method === 'init') {
    const cfg = params as unknown as InitPayload;
    const levels = ['low', 'medium', 'high', 'xhigh', 'max'];
    const isAnthropic = cfg.api === 'anthropic-messages';
    controller = new NanoDolphinBenchController({
      provider: 'dolphinbench-eval',
      model: cfg.model,
      reasoningEffort: cfg.reasoningEffort,
      builtinSkillsRoot,
      timeZone: cfg.timeZone,
      mcpToolNames: cfg.mcpToolNames,
      saveRawRequests: cfg.saveRawRequests,
      dreamMinIntervalDays: cfg.dreamMinIntervalDays,
      environment: {
        [cfg.apiKeyEnv]: process.env[cfg.apiKeyEnv] ?? 'nano-local-proxy',
      },
      providerPatch: [{
        id: 'llm-pi-ai',
        config: {
          providers: {
            'dolphinbench-eval': {
              api: cfg.api,
              baseURL: cfg.baseURL,
              apiKeyEnv: cfg.apiKeyEnv,
              streamIdleTimeoutMs: 90_000,
              defaultInput: ['text', 'image'],
              retryPolicy: {
                mode: 'normal',
                maxRetries: 6,
                backoff: { initialDelayMs: 2000, maxDelayMs: 30000, jitterRatio: 0.2 },
              },
              models: [{
                id: cfg.model,
                contextWindow: cfg.contextWindow,
                reasoningEfforts: Object.fromEntries(levels.map(level => [level, level])),
                ...(isAnthropic ? { compat: { forceAdaptiveThinking: true } } : {}),
              }],
            },
          },
        },
      }],
      createProduct: makeProductFactory(cfg.timeZone),
    });
    return { ok: true };
  }
  if (!controller) throw new Error('Controller not initialized; call init first');
  if (method === 'openIngestion') {
    return controller.openIngestion(
      params.stateDir as string,
      params.startTimeMs as number,
      params.limits as EvaluationLimits,
    );
  }
  if (method === 'ingestSession') {
    return controller.ingestSession(params as Parameters<NanoDolphinBenchController['ingestSession']>[0]);
  }
  if (method === 'freezeIngestion') {
    return controller.freezeIngestion(
      params.persona as string,
      params.sealedDir as string,
      params.finalNightMs as number | undefined,
    );
  }
  if (method === 'runTest') {
    return controller.runTest(params as Parameters<NanoDolphinBenchController['runTest']>[0] & { arm: DolphinBenchArm });
  }
  if (method === 'close') {
    await controller.closeIngestion();
    return { ok: true };
  }
  throw new Error(`Unknown method: ${method}`);
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
(async () => {
  for await (const line of rl) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    let reqId: number | string | null = null;
    try {
      const req = JSON.parse(trimmed) as { id: number | string; method: string; params?: Record<string, unknown> };
      reqId = req.id;
      const result = await dispatch(req.method, req.params ?? {});
      process.stdout.write(JSON.stringify({ id: reqId, ok: true, result }) + '\n');
    } catch (error) {
      process.stdout.write(JSON.stringify({ id: reqId, ok: false, error: error instanceof Error ? error.stack ?? error.message : String(error) }) + '\n');
    }
  }
  if (controller) await controller.closeIngestion();
})();
