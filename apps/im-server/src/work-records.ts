import type { DatabaseSync } from 'node:sqlite';
import { decodeWorkEvent, workRedactedType, type DecodedWorkEvent, type WorkAppendBatch, type WorkAppendAck, type WorkSessionFields } from '@nano/product-contracts';
import { all, one, now, fail, transaction } from './context.js';
import { agentAvailable } from './identity.js';
import type { WorkSessionRecord, WorkEventRecord, WorkTurnRecord, WorkItemRecord, WorkSessionView, WorkTurnData, WorkItemData, WorkItemsPage, WorkTurnsPage, WorkTurnView, WorkFocus, WorkRecordView, WorkCatalogFilter, WorkCatalogPage } from './work-record-types.js';

// The planner can otherwise favor a broader root index before fresh statistics exist.
const currentMainSql = `SELECT session_id FROM agent_work_sessions INDEXED BY agent_work_sessions_current_main
  WHERE root_agent_id=? AND scope='global_main' AND COALESCE(json_extract(payload,'$.retired'),0)=0 LIMIT 1`;

/** Look up a removed Work position and reject incompatible retries.
 * Args:
 *   root: The decoded product Agent when the transport carries an event body.
 * Returns:
 *   The root identity if the position is covered by a deletion receipt.
 */
export function workRedaction(db: DatabaseSync, node: string, journal: string, seq: number, eventId: string, root?: string): string | undefined {
  const row = one(db, 'SELECT * FROM work_sync_redactions WHERE (node_id=? AND journal_id=? AND seq=?) OR event_id=?', node, journal, seq, eventId);
  if (!row) return undefined;
  if (row.node_id !== node || row.journal_id !== journal || row.seq !== seq || row.event_id !== eventId || (root !== undefined && row.root_agent_id !== root))
    fail(409, 'event_identity_conflict');
  return row.root_agent_id;
}

/** Own the atomic Work journal and its persisted public projection. */
export class WorkRecords {
  constructor(readonly db: DatabaseSync) {
    db.exec(`CREATE TABLE IF NOT EXISTS work_sync_redactions (
      node_id TEXT NOT NULL, journal_id TEXT NOT NULL, seq INTEGER NOT NULL,
      event_id TEXT NOT NULL UNIQUE, root_agent_id TEXT NOT NULL, operation_id TEXT NOT NULL,
      PRIMARY KEY(node_id,journal_id,seq));`);
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
    return this.sessionView(r);
  }
  private sessionView({payload, ...identity}: WorkSessionRecord): WorkSessionView {
    return {...JSON.parse(payload) as Partial<WorkSessionFields>, ...identity};
  }

  /** Page a catalog or the matching executions for one legacy link.
   * Args:
   *   root: Authorized product Agent identity.
   *   after: Exclusive execution ID from the same filter.
   *   limit: Maximum number of returned executions.
   *   filter: Parent/call or parent/agent evidence from a Work item.
   * Returns:
   *   Matching executions and a stable continuation cursor.
   */
  catalog(root: string, after: string, limit: number, filter: WorkCatalogFilter): WorkCatalogPage {
    const {parent, call, agent} = filter;
    // Continuations keep the match class chosen for their first page. A late
    // exact link cannot reinterpret a weak cursor as a position in another set.
    let mode: WorkCatalogPage['match_mode'];
    if (parent || call || agent) {
      if (after.startsWith('exact:') && call) { mode='exact'; after=after.slice(6); }
      else if (after.startsWith('weak:') && agent) { mode='weak'; after=after.slice(5); }
      else if (after) fail(400,'invalid_cursor');
      else if (call && this.exactChild(root,parent!,call)) mode='exact';
      else if (agent) mode='weak';
      else return {sessions:[],next_cursor:null,match_mode:'exact'};
    }
    const bindings: string[] = [root, after];
    let sql = `SELECT * FROM agent_work_sessions WHERE root_agent_id=? AND session_id>?
      AND (scope!='global_main' OR COALESCE(json_extract(payload,'$.retired'),0)!=0)`;
    if (parent) { sql += ' AND parent_session_id=?'; bindings.push(parent); }
    if (mode === "exact") { sql += " AND json_extract(payload,'$.parent_tool_call_id')=?"; bindings.push(call!); }
    else if (mode === "weak") { sql += " AND json_extract(payload,'$.child_agent_id')=?"; bindings.push(agent!); }
    const rows = all(this.db, sql + ' ORDER BY session_id LIMIT ?', ...bindings, limit + 1) as WorkSessionRecord[];
    const sessions = rows.slice(0, limit).map(row => this.sessionView(row));
    const end=sessions.at(-1)?.session_id;
    return {sessions,next_cursor:rows.length > limit ? (mode ? mode+':'+end : end!) : null,
      ...(mode ? {match_mode:mode} : {})};
  }
  private exactChild(root:string,parent:string,call:string):boolean {
    return !!one(this.db, `SELECT 1 FROM agent_work_sessions
      WHERE root_agent_id=? AND parent_session_id=? AND json_extract(payload,'$.parent_tool_call_id')=? LIMIT 1`,root,parent,call);
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
        currentMainSql,
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
   *   commitDetail: Persist a large detail receipt inside the same transaction as its projection.
   * Returns:
   *   Committed acknowledgement and roots to notify after the transaction.
   */
  append(node: string, p: WorkAppendBatch, historical = false, commitDetail?: () => void): {ack: WorkAppendAck; appliedRoots: Set<string>} {
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
      if (!commitDetail && one(this.db, `SELECT 1 FROM work_detail_uploads
        WHERE node_id=? AND journal_id=? AND seq BETWEEN ? AND ?`,
        node, p.journal_id, p.from_seq, p.from_seq + p.events.length - 1)) fail(409, 'event_identity_conflict');
      for (const [i, e] of p.events.entries()) {
        if (e.seq !== p.from_seq + i) fail(400, "invalid_sequence");
        if (workRedaction(this.db, node, p.journal_id, e.seq, e.event_id, e.root_agent_id)) {
          if (e.seq > through + 1) fail(400, 'invalid_sequence');
          through = Math.max(through, e.seq);
          continue;
        }
        if (e.type === workRedactedType) fail(409, 'work_redaction_required');
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
      commitDetail?.();
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
    if (p.large_detail_preview === true) payload.large_detail_preview = true;
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
  items(root: string, session: string, turn: string, after = 0, limit = 100, afterRevision?: number, watermarked = false): WorkItemsPage {
    this.session(root, session);
    const order = afterRevision === undefined ? 'seq' : 'revision';
    const rows = all(
      this.db,
      `SELECT * FROM agent_work_items WHERE session_id=? AND turn_id=? AND ${order}>? ORDER BY ${order} LIMIT ?`,
      session, turn, afterRevision ?? after, limit + 1,
    ) as WorkItemRecord[];
    const last = rows[Math.min(rows.length, limit) - 1];
    // Synchronous reads take the item page and its initial watermark together.
    const revision = afterRevision !== undefined ? last?.revision ?? afterRevision :
      watermarked ? one(this.db, 'SELECT MAX(revision) AS n FROM agent_work_items WHERE session_id=? AND turn_id=?', session, turn)?.n ?? 0 : undefined;
    return {
      ...(revision === undefined ? {} : {revision}),
      items: rows.slice(0, limit).map(r => {
        const payload: WorkItemData=JSON.parse(r.payload);
        const call=payload.id ?? payload.call_id ?? payload.tool_call_id;
        const linked=(watermarked || afterRevision !== undefined) && r.kind==='tool' && typeof call==='string' &&
          this.exactChild(root,session,call);
        return {item_id:r.item_id,seq:r.seq,kind:r.kind,observed_at:r.observed_at,revision:r.revision,payload,
          ...(linked ? {has_exact_child:true} : {})};
      }),
      next_cursor: rows.length > limit ? String(last![order]) : null,
    };
  }
  /** Page logical turns with their initial item pages.
   * Args:
   *   root: Authorized product Agent identity.
   *   session: Registered execution identity.
   *   before: Exclusive turn identity cursor.
   *   limit: Maximum number of returned turns.
   *   summary: Defer full item bodies until the turn is opened.
   * Returns:
   *   Turns, control items and the next turn cursor.
   */
  turns(root: string, session: string, before?: string, limit = 20, summary = false, separate = false): WorkTurnsPage {
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
      turns: rows.slice(0, limit).map(row => this.turnView(root, registered.scope, row, summary, separate)),
      control_items: separate ? [] : this.items(root, session, "").items,
      next_cursor: rows.length > limit ? rows[limit - 1]!.turn_id : null,
      next_turn_id: rows[limit]?.turn_id ?? null,
    };
  }
  private turnView(root: string, scope: string, row: WorkTurnRecord, summary: boolean, separate: boolean): WorkTurnView {
    const turn = {...JSON.parse(row.payload) as WorkTurnData, scope, seq: row.seq};
    if (separate) return {...turn, items: [], next_items_cursor: null, items_deferred: true};
    if (!summary) {
      const page = this.items(root, row.session_id, row.turn_id);
      return {...turn, items: page.items, next_items_cursor: page.next_cursor};
    }
    const toolCount = one(this.db, "SELECT COUNT(*) AS n FROM agent_work_items WHERE session_id=? AND turn_id=? AND kind='tool'", row.session_id, row.turn_id)?.n ?? 0;
    const background = one(this.db, "SELECT COALESCE(json_extract(payload,'$.task_type'), json_extract(payload,'$.background_returns[0].task_type')) AS task_type FROM agent_work_items WHERE session_id=? AND turn_id=? AND (kind='background_return' OR json_array_length(payload,'$.background_returns') > 0) ORDER BY seq LIMIT 1", row.session_id, row.turn_id);
    return {...turn, items: [], next_items_cursor: null, items_deferred: true, tool_count: toolCount,
      has_background_returns: Boolean(background), background_task_type: background?.task_type ?? null};
  }

  private replyTurn(root: string, messageId: string): (WorkTurnRecord & {scope: string}) | undefined {
    // Only a committed delivery fact can identify a reply's actual wake.
    return one(this.db,
      `SELECT t.*,s.scope FROM agent_work_events e
       JOIN agent_work_sessions s ON s.session_id=e.session_id
       JOIN agent_work_turns t ON t.session_id=e.session_id AND t.turn_id=e.turn_id
       WHERE e.root_agent_id=? AND s.root_agent_id=? AND s.scope='global_main'
       AND e.type='message_sent' AND json_extract(e.payload,'$.message_id')=?
       ORDER BY e.revision LIMIT 1`, root, root, messageId) as (WorkTurnRecord & {scope: string}) | undefined;
  }

  /** Read one reply's durable turn summary and its nearest neighbors.
   * Args:
   *   root: Authorized product Agent identity.
   *   messageId: Published chat reply identity.
   * Returns:
   *   The exact turn and its neighbors, or null while the delivery is unavailable.
   */
  focus(root: string, messageId: string, separate = false): WorkFocus | null {
    const row = this.replyTurn(root, messageId);
    if (!row) return null;
    const newer = one(this.db, "SELECT turn_id FROM agent_work_turns WHERE session_id=? AND seq>? ORDER BY seq ASC LIMIT 1", row.session_id, row.seq);
    const older = one(this.db, "SELECT turn_id FROM agent_work_turns WHERE session_id=? AND seq<? ORDER BY seq DESC LIMIT 1", row.session_id, row.seq);
    return {turn: this.turnView(root, row.scope, row, true, separate), newer_turn_id: newer?.turn_id ?? null, older_turn_id: older?.turn_id ?? null};
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
   *   summary: Defer full item bodies until the turn is opened.
   *   messageId: Identify the reply's recorded wake without filtering the Work list.
   * Returns:
   *   Persisted main/child records and the node identity for the outer live-state adapter.
   */
  view(root: string, before?: string, limit = 20, summary = false, messageId?: string, separate = false): WorkRecordView {
    const sessions = separate ? [] : all(this.db, "SELECT * FROM agent_work_sessions WHERE root_agent_id=?", root) as WorkSessionRecord[];
    const main = (separate
      ? one(this.db, currentMainSql, root)
      : sessions.find(s => s.scope === "global_main" && !JSON.parse(s.payload).retired))?.session_id ?? null;
    const reply = messageId ? this.replyTurn(root, messageId) : undefined;
    // A message selects where to expand, not which records exist in Work.
    const page = main ? this.turns(root, main, before, limit, summary, separate) : { turns: [], next_cursor: null, next_turn_id: null };
    let latest = null;
    for (const r of main
      ? this.db.prepare(separate
        ? "SELECT payload FROM agent_work_turns WHERE session_id=? AND json_type(payload,'$.usage')='object' ORDER BY seq DESC LIMIT 1"
        : "SELECT payload FROM agent_work_turns WHERE session_id=? ORDER BY seq DESC").iterate(main)
      : []) {
      const t: WorkTurnData = JSON.parse(String(r.payload));
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

    const currentTurn = main ? one(this.db, "SELECT payload FROM agent_work_turns WHERE session_id=? ORDER BY seq DESC LIMIT 1", main) : undefined;
    let state = currentTurn ? (JSON.parse(currentTurn.payload) as WorkTurnData).status : "idle";
    if (["completed", "failed", "interrupted"].includes(state)) state = "idle";
    return {
      ...(separate ? {catalog: 'separate' as const} : {}),
      root_agent_id: root,
      main_session_id: main,
      ...(messageId ? {focus: reply ? {session_id: reply.session_id, turn_id: reply.turn_id} : null} : {}),
      revision: this.revision(root),
      latest_main_usage: latest,
      main_execution: state,
      node_id: agent.node_id,
      control_items: [],
      other_executions: sessions
        .filter((s) => s.scope !== "global_main" || JSON.parse(s.payload).retired)
        .map(s => this.sessionView(s)),
      ...page,
    };
  }
}
