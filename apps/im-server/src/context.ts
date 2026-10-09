import { randomInt } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import type { FastifyRequest } from "fastify";
import type { Identity } from "./identity.js";
import type { Gateway } from "./gateway.js";
import type { Messaging } from "./messaging.js";
export type Row = Record<string, any>;
export interface ImContext {
  db: DatabaseSync;
  dbPath: string;
  publicUrl: string;
  jwtSecret: string;
  uploadDir: string;
  identity: Identity;
  gateway: Gateway;
  messaging: Messaging;
}
export function fail(statusCode: number, detail: string | Row): never {
  throw Object.assign(
    new Error(typeof detail === "string" ? detail : String(detail.message ?? detail.code)),
    { statusCode, detail },
  );
}
export const now = () => new Date().toISOString();
export const body = (request: FastifyRequest): Row => (request.body ?? {}) as Row;
export const params = (request: FastifyRequest): Row => request.params as Row;
export const query = (request: FastifyRequest): Row => request.query as Row;
export function transaction<T>(db: DatabaseSync, fn: () => T): T {
  db.exec("BEGIN IMMEDIATE");
  try {
    const result = fn();
    db.exec("COMMIT");
    return result;
  } catch (e) {
    db.exec("ROLLBACK");
    throw e;
  }
}
export function one(db: DatabaseSync, sql: string, ...args: any[]): Row | undefined {
  return db.prepare(sql).get(...args) as Row | undefined;
}
export function all(db: DatabaseSync, sql: string, ...args: any[]): Row[] {
  return db.prepare(sql).all(...args) as Row[];
}

export const chatId = (prefix: string) =>
  prefix +
  Array.from({ length: 8 }, () => "abcdefghijklmnopqrstuvwxyz0123456789"[randomInt(36)]).join("");
