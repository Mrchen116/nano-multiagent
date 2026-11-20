import type { DatabaseSync } from 'node:sqlite';
import { all, one } from './context.js';
import type { WorkTurnRecord } from './work-record-types.js';
import { workEndTypes } from './work-lifetime-usage.js';

const startTypes = "'turn_started','turn_start'";
const activityTypes = `${startTypes},${workEndTypes}`;
const activityTime = `CASE WHEN type IN (${startTypes})
  THEN COALESCE(json_extract(payload,'$.started_at'),observed_at)
  ELSE COALESCE(json_extract(payload,'$.finished_at'),observed_at) END`;
const ordinary = `s.scope='subagent' AND json_type(s.payload,'$.child_agent_id')='text'
  AND json_extract(s.payload,'$.maintenance_kind') IS NULL`;
const workflow = "s.scope='workflow' AND json_type(s.payload,'$.workflow_run_id')='text'";
const graphChild = `((${ordinary}) OR (${workflow}) OR s.scope='worker')`;
const activeWorker = "s.scope='worker' AND json_extract(s.payload,'$.status') IN ('starting','running')";
const latestActive = `NOT EXISTS (SELECT 1 FROM agent_work_turns newer
  WHERE newer.session_id=a.session_id AND newer.seq>a.seq)`;

export type WorkWindow = '3d' | '2h';

type WorkSummarySession = {
  session_id: string;
  parent_session_id: string | null;
  scope: string;
  title: string | null;
  status: string;
  turn_id: string | null;
  last_active_at: string | null;
  runtime?: string;
  has_work_records?: true;
};
type CompactionRow = WorkTurnRecord & {control_payload: string};
export const standaloneCompaction = "turn_id='' AND kind='control_result' AND json_extract(payload,'$.command')='compact'";

/** Read turnless compactions as timeline entries without creating fake execution turns. */
export function standaloneCompactions(db: DatabaseSync, session: string, before: number, limit: number): CompactionRow[] {
  return all(db, `SELECT session_id,item_id AS turn_id,seq,
      json_object('command','compact','status',json_extract(payload,'$.status'),
        'manual',json(CASE WHEN json_type(payload,'$.manual')='true' THEN 'true' ELSE 'false' END),'error',substr(json_extract(payload,'$.error'),1,512),
        'duration_ms',json_extract(payload,'$.duration_ms'),
        'replaced_tokens',json_extract(payload,'$.replaced_tokens')) AS control_payload,
      json_object('session_id',session_id,'turn_id',item_id,'origin','context_compaction',
        'status',COALESCE(json_extract(payload,'$.status'),'unknown'),'usage',NULL,'started_at',observed_at) AS payload
    FROM agent_work_items WHERE session_id=? AND ${standaloneCompaction} AND seq<?
    ORDER BY seq DESC LIMIT ?`, session, before, limit) as CompactionRow[];
}

type TimelineRow = WorkTurnRecord & {scope: string; maintenance_stage?: string | null; maintenance_title?: string | null};
type WorkLifetimeUsage = {total_tokens: number | null; reported_turns: number; missing_turns: number};
type WorkGraphNode = WorkSummarySession & {ancestor_only: boolean; runtime?: string; usage?: WorkLifetimeUsage};

const latestTurnJoin = `LEFT JOIN agent_work_turns t ON t.session_id=s.session_id AND t.turn_id=(
  SELECT turn_id FROM agent_work_turns WHERE session_id=s.session_id ORDER BY seq DESC LIMIT 1
)`;
const summaryFields = `s.session_id,s.parent_session_id,s.scope,substr(json_extract(s.payload,'$.title'),1,240) AS title,
  CASE WHEN s.scope='worker' THEN json_extract(s.payload,'$.status')
    ELSE COALESCE(json_extract(t.payload,'$.status'),'unknown') END AS status,CASE WHEN s.scope!='worker' OR json_extract(s.payload,'$.worker_records_revision') IS NOT NULL THEN t.turn_id END AS turn_id,
  CASE WHEN s.scope='worker' THEN json_extract(s.payload,'$.last_active_at')
    ELSE COALESCE(json_extract(t.payload,'$.finished_at'),json_extract(t.payload,'$.started_at')) END AS last_active_at`;

/** Read bounded Work summaries from authorized roots and committed projections. */
export class WorkSummaries {
  constructor(private readonly db: DatabaseSync) {}

  /** Read the next continuous prefix of main turns, Dreaming and standalone compactions by journal position.
   *
   * Args:
   *   root: Authorized product Agent.
   *   main: Registered main execution whose maintenance belongs in the timeline.
   *   before: Exclusive position shared by all streams.
   *   limit: Maximum number of rows to return.
   */
  timeline(root: string, main: string, before: number, limit: number) {
    const mainRows = all(this.db, `SELECT t.*, 'global_main' AS scope
      FROM agent_work_turns t WHERE t.session_id=? AND t.seq<? ORDER BY t.seq DESC LIMIT ?`,
    main, before, limit + 1) as TimelineRow[];
    // The persisted maintenance start is its stable position, even when an old
    // turn was first created by a fact before the start became available.
    const maintenanceRows = all(this.db, `SELECT t.session_id,t.turn_id,e.revision AS seq,t.payload,s.scope,
      json_extract(s.payload,'$.maintenance_stage') AS maintenance_stage,
      substr(json_extract(s.payload,'$.title'),1,240) AS maintenance_title
      FROM agent_work_events e INDEXED BY agent_work_events_dreaming
      JOIN agent_work_sessions s ON s.session_id=e.session_id AND s.root_agent_id=e.root_agent_id AND s.parent_session_id=?
      JOIN agent_work_turns t ON t.session_id=e.session_id AND t.turn_id=e.turn_id
      WHERE e.root_agent_id=? AND e.revision<? AND e.type IN (${startTypes}) AND json_extract(e.payload,'$.origin')='dreaming'
      ORDER BY e.revision DESC LIMIT ?`, main, root, before, limit + 1) as TimelineRow[];
    const compactions = standaloneCompactions(this.db, main, before, limit + 1)
      .map(row => ({...row, scope: 'global_main'}));
    const rows: TimelineRow[] = [...mainRows, ...maintenanceRows, ...compactions].sort((a, b) => b.seq - a.seq);
    return {
      rows: rows.slice(0, limit),
      next_cursor: rows.length > limit ? String(rows[limit - 1]!.seq) : null,
      next_turn_id: rows[limit]?.turn_id ?? null,
      next_turn_seq: rows[limit]?.seq ?? null,
    };
  }

  /** Read the current main wake and ordinary child activity for an authorized Agent.
   *
   * Args:
   *   root: Authorized product Agent.
   *   main: Current main execution identity.
   *   complete: Whether the producing node has confirmed a current mirror.
   *   after: Exclusive session ID for the child list.
   *   limit: Maximum number of child sessions to return.
   */
  activity(root: string, main: string | null, complete: boolean, after: string, limit: number, mainComplete = complete) {
    const mainTurn = main ? one(this.db, `SELECT turn_id,json_extract(payload,'$.status') AS status
      FROM agent_work_turns WHERE session_id=? ORDER BY seq DESC LIMIT 1`, main) : undefined;
    const mainState = mainTurn?.status;
    const main_execution = !mainComplete ? 'unknown' : !mainState || ['completed', 'failed', 'interrupted'].includes(mainState) ? 'idle' : mainState;
    const latest_tool = main && mainTurn && ['running', 'waiting_permission'].includes(main_execution)
      ? this.latestTool(main, mainTurn.turn_id) : null;
    const activity = `WITH ranked AS (
      SELECT ${summaryFields},
        CASE WHEN ${ordinary} THEN ROW_NUMBER() OVER (
          PARTITION BY json_extract(s.payload,'$.child_agent_id') ORDER BY a.seq DESC, a.session_id DESC
        ) END AS child_rank
      FROM agent_work_active_turns a
      JOIN agent_work_sessions s USING(session_id)
      JOIN agent_work_turns t ON t.session_id=a.session_id AND t.turn_id=a.turn_id
      WHERE a.root_agent_id=? AND ${latestActive} AND s.scope='subagent'
        AND json_extract(s.payload,'$.maintenance_kind') IS NULL
        AND COALESCE(json_extract(t.payload,'$.origin'),'')!='dreaming'
      UNION ALL
      SELECT s.session_id,s.parent_session_id,s.scope,substr(json_extract(s.payload,'$.title'),1,240),
        json_extract(s.payload,'$.status'),NULL,json_extract(s.payload,'$.last_active_at'),1
      FROM agent_work_sessions s WHERE s.root_agent_id=? AND ${activeWorker}
    )`;
    const count = complete ? one(this.db, `${activity}
      SELECT COUNT(*) FILTER (WHERE child_rank=1 AND status IN ('starting','running')) AS running,
        COUNT(*) FILTER (WHERE child_rank=1 AND status='waiting_permission') AS waiting,
        COUNT(*) FILTER (WHERE child_rank IS NULL OR (child_rank=1 AND status='unknown')) AS unresolved
      FROM ranked`, root, root) : undefined;
    const pendingLink = complete && one(this.db, `SELECT 1 FROM agent_work_sessions s INDEXED BY agent_work_sessions_unclassified
      WHERE s.root_agent_id=? AND s.scope='subagent' AND json_extract(s.payload,'$.maintenance_kind') IS NULL
      AND json_type(s.payload,'$.child_agent_id') IS NULL AND NOT EXISTS (
        SELECT 1 FROM agent_work_turns t WHERE t.session_id=s.session_id
      ) AND NOT EXISTS (
        SELECT 1 FROM agent_work_events e INDEXED BY agent_work_knowledge_review_links
        WHERE e.root_agent_id=s.root_agent_id AND json_extract(e.payload,'$.child_session_id')=s.session_id
          AND e.type='session_linked' AND e.event_id GLOB 'knowledge-run:*'
      ) LIMIT 1`, root);
    const countsCurrent = complete && !count?.unresolved && !pendingLink;
    const rows = all(this.db, `${activity}
      SELECT session_id,parent_session_id,scope,title,status,turn_id,last_active_at
      FROM ranked WHERE child_rank=1 AND session_id>? AND status IN ('starting','running','waiting_permission')
      ORDER BY session_id LIMIT ?`, root, root, after, limit + 1) as WorkSummarySession[];
    const sessions = rows.slice(0, limit).map(row => {
      if (row.scope !== 'worker') return complete ? row : {...row, status:'unknown'};
      const worker = one(this.db, `SELECT json_extract(s.payload,'$.worker_records_revision') AS detailed,
          json_extract(s.payload,'$.runtime') AS runtime,t.turn_id,json_extract(t.payload,'$.status') AS turn_status
        FROM agent_work_sessions s ${latestTurnJoin} WHERE s.session_id=?`, row.session_id)!;
      return {...row, runtime:worker.runtime, status:complete ? row.status : 'unknown',
        ...(worker.detailed && {has_work_records:true, turn_id:worker.turn_id,
          latest_tool:complete && worker.turn_status === 'running' ? this.latestTool(row.session_id, worker.turn_id) : null})};
    });
    return {
      main_execution, latest_tool,
      running_count: countsCurrent ? count?.running ?? 0 : null,
      waiting_permission_count: countsCurrent ? count?.waiting ?? 0 : null,
      sessions,
      next_cursor: rows.length > limit ? sessions.at(-1)!.session_id : null,
    };
  }

  private latestTool(session: string, turn: string) {
    const item = one(this.db, `SELECT i.item_id,CASE WHEN octet_length(i.payload)<=4096 THEN i.payload ELSE p.payload END AS payload
      FROM agent_work_items i
      LEFT JOIN agent_work_item_previews p USING(session_id,turn_id,item_id,revision)
      WHERE i.session_id=? AND i.turn_id=? AND i.kind='tool' ORDER BY i.seq DESC LIMIT 1`, session, turn);
    if (!item?.payload) return null;
    const {name, label, status, output} = JSON.parse(item.payload);
    const description = typeof label === 'string' ? label : typeof output === 'string' ? output : undefined;
    return typeof name === 'string' ? {
      name: name.slice(0, 120),
      label: description?.slice(0, 240),
      status, session_id: session, turn_id: turn, item_id: item.item_id,
    } : null;
  }

  /** Read a delegation page and the real ancestors needed to connect it.
   *
   * Args:
   *   root: Authorized product Agent.
   *   main: Current main execution identity.
   *   window: Activity time range.
   *   until: Fixed range endpoint for a continuation.
   *   after: Exclusive session ID in the candidate set.
   *   limit: Maximum number of activity candidates before adding ancestors.
   */
  delegation(root: string, main: string | null, window: WorkWindow, until: string, after: string, limit: number) {
    const from = new Date(Date.parse(until) - (window === '3d' ? 72 : 2) * 3_600_000).toISOString();
    // Start joins from the bounded-window candidates and selected ancestry. On
    // cold databases SQLite otherwise scans the whole root catalog at each step.
    const candidates = all(this.db, `WITH candidates AS (
      SELECT session_id FROM agent_work_events INDEXED BY agent_work_events_activity_window
      WHERE root_agent_id=? AND type IN (${activityTypes}) AND (${activityTime}) BETWEEN ? AND ?
        AND session_id>?
      UNION
      SELECT session_id FROM agent_work_events WHERE root_agent_id=? AND type='worker_state'
        AND observed_at BETWEEN ? AND ? AND session_id>?
      UNION
      SELECT s.session_id FROM agent_work_sessions s WHERE s.root_agent_id=? AND ${activeWorker} AND s.session_id>?
      UNION
      SELECT a.session_id FROM agent_work_active_turns a
      WHERE a.root_agent_id=? AND a.session_id>? AND a.status IN ('running','waiting_permission') AND ${latestActive}
    )
    SELECT s.session_id FROM candidates c CROSS JOIN agent_work_sessions s USING(session_id)
    WHERE s.root_agent_id=? AND ${graphChild}
    ORDER BY c.session_id LIMIT ?`, root, from, until, after, root, from, until, after, root, after, root, after, root, limit + 1) as {session_id: string}[];
    const selected = candidates.slice(0, limit).map(row => row.session_id);
    const entries = main ? [main, ...selected] : selected;
    const rows = entries.length ? all(this.db, `WITH RECURSIVE ancestry(session_id) AS (
      VALUES ${entries.map(() => '(?)').join(',')}
      UNION
      SELECT s.parent_session_id FROM ancestry a CROSS JOIN agent_work_sessions s USING(session_id)
      WHERE s.root_agent_id=? AND s.parent_session_id IS NOT NULL AND ${graphChild}
    )
    SELECT ${summaryFields},json_extract(s.payload,'$.runtime') AS runtime,json_extract(s.payload,'$.worker_records_revision') AS detailed,
      CASE WHEN u.reported_turns>0 THEN u.total_tokens END AS total_tokens,
      COALESCE(u.reported_turns,0) AS reported_turns,
      COALESCE(u.ended_turns-u.reported_turns,0) AS missing_turns
    FROM ancestry a CROSS JOIN agent_work_sessions s USING(session_id)
    ${latestTurnJoin}
    LEFT JOIN agent_work_lifetime_usage u ON u.root_agent_id=s.root_agent_id
      AND u.session_id=CASE WHEN s.session_id=? THEN '' ELSE s.session_id END
    WHERE s.root_agent_id=? AND (s.scope='global_main' OR ${graphChild})
    ORDER BY s.session_id`, ...entries, root, main, root) as Array<WorkSummarySession & WorkLifetimeUsage & {runtime:string; detailed:number | null}> : [];
    const selectedSet = new Set(entries);
    const ancestors = rows.filter(row => !selectedSet.has(row.session_id)).map(row => row.session_id);
    const activeAncestors = new Set(ancestors.length ? all(this.db, `
      SELECT DISTINCT session_id FROM agent_work_events INDEXED BY agent_work_events_session_window
      WHERE root_agent_id=? AND session_id IN (${ancestors.map(() => '?').join(',')})
      AND type IN (${activityTypes}) AND (${activityTime}) BETWEEN ? AND ?
    `, root, ...ancestors, from, until).map(row => row.session_id) : []);
    const nodes: WorkGraphNode[] = rows.map(({total_tokens, reported_turns, missing_turns, runtime, detailed, ...row}) => ({
      ...row,
      ancestor_only: !selectedSet.has(row.session_id) && !activeAncestors.has(row.session_id),
      ...(row.scope === 'worker' && {runtime, ...(detailed && {has_work_records:true as const,
        latest_tool:row.turn_id ? this.latestTool(row.session_id, row.turn_id) : null})}),
      ...(row.scope !== 'worker' || reported_turns + missing_turns > 0 ? {usage:{total_tokens, reported_turns, missing_turns}} : {}),
    }));
    return {window, from, until, nodes, next_cursor: candidates.length > limit ? selected.at(-1)! : null};
  }
}
