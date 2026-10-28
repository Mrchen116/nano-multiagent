import type { DatabaseSync } from 'node:sqlite';
import { decodeWorkEvent, type DecodedWorkEvent, type WorkAppendBatch, type WorkAppendAck, type WorkSessionFields } from '@nano/product-contracts';
import { all, one, now, fail, transaction } from './context.js';
import { agentAvailable } from './identity.js';
import type { WorkSessionRecord, WorkEventRecord, WorkTurnRecord, WorkItemRecord, WorkSessionView, WorkTurnData, WorkItemData, WorkItemsPage, WorkTurnsPage, WorkRecordView } from './work-record-types.js';

/** Own the atomic Work journal and its persisted public projection. */
export class WorkRecords {
  constructor(readonly db: DatabaseSync) {
    for (const r of all(db, "SELECT session_id,turn_id,payload FROM agent_work_turns") as Pick<WorkTurnRecord, "session_id" | "turn_id" | "payload">[]) {
      const p: WorkTurnData = JSON.parse(r.payload);
      if (["running", "waiting_permission"].includes(p.status))
        db
          .prepare("UPDATE agent_work_turns SET payload=? WHERE session_id=? AND turn_id=?")
          .run(JSON.stringify({ ...p, status: "unknown" }), r.session_id, r.turn_id);
    }
  }
  /** Read one registered execution under its product root.
   * Args:
   *   root: Authorized product Agent identity.
   *   id: Execution identity to resolve.
   * Returns:
   *   Public metadata without the stored JSON column.
   */
  session(root: string, id: string): WorkSessionView {
    const r = one(
      this.db,
      "SELECT * FROM agent_work_sessions WHERE root_agent_id=? AND session_id=?",
      root,
      id,
    ) as WorkSessionRecord | undefined;
    if (!r) fail(404, "scope_not_allowed");
    const {payload, ...identity} = r;
    return { ...(JSON.parse(payload) as Partial<WorkSessionFields>), ...identity };
  }
  /** Retain execution identity while applying the existing main-session replacement rules.
   * Args:
   *   root: Product Agent owning the execution.
   *   session: Durable execution identity.
   *   node: Authenticated producer node.
   *   p: Decoded registration metadata.
   *   metadataOnly: Retain identity alone when content authority has been revoked.
   */
  register(root: string, session: string, node: string, p: Partial<WorkSessionFields>, metadataOnly = false) {
    if (!["global_main", "subagent", "workflow", "cron"].includes(p.scope ?? ""))
      fail(400, "invalid_scope");
    if (["subagent", "workflow"].includes(p.scope ?? "")) this.session(root, p.parent_session_id ?? "");
    const old = one(this.db, "SELECT * FROM agent_work_sessions WHERE session_id=?", session) as WorkSessionRecord | undefined;
    if (
      old &&
      (old.root_agent_id !== root ||
        old.node_id !== node ||
        old.scope !== p.scope ||
        old.parent_session_id !== (p.parent_session_id ?? null))
    )
      fail(409, "session_identity_conflict");
    if (p.scope === "global_main") {
      if(old && JSON.parse(old.payload).retired && !JSON.parse(old.payload).historical_only)fail(409,"retired_main_session");
      const other = one(
        this.db,
        "SELECT session_id FROM agent_work_sessions WHERE root_agent_id=? AND scope='global_main' AND COALESCE(json_extract(payload,'$.retired'),0)=0",
        root,
      );
      if (other && other.session_id !== session) {
        // Restoring a PA on its current device can replace execution context,
        // while keeping the owner's old Work records available as history.
        if(!one(this.db,"SELECT 1 FROM personal_agent_bindings WHERE agent_id=? AND node_id=? AND status='active'",root,node))fail(409,"main_session_conflict");
        this.db.prepare("UPDATE agent_work_sessions SET payload=json_set(payload,'$.retired',json('true')) WHERE session_id=?").run(other.session_id);
      }
    }
    this.db
      .prepare(
        "INSERT INTO agent_work_sessions VALUES(?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload",
      )
      .run(session, root, node, p.scope!, p.parent_session_id ?? null, metadataOnly
        ? old?.payload ?? JSON.stringify({ scope: p.scope, parent_session_id: p.parent_session_id ?? null })
        : JSON.stringify(p));
  }
  /** Commit journal, projections and watermark in one transaction.
   * Args:
   *   node: Authenticated producer node, supplied by the transport adapter.
   *   p: Decoded batch retaining original payload objects.
   *   historical: HTTP recovery may register an old main execution as history.
   * Returns:
   *   Committed acknowledgement and roots to notify after the transaction.
   */
  append(node: string, p: WorkAppendBatch, historical = false): {ack: WorkAppendAck; appliedRoots: Set<string>} {
    let through =
      one(
        this.db,
        "SELECT through_seq FROM agent_work_journals WHERE node_id=? AND journal_id=?",
        node,
        p.journal_id,
      )?.through_seq ?? 0;
    if (p.from_seq > through + 1)
      return { ack: {
        journal_id: p.journal_id,
        through_seq: through,
        expected_seq: through + 1,
      }, appliedRoots: new Set() };
    const appliedRoots = new Set<string>();
    transaction(this.db, () => {
      for (const [i, e] of p.events.entries()) {
        if (e.seq !== p.from_seq + i) fail(400, "invalid_sequence");
        const profile = one(
          this.db,
          "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND work_mode='global' AND is_stale=0",
          e.root_agent_id,
          node,
        );
        if (!profile) fail(403, "scope_not_allowed");
        const old = one(
          this.db,
          "SELECT * FROM agent_work_events WHERE node_id=? AND journal_id=? AND seq=?",
          node,
          p.journal_id,
          e.seq,
        ) as WorkEventRecord | undefined;
        if (old) {
          if (
            old.event_id !== e.event_id ||
            old.root_agent_id !== e.root_agent_id ||
            old.session_id !== e.session_id ||
            old.type !== e.type || old.turn_id !== (e.turn_id ?? null) ||
            (e.observed_at !== undefined && old.observed_at !== e.observed_at) || old.payload !== JSON.stringify(e.payload)
          )
            fail(409, "event_identity_conflict");
          continue;
        }
        // Revoked content is never replayed. Keep only session identities so a
        // later authorized owner can continue the same shared journal.
        if (e.seq <= through) continue;
        if (e.seq !== through + 1) fail(400, "invalid_sequence");
        const available = agentAvailable(this.db, profile);
        const fact = decodeWorkEvent(e).fact;
        if (fact?.type === "session_registered") {
          if (historical && fact.payload.scope === 'global_main') {
            const existing = one(this.db,'SELECT * FROM agent_work_sessions WHERE session_id=?',e.session_id);
            if (existing) {
              if (existing.root_agent_id!==e.root_agent_id || existing.node_id!==node || existing.scope!=='global_main') fail(409,'session_identity_conflict');
            } else this.db.prepare('INSERT INTO agent_work_sessions VALUES(?,?,?,?,?,?)').run(e.session_id,e.root_agent_id,node,'global_main',null,JSON.stringify({...e.payload,retired:true,historical_only:true}));
          } else this.register(e.root_agent_id, e.session_id, node, fact.payload, !available);
        }
        else if (available || e.type === "session_linked") this.session(e.root_agent_id, e.session_id);
        if (fact?.type === "session_linked") {
          if (fact.payload.parent_session_id !== e.session_id) fail(403, "scope_not_allowed");
          this.register(e.root_agent_id, fact.payload.child_session_id, node, {
            ...fact.payload,
            scope: fact.payload.workflow_run_id ? "workflow" : "subagent",
            parent_session_id: e.session_id,
          }, !available);
        }
        if (!available) { through = e.seq; continue; }
        const result = this.db
          .prepare(
            "INSERT INTO agent_work_events(node_id,journal_id,seq,event_id,root_agent_id,session_id,turn_id,type,observed_at,payload) VALUES(?,?,?,?,?,?,?,?,?,?)",
          )
          .run(
            node,
            p.journal_id,
            e.seq,
            e.event_id,
            e.root_agent_id,
            e.session_id,
            e.turn_id ?? null,
            e.type,
            e.observed_at ?? now(),
            JSON.stringify(e.payload),
          );
        this.project({event: e, fact}, Number(result.lastInsertRowid));
        appliedRoots.add(e.root_agent_id);
        through = e.seq;
      }
      this.db
        .prepare(
          "INSERT INTO agent_work_journals VALUES(?,?,?) ON CONFLICT(node_id,journal_id) DO UPDATE SET through_seq=excluded.through_seq",
        )
        .run(node, p.journal_id, through);
    });
    return { ack: { journal_id: p.journal_id, through_seq: through }, appliedRoots };
  }
  private project({event: e, fact}: DecodedWorkEvent, revision: number) {
    const p = e.payload,
      kind = e.type,
      session = e.session_id;
    let turnId = e.turn_id;
    if (!turnId && p.run_id && !["cron_trigger", "cron_delivery"].includes(kind))
      turnId = one(
        this.db,
        "SELECT turn_id FROM agent_work_turns WHERE session_id=? AND json_extract(payload,'$.run_id')=? ORDER BY seq DESC LIMIT 1",
        session,
        p.run_id,
      )?.turn_id;
    if (!turnId) {
      if (
        [
          "control_result",
          "recording_degraded",
          "model_fallback",
          "cron_trigger",
          "cron_delivery",
        ].includes(kind)
      )
        this.db
          .prepare("INSERT INTO agent_work_items VALUES(?,?,?,?,?,?,?,?)")
          .run(
            session,
            "",
            e.event_id,
            revision,
            kind,
            e.observed_at ?? null,
            JSON.stringify(p),
            revision,
          );
      return;
    }
    const prior = one(
      this.db,
      "SELECT * FROM agent_work_turns WHERE session_id=? AND turn_id=?",
      session,
      turnId,
    ) as WorkTurnRecord | undefined;
    const turn: WorkTurnData = prior
      ? JSON.parse(prior.payload)
      : {
          session_id: session,
          turn_id: turnId,
          status: "unknown",
          usage: null,
          source_refs: [],
        };
    if (fact?.type === "inbox_wake_admitted")
      turn.trigger = { kind: "inbox", submission_id: fact.payload.submission_id };
    if (fact?.type === "turn_started" || fact?.type === "turn_start") {
      const p = fact.payload;
      Object.assign(turn, {
        status: "running",
        origin: p.origin,
        trigger: p.trigger,
        job_id: p.trigger?.job_id,
        model_id: p.model_id ?? p.model,
        run_id: p.run_id,
        started_at: p.started_at ?? e.observed_at,
      });
    }
    if (fact?.type === "turn_end" || fact?.type === "run_completed" || fact?.type === "run_failed" || fact?.type === "run_cancelled") {
      const p = fact.payload;
      Object.assign(turn, {
        status:
          p.status ??
          (["cancelled", "aborted", "interrupted"].includes(p.stop_reason ?? "") ||
          kind === "run_cancelled"
            ? "interrupted"
            : p.completed === false || p.error || kind === "run_failed"
              ? "failed"
              : "completed"),
        finished_at: p.finished_at ?? e.observed_at,
        elapsed_ms: p.elapsed_ms ?? p.duration_ms,
        error: p.error,
        model_id: p.model ?? turn.model_id,
      });
      if (p.usage)
        turn.usage = {
          ...p.usage,
          context_used: p.usage.context_used ?? p.usage.prompt_tokens,
          output: p.usage.output ?? p.usage.completion_tokens,
          context_window: p.context_window ?? p.usage.context_window,
        };
    }
    if (fact?.type === "model_selected") turn.model_id = fact.payload.model;
    if (kind === "permission_request") turn.status = "waiting_permission";
    if (fact?.type === "permission_resolved" && turn.status === "waiting_permission") {
      const p = fact.payload;
      turn.status = one(
        this.db,
        "SELECT 1 FROM agent_work_items WHERE session_id=? AND turn_id=? AND kind='permission' AND item_id!=? AND json_extract(payload,'$.status')='pending'",
        session,
        turnId,
        `permission:${p.request_id}`,
      )
        ? "waiting_permission"
        : "running";
    }
    if (p.source_refs) turn.source_refs = p.source_refs;
    this.db
      .prepare(
        "INSERT INTO agent_work_turns VALUES(?,?,?,?) ON CONFLICT(session_id,turn_id) DO UPDATE SET payload=excluded.payload",
      )
      .run(session, turnId, prior?.seq ?? revision, JSON.stringify(turn));
    if (
      [
        "turn_started",
        "turn_start",
        "model_selected",
        "turn_end",
        "tool_result_committed",
        "turn_input_committed",
        "run_heartbeat",
        "inbox_wake_admitted",
      ].includes(kind)
    )
      return;
    let itemKind = kind, id = e.event_id, call: string | undefined;
    switch (fact?.type) {
      case 'tool_start': case 'tool_end': case 'draft_withheld':
      case 'message_sent': case 'dispatch_confirmed': case 'inbox_read_committed':
        call = fact.payload.call_id ?? fact.payload.tool_call_id;
        if (call) { itemKind = 'tool'; id = `tool:${call}`; }
        break;
      case 'permission_request': case 'permission_resolved':
        itemKind = 'permission'; id = `permission:${fact.payload.request_id}`; break;
      case 'message': case 'message_delta': case 'text_delta':
        if (fact.payload.message_id) id = `message:${fact.payload.message_id}`;
        break;
    }
    const old = one(
      this.db,
      "SELECT * FROM agent_work_items WHERE session_id=? AND turn_id=? AND item_id=?",
      session,
      turnId,
      id,
    ) as WorkItemRecord | undefined;
    const payload: WorkItemData = old ? JSON.parse(old.payload) : {};
    if (itemKind === "tool") {
      if (fact?.type === "tool_start" || fact?.type === "tool_end") {
        const p = fact.payload;
        Object.assign(payload, p, {
          input: p.arguments ?? payload.input ?? {},
          reason: p.reason_code,
          id: call,
          status:
            kind === "tool_start" ? "running" : p.error || p.is_error ? "failed" : "completed",
          output: p.presentation?.summary ?? payload.output,
          name: p.name ?? p.tool_name ?? payload.name ?? "tool",
        });
        for (const key of ["label", "summary", "detail", "emoji"])
          if (p.presentation?.[key] !== undefined) payload[key] = p.presentation[key];
      } else (payload.work_facts ??= []).push({ type: kind, ...p });
    } else if (fact?.type === "permission_request" || fact?.type === "permission_resolved") {
      const p = fact.payload;
      Object.assign(payload, p.permission_request ?? p, {
        lifecycle_revision:p.lifecycle_revision??p.permission_request?.lifecycle_revision,
        node_epoch:
          one(
            this.db,
            "SELECT b.node_epoch FROM node_binding_state b JOIN agent_work_sessions s ON s.node_id=b.node_id WHERE s.session_id=?",
            session,
          )?.node_epoch ?? 0,
        status: kind === "permission_resolved" ? "resolved" : "pending",
      });
    } else if (fact?.type === "message_delta" || fact?.type === "text_delta")
      payload.text = (payload.text ?? "") + (fact.payload.text ?? fact.payload.delta ?? "");
    else Object.assign(payload, p);
    payload.seq = old?.seq ?? revision;
    this.db
      .prepare(
        "INSERT INTO agent_work_items VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(session_id,turn_id,item_id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision",
      )
      .run(
        session,
        turnId,
        id,
        payload.seq,
        itemKind,
        e.observed_at ?? null,
        JSON.stringify(payload),
        revision,
      );
  }
  /** Page decoded items for a registered execution.
   * Args:
   *   root: Authorized product Agent identity.
   *   session: Registered execution identity.
   *   turn: Logical turn, or an empty string for control records.
   *   after: Exclusive item sequence cursor.
   *   limit: Maximum number of returned items.
   * Returns:
   *   Public items and the next page cursor.
   */
  items(root: string, session: string, turn: string, after = 0, limit = 100): WorkItemsPage {
    this.session(root, session);
    const rows = all(
      this.db,
      "SELECT * FROM agent_work_items WHERE session_id=? AND turn_id=? AND seq>? ORDER BY seq LIMIT ?",
      session,
      turn,
      after,
      limit + 1,
    ) as WorkItemRecord[];
    return {
      items: rows.slice(0, limit).map((r) => ({
        item_id: r.item_id,
        seq: r.seq,
        kind: r.kind,
        observed_at: r.observed_at,
        revision: r.revision,
        payload: JSON.parse(r.payload),
      })),
      next_cursor: rows.length > limit ? String(rows[limit - 1]!.seq) : null,
    };
  }
  /** Page logical turns with their initial item pages.
   * Args:
   *   root: Authorized product Agent identity.
   *   session: Registered execution identity.
   *   before: Exclusive turn identity cursor.
   *   limit: Maximum number of returned turns.
   * Returns:
   *   Turns, control items and the next turn cursor.
   */
  turns(root: string, session: string, before?: string, limit = 20): WorkTurnsPage {
    const registered = this.session(root, session);
    const anchor = before
      ? one(
          this.db,
          "SELECT seq FROM agent_work_turns WHERE session_id=? AND turn_id=?",
          session,
          before,
        )?.seq
      : Number.MAX_SAFE_INTEGER;
    if (anchor === undefined) fail(400, "invalid_cursor");
    const rows = all(
      this.db,
      "SELECT * FROM agent_work_turns WHERE session_id=? AND seq<? ORDER BY seq DESC LIMIT ?",
      session,
      anchor,
      limit + 1,
    ) as WorkTurnRecord[];
    return {
      turns: rows.slice(0, limit).map((r) => {
        const page = this.items(root, session, r.turn_id);
        return {
          ...(JSON.parse(r.payload) as WorkTurnData),
          scope: registered.scope,
          items: page.items,
          next_items_cursor: page.next_cursor,
        };
      }),
      control_items: this.items(root, session, "").items,
      next_cursor: rows.length > limit ? rows[limit - 1]!.turn_id : null,
    };
  }
  /** Read the committed revision used for client invalidation.
   * Args:
   *   root: Product Agent identity.
   * Returns:
   *   The latest stored event revision, or zero.
   */
  revision(root: string): number {
    const row = one(
      this.db,
      "SELECT COALESCE(MAX(revision),0) n FROM agent_work_events WHERE root_agent_id=?",
      root,
    ) as {n: number};
    return row.n;
  }
  /** Assemble stored Work without inferring live connection or synchronization state.
   * Args:
   *   root: Authorized product Agent identity.
   *   before: Exclusive main-turn identity cursor.
   *   limit: Maximum number of main turns.
   * Returns:
   *   Persisted main/child records and the node identity for the outer live-state adapter.
   */
  view(root: string, before?: string, limit = 20): WorkRecordView {
    const sessions = all(this.db, "SELECT * FROM agent_work_sessions WHERE root_agent_id=?", root) as WorkSessionRecord[],
      main = sessions.find((s) => s.scope === "global_main" && !JSON.parse(s.payload).retired)?.session_id ?? null;
    const page = main ? this.turns(root, main, before, limit) : { turns: [], next_cursor: null };
    let latest = null;
    for (const r of main
      ? all(
          this.db,
          "SELECT payload FROM agent_work_turns WHERE session_id=? ORDER BY seq DESC",
          main,
        )
      : []) {
      const t: WorkTurnData = JSON.parse(r.payload);
      if (t.usage) {
        latest = {
          session_id: main!,
          turn_id: t.turn_id,
          model_id: t.model_id,
          ...t.usage,
        };
        break;
      }
    }
    const agent = one(this.db, "SELECT node_id FROM agent_profiles WHERE agent_id=?", root) as {node_id: string};

    let state = page.turns[0]?.status ?? "idle";
    if (["completed", "failed", "interrupted"].includes(state)) state = "idle";
    return {
      root_agent_id: root,
      main_session_id: main,
      revision: this.revision(root),
      latest_main_usage: latest,
      main_execution: state,
      node_id: agent.node_id,
      control_items: main ? this.items(root, main, "").items : [],
      other_executions: sessions
        .filter((s) => s.scope !== "global_main" || JSON.parse(s.payload).retired)
        .map((s) => {
          const {payload, ...identity} = s;
          return { ...(JSON.parse(payload) as Partial<WorkSessionFields>), ...identity };
        }),
      ...page,
    };
  }
}
