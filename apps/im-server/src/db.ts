import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
/** Open the center's existing business database without replacing its data. */
export function openDatabase(path: string): DatabaseSync {
  if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;");
  db.exec(readFileSync(new URL("./schema.sql", import.meta.url), "utf8"));
  db.prepare(
    `INSERT OR IGNORE INTO settings_policies VALUES ('default','codex_oauth:gpt-5.5',14,15,30,'basic',45)`,
  ).run();
  return db;
}
