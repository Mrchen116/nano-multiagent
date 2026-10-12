import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
/** Open the center's existing business database without replacing its data. */
export function openDatabase(path: string): DatabaseSync {
  if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;");
  db.exec(readFileSync(new URL("./schema.sql", import.meta.url), "utf8"));
  // CREATE TABLE does not upgrade deployed databases. Keep the old company rows
  // intact; new private inserts must choose their scope explicitly.
  db.exec("BEGIN IMMEDIATE");
  try {
    db.exec("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY)");
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
