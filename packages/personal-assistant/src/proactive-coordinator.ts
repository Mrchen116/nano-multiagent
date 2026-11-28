import {
  definitionsForRole,
  effectiveFeatures,
  type AgentConfiguration,
  type ProactiveSyncObservationsInput,
  type ProactiveSyncObservationsResult,
  type RuntimePort,
  type SessionBinding,
} from '@nano/product-contracts';
import type { NodeStore } from './store.js';
import type { InboxStore } from './inbox.js';

export const DEFAULT_PROACTIVE_REVIEW_QUIET_MS = 12 * 60_000;
export const DEFAULT_PROACTIVE_NIGHTLY_QUIET_MS = 30 * 60_000;
export const PROACTIVE_NIGHT_START_HOUR = 3;
export const PROACTIVE_NIGHT_END_HOUR = 6;

export interface ProactiveCoordinatorOptions {
  ownerId: string;
  agents: AgentConfiguration[];
  store: NodeStore;
  inbox: InboxStore;
  runtime: RuntimePort;
  binding(agent: AgentConfiguration): Promise<SessionBinding>;
  available(agentId: string): boolean;
  syncObservations(agent: AgentConfiguration, binding: SessionBinding): Promise<void>;
  onError(error: unknown): void;
  reviewQuietMs?: number;
  nightlyQuietMs?: number;
}

interface ZonedParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
}

/** Resolve a canonical IANA timezone from owner preference or host system clock. */
export function resolveEffectiveTimeZone(ownerTimezone?: string): string {
  for (const candidate of [ownerTimezone, Intl.DateTimeFormat().resolvedOptions().timeZone, 'UTC']) {
    if (!candidate) continue;
    try {
      return new Intl.DateTimeFormat('en-US', { timeZone: candidate }).resolvedOptions().timeZone;
    } catch {
      // Ignore invalid cached strings and fall back to host timezone.
    }
  }
  return 'UTC';
}

function zonedParts(ms: number, timeZone: string): ZonedParts {
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
  return {
    year: get('year'),
    month: get('month'),
    day: get('day'),
    hour: hour === 24 ? 0 : hour,
    minute: get('minute'),
    second: get('second'),
  };
}

/** Format an instant as a wall-clock ISO timestamp with explicit numeric offset in timeZone. */
export function formatZonedIso(ms: number, timeZone: string): string {
  const p = zonedParts(ms, timeZone);
  const utcEquivalent = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  const offsetMinutes = Math.round((utcEquivalent - Math.floor(ms / 1000) * 1000) / 60_000);
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const abs = Math.abs(offsetMinutes);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${String(p.year).padStart(4, '0')}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}:${pad(p.second)}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

/** Compute the natural-day cycle slot anchored at local anchorHour ([D 03:00, D+1 03:00) -> D). */
export function nightlyCycleSlotKey(ms: number, timeZone: string, anchorHour = PROACTIVE_NIGHT_START_HOUR): string {
  const p = zonedParts(ms, timeZone);
  const dayShift = p.hour < anchorHour ? -1 : 0;
  const shifted = new Date(Date.UTC(p.year, p.month - 1, p.day + dayShift));
  return shifted.toISOString().slice(0, 10);
}

/** Render the hidden post-quiet lightweight accounting prompt appended to a Global root session. */
export function renderProactiveReviewWake(input: { localTime: string; quietMinutes: number; quietHours: boolean; personal?: boolean }): string {
  const personal = input.personal ?? true;
  return [
    `<proactive-review-wake local_time="${input.localTime}" quiet_minutes="${input.quietMinutes}" quiet_hours="${input.quietHours}">`,
    personal
      ? 'guidance: Conversation has been quiet (lightweight accounting pass). Honor MEMORY.md "## 主动性与介入偏好" alongside any <updated-formal-memory> and <proactive-policy> attached in this context window ("免打扰禁区" / No-Intrusion Boundaries receive zero task bookkeeping, and any custom quiet-hours rule in "触达时机与汇总方式" / Timing & Delivery Cadence overrides the default quiet_hours flag); never read knowledge/proactivity-signals.md. Only update already-explicit commitments, progress transitions, or item-specific native schedules in your private task_graph and schedule tools; do not brainstorm speculative proposals or rearrange tomorrow morning briefings in this pass. If outside effective quiet hours and you find an urgent conflict due within roughly one hour, you may send one brief heads-up; otherwise do NOT call send_message and end this turn silently.'
      : 'guidance: Conversation activity has settled (lightweight accounting pass). Honor ROLE.md, MEMORY.md "## 主动性与介入偏好", and any <updated-formal-memory> or <proactive-policy> attached in this context window (enforce zero bookkeeping on "免打扰禁区" / collaborator-scoped opt-outs, and honor any custom quiet-hours rule in "触达时机与汇总方式"); never read knowledge/proactivity-signals.md. Only update already-explicit task progress, deadlines, or item-specific native schedules in each matter\'s originating conversation task_graph and schedule tools—never move private DM matters into group boards or vice versa, and do not brainstorm speculative proposals in this pass. If outside effective quiet hours and you spot an urgent role-scoped conflict due within roughly one hour, you may send one concise heads-up to that originating conversation/thread; otherwise do NOT call send_message and end this turn silently.',
    '</proactive-review-wake>',
  ].join('\n');
}

/** Render the hidden nightly deep-planning prompt appended to a Global root session after Dreaming. */
export function renderProactiveNightlyWake(input: { localTime: string; quietMinutes: number; quietHours: boolean; personal?: boolean }): string {
  const personal = input.personal ?? true;
  return [
    `<proactive-nightly-wake local_time="${input.localTime}" quiet_minutes="${input.quietMinutes}" quiet_hours="${input.quietHours}">`,
    personal
      ? 'guidance: Nightly deep planning pass (once per night while the owner is resting). 1) Strictly honor all four calibration buckets in "## 主动性与介入偏好" (or "## Proactive & Intervention Preferences") of the latest MEMORY.md alongside ROLE.md and any <updated-formal-memory> / <proactive-policy> attached in this context window—follow through and prepare ahead on "积极盯紧与提前备料", keep "低打扰挂卡与静默跟进" as silent candidate cards without chat interruptions, enforce zero task cards and zero nudges on "免打扰禁区", and match morning timing/granularity in "触达时机与汇总方式" (never read knowledge/proactivity-signals.md); 2) Review today\'s new conversations (including evening reflections and late-night supplements) and active goal graphs, perform read-only verification anchored to each root goal\'s objective, prepare substantive candidate points for tomorrow\'s active goals (write longer drafts to workspace files if helpful), and close resolved or stale proposed cards first. Remember that status="proposed" is a non-intrusive candidate offer (Approve or Stash to backlog), NOT an active todo commitment: whenever today\'s conversation included an undecided project/product spark outside non-proposal boundaries or an active goal where you can execute a concrete helper deliverable on approval (even if the main milestone belongs to the owner), create 1-3 high-signal status="proposed" cards in the owner\'s private conversation (assigning yourself when you will execute it, with one cohesive description stating why it matters and what concrete step will run upon approval); if today had only casual small talk or routine greetings with no new project spark or actionable goal frontier, create 0 proposed cards; 3) Inspect schedule_list: if the owner already has a recurring morning schedule, do NOT create another morning alarm—save the prepared summary/file paths and TaskCardRefs ({graph_id, node_id}, including any newly created proposed cards) in notes under [Pending Morning Brief] so tomorrow morning\'s scheduled turn delivers them together in one message and clears the pending handoff; if no morning schedule exists, create a one-shot morning schedule (e.g. 09:00 local time, or the owner\'s preferred morning time in MEMORY.md) ONLY when tonight produced substantive new preparation or new proposed cards (zero new value = zero alarm). Quiet hours are active: do NOT call send_message; finish this turn silently.'
      : 'guidance: Nightly role-driven planning pass (once per night during quiet hours). 1) Honor ROLE.md, all four calibration buckets in "## 主动性与介入偏好" (or "## Proactive & Intervention Preferences") of the latest MEMORY.md, and any <updated-formal-memory> / <proactive-policy> attached in this context window—respecting both role-wide standing rules and collaborator/conversation-scoped boundaries, following relative links to entities/, projects/, or knowledge/proactivity-policy.md when needed, and never reading knowledge/proactivity-signals.md; 2) Review today\'s new conversations across joined groups/threads and 1-on-1 DMs alongside active goal graphs, perform read-only verification within your standing authority (writing longer drafts or reports to workspace files if helpful), close resolved or stale proposed cards first, and create at most 1-3 high-signal status="proposed" candidate cards strictly in each matter\'s originating conversation_id (group goal -> that group/goal graph with proposed_for_user_id set to the goal/module owner u_xxxxxx; 1-on-1 DM -> that exact DM without leaking to groups; net-new ROLE.md duty with no prior chat -> its target business group, or your bound administrator\'s DM only if unassociated with any group; casual chat with no role gap -> 0 cards); 3) Low-noise team delivery: inspect schedule_list—if a target conversation already has a recurring report/check-in schedule, save prepared points/file paths and TaskCardRefs ({graph_id, node_id}) in notes under [Pending Proactive Handoff: <target>] instead of adding another schedule; otherwise leave routine proposed cards silent on the task board (0 morning greetings) and create a one-shot working-hours schedule to the originating conversation/thread ONLY for urgent substantive preparation needed tomorrow or a time-sensitive risk/blocker within your role. Quiet hours are active: do NOT call send_message; finish this turn silently.',
    '</proactive-nightly-wake>',
  ].join('\n');
}

/** Check whether proactive_planning is effectively enabled for one Agent configuration. */
export function isProactivePlanningEnabled(config: AgentConfiguration): boolean {
  if (config.mode !== 'global') return false;
  const effective = effectiveFeatures(config.features, definitionsForRole(Boolean(config.personal), undefined, 'global'), {
    tool_allowlist: config.toolAllowlist,
  });
  return effective.proactive_planning === true && effective.task_graph !== false
    && (!config.toolAllowlist || config.toolAllowlist.includes('task_graph'));
}

/** Coordinates PA two-phase quiet review, nightly planning, and pre-schedule observation sync. */
export class ProactiveCoordinator {
  private readonly chains = new Map<string, Promise<void>>();
  private readonly inFlight = new Set<string>();
  private readonly held = new Map<string, string>();
  private timer?: ReturnType<typeof setInterval>;
  private stopping = false;
  private hostClock = false;
  private now: () => number = () => Date.now();
  private readonly reviewQuietMs: number;
  private readonly nightlyQuietMs: number;

  constructor(private readonly options: ProactiveCoordinatorOptions) {
    this.reviewQuietMs = options.reviewQuietMs ?? DEFAULT_PROACTIVE_REVIEW_QUIET_MS;
    this.nightlyQuietMs = options.nightlyQuietMs ?? DEFAULT_PROACTIVE_NIGHTLY_QUIET_MS;
  }

  /** Switch to a monotonic logical clock for isolated E2E verification; disables background polling. */
  useClock(now: () => number): void {
    this.now = now;
    this.hostClock = true;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
  }

  /** Read the current clock instant in Unix milliseconds. */
  clockNow(): number {
    return this.now();
  }

  /** Resolve the active owner/host IANA timezone used across Dreaming and PA proactive windows. */
  effectiveTimeZone(): string {
    return resolveEffectiveTimeZone(this.options.store.ownerTimezone);
  }

  /** Start background wall-clock polling unless driven by an isolated logical clock. */
  start(): void {
    if (this.timer || this.hostClock || this.stopping) return;
    this.timer = setInterval(() => {
      void this.tick().catch(this.options.onError);
    }, 30_000);
    this.timer.unref();
  }

  /** Stop background polling and wait for any in-flight coordinator submissions to settle. */
  async stop(): Promise<void> {
    this.stopping = true;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
    await Promise.allSettled(this.chains.values());
  }

  get busy(): boolean {
    return this.inFlight.size > 0;
  }

  busyFor(agentId: string): boolean {
    return this.inFlight.has(agentId);
  }

  /** Hold proactive wakes while a configuration withdrawal is prepared. */
  hold(agentId: string, operationId: string): boolean {
    const prior = this.held.get(agentId);
    if (prior && prior !== operationId) return false;
    this.held.set(agentId, operationId);
    if (this.inFlight.has(agentId)) {
      this.held.delete(agentId);
      return false;
    }
    return true;
  }

  release(agentId: string, operationId: string): void {
    if (this.held.get(agentId) === operationId) this.held.delete(agentId);
  }

  /** Record human DM, group participation, or admitted owner-relevant observation without self-excitation. */
  recordActivity(agentId: string, atMs = this.now()): void {
    const config = this.options.agents.find(item => item.agentId === agentId);
    if (config?.mode !== 'global') return;
    this.options.store.recordProactiveActivity(agentId, atMs);
  }

  /** Evaluate watermarks across Global-mode Agents at nowMs, preserving watermarks when busy. */
  async tick(nowMs = this.now()): Promise<void> {
    if (this.stopping) return;
    const globalAgents = this.options.agents.filter(agent => agent.mode === 'global');
    await Promise.all(globalAgents.map(config => this.tickAgent(config, nowMs)));
  }

  private tickAgent(config: AgentConfiguration, nowMs: number): Promise<void> {
    const previous = this.chains.get(config.agentId) ?? Promise.resolve();
    const task = previous.catch(() => {}).then(async () => {
      if (this.stopping || this.held.has(config.agentId)) return;
      if (!isProactivePlanningEnabled(config)) return;
      if (!this.options.available(config.agentId) || !this.options.store.lifecycle.allowed(config.agentId)) return;
      const state = this.options.store.proactiveState(config.agentId);
      if (state.lastActivitySeq <= 0 || state.lastActivityAt <= 0) return;

      const timeZone = this.effectiveTimeZone();
      const parts = zonedParts(nowMs, timeZone);
      const quietMs = Math.max(0, nowMs - state.lastActivityAt);
      const quietMinutes = Math.floor(quietMs / 60_000);
      const localTime = formatZonedIso(nowMs, timeZone);
      const quietHours = parts.hour >= 22 || parts.hour < 8;
      const inNightWindow = parts.hour >= PROACTIVE_NIGHT_START_HOUR && parts.hour < PROACTIVE_NIGHT_END_HOUR;
      const cycleKey = nightlyCycleSlotKey(nowMs, timeZone, PROACTIVE_NIGHT_START_HOUR);

      if (inNightWindow && state.lastActivitySeq > state.lastNightlySeq && state.lastNightlyCycle !== cycleKey) {
        if (quietMs < this.nightlyQuietMs) return;
        await this.submitWake(config, {
          channel: 'proactive_nightly',
          inputId: `proactive-nightly:${config.agentId}:${cycleKey}:${state.lastActivitySeq}`,
          text: renderProactiveNightlyWake({ localTime, quietMinutes, quietHours: true, personal: Boolean(config.personal) }),
          onAccepted: () => this.options.store.advanceProactiveNightly(config.agentId, state.lastActivitySeq, cycleKey),
        });
        return;
      }

      if (state.lastActivitySeq > state.lastReviewedSeq && quietMs >= this.reviewQuietMs) {
        await this.submitWake(config, {
          channel: 'proactive_review',
          inputId: `proactive-review:${config.agentId}:${state.lastActivitySeq}`,
          text: renderProactiveReviewWake({ localTime, quietMinutes, quietHours, personal: Boolean(config.personal) }),
          onAccepted: () => this.options.store.advanceProactiveReviewed(config.agentId, state.lastActivitySeq),
        });
      }
    }).catch(this.options.onError).finally(() => {
      if (this.chains.get(config.agentId) === task) this.chains.delete(config.agentId);
    });
    this.chains.set(config.agentId, task);
    return task;
  }

  private async submitWake(
    config: AgentConfiguration,
    wake: { channel: 'proactive_review' | 'proactive_nightly'; inputId: string; text: string; onAccepted: () => void },
  ): Promise<void> {
    this.inFlight.add(config.agentId);
    try {
      await this.options.store.lifecycle.run(config.agentId, undefined, async () => {
        if (this.held.has(config.agentId) || !isProactivePlanningEnabled(config)) return;
        const binding = await this.options.binding(config);
        const prior = await this.options.runtime.request('session.lookup', { sessionId: binding.sessionId, inputId: wake.inputId });
        if (prior.accepted) {
          wake.onAccepted();
          return;
        }
        const submitted = await this.options.runtime.request('session.submit', {
          sessionId: binding.sessionId,
          inputId: wake.inputId,
          mode: 'followup',
          onlyIfIdle: true,
          content: [{ type: 'text', text: wake.text }],
          source: { kind: 'system', actorId: config.agentId, channel: wake.channel, messageId: wake.inputId },
        });
        if (submitted.accepted) wake.onAccepted();
      });
    } finally {
      this.inFlight.delete(config.agentId);
    }
  }

  /** Synchronize unread observations into the local Inbox before a scheduled Global step runs. */
  async syncObservations(input: ProactiveSyncObservationsInput): Promise<ProactiveSyncObservationsResult> {
    const binding = this.options.store.bindingForSession(input.sessionId);
    const config = this.options.agents.find(item => item.agentId === input.agentId && item.mode === 'global');
    if (!binding || !config || binding.agentId !== input.agentId || binding.ownerId !== input.ownerId || input.ownerId !== this.options.ownerId) {
      return { synced_count: 0, unread_conversations: [] };
    }
    const before = this.options.inbox.unreadEntryCount(config.agentId);
    await this.options.syncObservations(config, binding);
    const after = this.options.inbox.unreadEntryCount(config.agentId);
    const checked = this.options.inbox.check(config.agentId, Boolean(config.personal), this.effectiveTimeZone());
    const unread_conversations = checked.sources.map(source => ({
      conversation_id: String(this.options.store.toolReferences.targetRef(config.agentId, source.target)),
      title: source.name,
      count: source.unread,
    }));
    return { synced_count: Math.max(0, after - before), unread_conversations };
  }
}
