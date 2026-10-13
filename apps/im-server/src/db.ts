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
  db.exec(readFileSync(new URL("./schema.sql", import.meta.url), "utf8"));
  db.prepare(
    `INSERT OR IGNORE INTO settings_policies VALUES ('default','codex_oauth:gpt-5.5',14,15,30,'basic',45)`,
  ).run();
  return db;
}
