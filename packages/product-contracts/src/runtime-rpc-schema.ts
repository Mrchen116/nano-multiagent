import { z } from 'zod';
import { workObject } from './work-event-codec.js';

export const id = z.string().min(1);
export const text = z.string();
export const bool = z.boolean();
export const count = z.int().nonnegative();
export const cursor = z.int().min(-1);
export const ids = z.array(id);
export const dataObject = z.custom<Record<string, unknown>>(workObject);

// These fields are added by the product lifecycle wrapper before stdio dispatch.
export const lifecycle = {agent_id: id.optional(), lifecycle_revision: count.optional()};
export function input<const S extends z.ZodRawShape>(shape: S) {
  return z.object({...lifecycle, ...shape});
}
export function rpc<I extends z.ZodType, O extends z.ZodType>(input: I, result: O) {
  return {input, result};
}
export const evidence = z.object({
  accepted: bool, pending: bool, acceptedSeq: count.optional(), consumedSeq: count.optional(),
  turn: count.optional(), turns: z.array(count).optional(), terminal: z.object({kind: id}).optional(),
  providerDelivered: bool.optional(),
});
