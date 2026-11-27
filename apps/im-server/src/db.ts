import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import { interactiveTextProjection } from "./interactive-source.js";
import { initializeWorkLifetimeUsage } from "./work-lifetime-usage.js";
/** Open the center's existing business database without replacing its data. */
export function openDatabase(path: string): DatabaseSync {
  if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;");
  const tables = new Set((db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all() as {name:string}[]).map(r=>r.name));
  if (tables.has("task_graphs")) {
    const required: Record<string,string[]> = {task_graphs:["conversation_id"],conversations:["visibility","dissolved_at"],task_graph_mutation_receipts:["conversation_id"]};
    for (const [table,names] of Object.entries(required)) {
      const columns = new Set((db.prepare(`PRAGMA table_info(${table})`).all() as {name:string}[]).map(r=>r.name));
      if (names.some(name=>!columns.has(name))) {db.close();throw Error("Task collaboration migration required; run migrate-task-collaboration dry-run/apply/verify before starting IM");}
    }
    if (db.prepare("SELECT 1 FROM task_graphs WHERE json_extract(document_json,'$.schema_version') != 2 OR conversation_id='' LIMIT 1").get()) {db.close();throw Error("Task collaboration v2 data migration required");}
  }
  if (tables.has('pa_delegated_messages') && !db.prepare('PRAGMA table_info(pa_delegated_messages)').all().some(column => column.name === 'representation_operation_id')) {
    db.close(); throw Error('PA representation migration required; run migrate-pa-representation dry-run/apply/verify before starting IM');
  }
  db.exec("DROP TRIGGER IF EXISTS personal_observation_event; DROP TRIGGER IF EXISTS personal_membership_revoked; DROP VIEW IF EXISTS owner_direct_agent_messages");
  db.exec(readFileSync(new URL("./schema.sql", import.meta.url), "utf8"));
  if (!db.prepare("PRAGMA table_info(pa_operations)").all().some(column => column.name === "result_json"))
    db.exec("ALTER TABLE pa_operations ADD COLUMN result_json TEXT");
  if (!db.prepare('PRAGMA table_info(messages)').all().some(column => column.name === 'caller_payload_json'))
    db.exec('ALTER TABLE messages ADD COLUMN caller_payload_json TEXT');
  if (!db.prepare('PRAGMA table_info(messages)').all().some(column => column.name === 'lifecycle_revision'))
    db.exec('ALTER TABLE messages ADD COLUMN lifecycle_revision INTEGER');
  if (!db.prepare('PRAGMA table_info(messages)').all().some(column => column.name === 'reply_to_json'))
    db.exec('ALTER TABLE messages ADD COLUMN reply_to_json TEXT');
  if (!db.prepare('PRAGMA table_info(messages)').all().some(column => column.name === 'task_cards_json'))
    db.exec('ALTER TABLE messages ADD COLUMN task_cards_json TEXT');
  if (!db.prepare('PRAGMA table_info(messages)').all().some(column => column.name === 'thread_root_id'))
    db.exec('ALTER TABLE messages ADD COLUMN thread_root_id TEXT REFERENCES messages(id)');
  if (!db.prepare('PRAGMA table_info(thread_follows)').all().some(column => column.name === 'followed_at'))
    db.exec('ALTER TABLE thread_follows ADD COLUMN followed_at TEXT');
  if (!db.prepare('PRAGMA table_info(thread_follows)').all().some(column => column.name === 'reactivated_by_message_id'))
    db.exec('ALTER TABLE thread_follows ADD COLUMN reactivated_by_message_id TEXT');
  db.exec('CREATE INDEX IF NOT EXISTS messages_thread_root ON messages(thread_root_id, created_at, id)');
  // CREATE TABLE does not upgrade deployed databases. Keep the old company rows
  // intact; new private inserts must choose their scope explicitly.
  db.exec("BEGIN IMMEDIATE");
  try {
    db.exec("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY)");
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='stable-browser-sessions-v1'").get()) {
      if (!db.prepare("PRAGMA table_info(auth_sessions)").all().some(column => column.name === "browser_session"))
        db.exec("ALTER TABLE auth_sessions ADD COLUMN browser_session INTEGER NOT NULL DEFAULT 0");
      db.prepare("INSERT INTO schema_migrations VALUES('stable-browser-sessions-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='interactive-replies-v1'").get()) {
      if (!db.prepare("PRAGMA table_info(interaction_drafts)").all().some(column => column.name === "updated_at"))
        db.exec("ALTER TABLE interaction_drafts ADD COLUMN updated_at TEXT");
      if (!db.prepare("PRAGMA table_info(messages)").all().some(column => column.name === "interaction_reply_json"))
        db.exec("ALTER TABLE messages ADD COLUMN interaction_reply_json TEXT");
      db.prepare("INSERT INTO schema_migrations VALUES('interactive-replies-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='interactive-native-v2'").get()) {
      if (!db.prepare("PRAGMA table_info(message_interactive)").all().some(column => column.name === "publication_json"))
        db.exec("ALTER TABLE message_interactive ADD COLUMN publication_json TEXT");
      db.exec(`CREATE TABLE interaction_submissions_v2 (
        source_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE, semantic_json TEXT NOT NULL);
        INSERT INTO interaction_submissions_v2 SELECT * FROM interaction_submissions;
        DROP TABLE interaction_submissions;
        ALTER TABLE interaction_submissions_v2 RENAME TO interaction_submissions;
        CREATE INDEX interaction_submissions_source_user ON interaction_submissions(source_message_id,user_id);`);
      db.prepare("INSERT INTO schema_migrations VALUES('interactive-native-v2')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='interactive-card-text-v1'").get()) {
      const columns = new Set(db.prepare('PRAGMA table_info(message_interactive)').all().map(column => column.name));
      if (!columns.has('search_text'))
        db.exec("ALTER TABLE message_interactive ADD COLUMN search_text TEXT NOT NULL DEFAULT ''");
      if (!columns.has('preview_title'))
        db.exec('ALTER TABLE message_interactive ADD COLUMN preview_title TEXT');
      const save = db.prepare('UPDATE message_interactive SET search_text=?,preview_title=? WHERE message_id=?');
      const cards = db.prepare('SELECT message_id,source FROM message_interactive').all() as {message_id:string;source:string}[];
      for (const card of cards) {
        let text: ReturnType<typeof interactiveTextProjection>;
        try { text = interactiveTextProjection(card.source); }
        catch { continue; } // Historical programs unsupported by the current parser stay readable as stored.
        save.run(text.searchText, text.previewTitle, card.message_id);
      }
      db.prepare("INSERT INTO schema_migrations VALUES('interactive-card-text-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='user-timezone-v1'").get()) {
      for (const table of ['users', 'messages']) {
        if (!db.prepare(`PRAGMA table_info(${table})`).all().some(column => column.name === 'timezone'))
          db.exec(`ALTER TABLE ${table} ADD COLUMN timezone TEXT`);
      }
      db.prepare("INSERT INTO schema_migrations VALUES('user-timezone-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='personal-spaces-v1'").get()) {
      for (const [table, column, definition] of [
        ["users", "personal_space_enabled", "INTEGER NOT NULL DEFAULT 0"],
        ...["conversations", "agent_profiles", "task_graphs", "task_graph_mutation_receipts"].map(table => [table, "space_id", "TEXT NOT NULL DEFAULT 'company:default'"]),
      ]) {
        const columns = db.prepare(`PRAGMA table_info(${table})`).all();
        if (!columns.some(columnInfo => columnInfo.name === column))
          db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`);
      }
      db.prepare("INSERT INTO schema_migrations VALUES('personal-spaces-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='agent-avatar-v1'").get()) {
      if (!db.prepare('PRAGMA table_info(agent_profiles)').all().some(column => column.name === 'avatar_variant'))
        db.exec('ALTER TABLE agent_profiles ADD COLUMN avatar_variant INTEGER CHECK (avatar_variant BETWEEN 0 AND 23)');
      db.prepare("INSERT INTO schema_migrations VALUES('agent-avatar-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='agent-approval-mode-v1'").get()) {
      if (!db.prepare('PRAGMA table_info(agent_profiles)').all().some(column => column.name === 'approval_mode'))
        db.exec("ALTER TABLE agent_profiles ADD COLUMN approval_mode TEXT CHECK (approval_mode IS NULL OR approval_mode IN ('cc', 'codex'))");
      db.prepare("INSERT INTO schema_migrations VALUES('agent-approval-mode-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='task-context-unfinished-relays-v1'").get()) {
      // Accepted transport is not consumption. Bootstrap only unfinished business
      // relays, by their authoritative original IDs, before admitting any steps.
      // A previously withdrawn source must never be resurrected by a later seq.
      db.exec(`WITH unfinished AS (
          SELECT r.*,r.rowid AS relay_order,CASE WHEN json_valid(r.payload_json) THEN r.payload_json ELSE '{}' END AS payload
          FROM relay_tasks r WHERE r.status IN ('queued','sent','accepted')
        )
        INSERT OR IGNORE INTO task_context_index(agent_id,message_id,conversation_id,projection_kind)
        SELECT a.agent_id,m.id,m.conversation_id,'full'
        FROM unfinished r JOIN messages m ON m.id=r.message_id AND m.conversation_id=r.conversation_id
        JOIN agent_profiles a ON a.agent_id=json_extract(r.payload,'$.agent_id')
        WHERE json_type(r.payload,'$.agent_id')='text' AND m.sender_type='system'
          AND json_extract(CASE WHEN json_valid(m.system_notice_json) THEN m.system_notice_json END,'$.kind')='task_graph'
          AND NOT EXISTS (SELECT 1 FROM task_context_revocations v WHERE v.message_id=m.id)
          AND NOT EXISTS (SELECT 1 FROM json_each(CASE WHEN json_valid(m.system_notice_json) THEN m.system_notice_json END,'$.change_kinds') k WHERE k.value='access_revoked')
          AND NOT EXISTS (SELECT 1 FROM task_context_index i WHERE i.agent_id=a.agent_id AND i.conversation_id=m.conversation_id AND i.projection_kind='revoked')
        ORDER BY m.rowid,r.relay_order`);
      db.prepare("INSERT INTO schema_migrations VALUES('task-context-unfinished-relays-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='work-lifetime-usage-v1'").get()) {
      initializeWorkLifetimeUsage(db);
      db.prepare("INSERT INTO schema_migrations VALUES('work-lifetime-usage-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='owner-direct-wechat-view-v1'").get()) {
      db.exec(`DROP VIEW IF EXISTS owner_direct_agent_messages;
        CREATE VIEW owner_direct_agent_messages AS
          SELECT m.id AS message_id, a.agent_id
          FROM messages m
          JOIN conversations c ON c.id=m.conversation_id AND c.type='direct'
          JOIN agent_profiles a ON ((m.sender_source_id IS NOT NULL AND a.agent_id=c.config_agent_id)
            OR (m.sender_source_id IS NULL AND EXISTS (SELECT 1 FROM conversation_participants cp JOIN users agent ON agent.id=cp.user_id
              WHERE cp.conversation_id=c.id AND agent.username='agent:'||a.agent_id)))
          WHERE m.sender_type='user'
          AND NOT EXISTS (SELECT 1 FROM pa_delegated_messages d WHERE d.message_id=m.id AND d.representation_operation_id IS NOT NULL)
          AND ((m.sender_source_id IS NULL AND m.sender_user_id=COALESCE(
                (SELECT b.owner_user_id FROM personal_agent_bindings b WHERE b.agent_id=a.agent_id),
                (SELECT u.id FROM users u WHERE u.owner_id=a.owner_id AND u.username NOT LIKE 'agent:%' AND u.username NOT LIKE 'shadow:%' AND u.username!='system' LIMIT 1)))
            OR (c.config_agent_id=a.agent_id AND c.external_source='feishu' AND EXISTS (
              SELECT 1 FROM agent_channels ch WHERE ch.agent_id=a.agent_id AND ch.provider='feishu' AND ch.enabled=1
              AND ch.owner_id=a.owner_id AND ch.node_id=a.node_id AND m.sender_source_id=json_extract(ch.provider_runtime_json,'$.owner_open_id')
              AND c.external_chat_id='feishu:'||json_extract(ch.config_json,'$.app_id')||':dm:'||m.sender_source_id))
            OR (c.config_agent_id=a.agent_id AND c.external_source='wechat' AND EXISTS (
              SELECT 1 FROM agent_channels ch WHERE ch.agent_id=a.agent_id AND ch.provider='wechat' AND ch.enabled=1
              AND ch.owner_id=a.owner_id AND ch.node_id=a.node_id AND m.sender_source_id=json_extract(ch.config_json,'$.owner_user_id')
              AND c.external_chat_id='wechat:'||json_extract(ch.config_json,'$.bot_id')||':dm:'||m.sender_source_id)));`);
      db.prepare("INSERT INTO schema_migrations VALUES('owner-direct-wechat-view-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='pa-binding-collaboration-scope-v1'").get()) {
      db.exec(`INSERT OR IGNORE INTO pa_binding_scopes(binding_id, collaboration_scope)
        SELECT b.binding_id, COALESCE(a.collaboration_scope, 'team')
        FROM personal_agent_bindings b
        LEFT JOIN agent_profiles a ON a.agent_id = b.agent_id
        WHERE COALESCE(a.collaboration_scope, 'team') IN ('team', 'owner_only')`);
      db.prepare("INSERT INTO schema_migrations VALUES('pa-binding-collaboration-scope-v1')").run();
    }
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='user-avatar-v1'").get()) {
      const userCols = new Set(db.prepare("PRAGMA table_info(users)").all().map(column => column.name));
      for (const col of ["avatar_storage_name", "avatar_version", "avatar_content_type"]) {
        if (!userCols.has(col)) db.exec(`ALTER TABLE users ADD COLUMN ${col} TEXT`);
      }
      db.prepare("INSERT INTO schema_migrations VALUES('user-avatar-v1')").run();
    }
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    db.close();
    throw error;
  }
  db.prepare(
    `INSERT OR IGNORE INTO settings_policies VALUES ('default','codex_oauth:gpt-5.5',14,15,30,'basic',45)`,
  ).run();
  return db;
}
