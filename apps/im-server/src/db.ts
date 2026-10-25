import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
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
  db.exec("DROP TRIGGER IF EXISTS personal_observation_event; DROP TRIGGER IF EXISTS personal_membership_revoked");
  db.exec(readFileSync(new URL("./schema.sql", import.meta.url), "utf8"));
  if (!db.prepare("PRAGMA table_info(pa_operations)").all().some(column => column.name === "result_json"))
    db.exec("ALTER TABLE pa_operations ADD COLUMN result_json TEXT");
  if (!db.prepare('PRAGMA table_info(messages)').all().some(column => column.name === 'caller_payload_json'))
    db.exec('ALTER TABLE messages ADD COLUMN caller_payload_json TEXT');
  // CREATE TABLE does not upgrade deployed databases. Keep the old company rows
  // intact; new private inserts must choose their scope explicitly.
  db.exec("BEGIN IMMEDIATE");
  try {
    db.exec("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY)");
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
    if (!db.prepare("SELECT 1 FROM schema_migrations WHERE version='agent-approval-mode-v1'").get()) {
      if (!db.prepare('PRAGMA table_info(agent_profiles)').all().some(column => column.name === 'approval_mode'))
        db.exec("ALTER TABLE agent_profiles ADD COLUMN approval_mode TEXT CHECK (approval_mode IS NULL OR approval_mode IN ('cc', 'codex'))");
      db.prepare("INSERT INTO schema_migrations VALUES('agent-approval-mode-v1')").run();
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
