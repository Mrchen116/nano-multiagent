import type { DatabaseSync } from 'node:sqlite';

export const workEndTypes = "'turn_end','run_completed','run_failed','run_cancelled'";

/** Rebuild the lifetime projection from durable turn and completion records. */
export function initializeWorkLifetimeUsage(db: DatabaseSync) {
  db.exec(`
    WITH endings AS (
      SELECT e.session_id,e.revision,COALESCE(e.turn_id,(
        SELECT t.turn_id FROM agent_work_turns t
        WHERE t.session_id=e.session_id AND json_extract(t.payload,'$.run_id')=json_extract(e.payload,'$.run_id')
        ORDER BY t.seq DESC LIMIT 1
      )) AS turn_id,COALESCE(json_extract(e.payload,'$.finished_at'),e.observed_at) AS finished_at
      FROM agent_work_events e WHERE e.type IN (${workEndTypes})
    ), latest AS (
      SELECT *,ROW_NUMBER() OVER (PARTITION BY session_id,turn_id ORDER BY revision DESC) AS position FROM endings
    )
    UPDATE agent_work_turns AS t
    SET payload=json_set(t.payload,'$.finished_at',e.finished_at)
    FROM latest e WHERE e.position=1 AND e.session_id=t.session_id AND e.turn_id=t.turn_id
      AND json_extract(t.payload,'$.finished_at') IS NULL;

    WITH ended AS (
      SELECT s.root_agent_id,t.session_id,s.scope,COUNT(*) AS ended_turns,
        COUNT(CASE WHEN json_type(t.payload,'$.usage.total_tokens') IN ('integer','real') THEN 1 END) AS reported_turns,
        SUM(CASE WHEN json_type(t.payload,'$.usage.total_tokens') IN ('integer','real')
          THEN json_extract(t.payload,'$.usage.total_tokens') ELSE 0 END) AS total_tokens
      FROM agent_work_turns t JOIN agent_work_sessions s USING (session_id)
      WHERE json_extract(t.payload,'$.finished_at') IS NOT NULL
      GROUP BY t.session_id
    )
    INSERT INTO agent_work_lifetime_usage (root_agent_id,session_id,ended_turns,reported_turns,total_tokens)
    SELECT root_agent_id,session_id,ended_turns,reported_turns,total_tokens FROM ended
    UNION ALL
    SELECT root_agent_id,'',SUM(ended_turns),SUM(reported_turns),SUM(total_tokens)
    FROM ended WHERE scope='global_main' GROUP BY root_agent_id;
  `);
}

/** Apply a reported end in the same transaction as its turn projection.
 *
 * Args:
 *   db: The open Work append transaction.
 *   sessionId: The owner of the turn.
 *   wasEnded: Whether the turn had a previous durable completion.
 *   before: Reported total from the previous completion, if available.
 *   after: Current reported total, if available.
 */
export function updateWorkLifetimeUsage(
  db: DatabaseSync,
  sessionId: string,
  wasEnded: boolean,
  before: number | undefined,
  after: number | undefined,
) {
  const previousTokens = wasEnded && typeof before === 'number' ? before : undefined;
  const tokens = typeof after === 'number' ? after : undefined;
  if (wasEnded && previousTokens === tokens) return;
  db.prepare(`WITH delta(ended_turns,reported_turns,total_tokens) AS (VALUES(?,?,?)),
    session AS (SELECT root_agent_id,session_id,scope FROM agent_work_sessions WHERE session_id=?)
    INSERT INTO agent_work_lifetime_usage (root_agent_id,session_id,ended_turns,reported_turns,total_tokens)
    SELECT root_agent_id,session_id,ended_turns,reported_turns,total_tokens FROM session CROSS JOIN delta
    UNION ALL
    SELECT root_agent_id,'',ended_turns,reported_turns,total_tokens FROM session CROSS JOIN delta WHERE scope='global_main'
    ON CONFLICT(root_agent_id,session_id) DO UPDATE SET
      ended_turns=agent_work_lifetime_usage.ended_turns+excluded.ended_turns,
      reported_turns=agent_work_lifetime_usage.reported_turns+excluded.reported_turns,
      total_tokens=agent_work_lifetime_usage.total_tokens+excluded.total_tokens
  `).run(Number(!wasEnded), Number(tokens !== undefined) - Number(previousTokens !== undefined),
    (tokens ?? 0) - (previousTokens ?? 0), sessionId);
}
