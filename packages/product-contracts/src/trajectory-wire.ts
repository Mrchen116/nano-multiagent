import { TRAJECTORY_MAX_BYTES } from './trajectory.js';

const BUDGET = TRAJECTORY_MAX_BYTES - 1024;
// A UTF-16 code unit needs at most six bytes when escaped in the JSON envelope.
const CHUNK_LENGTH = Math.floor((BUDGET - 1024) / 6);
const encoder = new TextEncoder();
interface Fragment {
  type: 'trajectory-fragment'; transferId: string; index: number; final: boolean; data: string;
  observerId?: string; requestId?: string;
}
interface Assembly { parts: string[]; observerId?: string; requestId?: string }

/** Split a complete JSON DTO without changing its fields or native history semantics.
 *
 * Args:
 *   value: One native frame or Nano response. Routing identities accompany each fragment.
 * Returns:
 *   Ordered JSON values, each below the physical carrier budget; small DTOs pass through.
 */
export function* encodeTrajectoryValue(value: unknown): Generator<unknown> {
  const text = JSON.stringify(value);
  if (encoder.encode(text).byteLength <= BUDGET) { yield value; return; }
  const routing = value as { observerId?: string; requestId?: string };
  const transferId = crypto.randomUUID();
  for (let offset = 0, index = 0; offset < text.length; offset += CHUNK_LENGTH, index++) {
    yield { type: 'trajectory-fragment', transferId, index, final: offset + CHUNK_LENGTH >= text.length,
      data: text.slice(offset, offset + CHUNK_LENGTH), observerId: routing.observerId, requestId: routing.requestId } satisfies Fragment;
  }
}

/** Reassemble interleaved carrier transfers within one observer generation. */
export class TrajectoryValueDecoder {
  private readonly assemblies = new Map<string, Assembly>();

  /** Accept a carrier value; publish only complete DTOs, rejecting gaps and identity changes.
   *
   * Returns:
   *   The original DTO, or undefined while a transfer remains incomplete.
   * Raises:
   *   Error: A fragment is malformed, missing, duplicated, or changes routing identity.
   */
  push(value: unknown): any {
    if (!value || typeof value !== 'object' || (value as Fragment).type !== 'trajectory-fragment') return value;
    const frame = value as Fragment;
    if (typeof frame.transferId !== 'string' || !Number.isSafeInteger(frame.index) || frame.index < 0
      || typeof frame.data !== 'string' || typeof frame.final !== 'boolean') throw new Error('trajectory_invalid_fragment');
    let assembly = this.assemblies.get(frame.transferId);
    if (frame.index === 0 && !assembly) {
      assembly = { parts: [], observerId: frame.observerId, requestId: frame.requestId };
      this.assemblies.set(frame.transferId, assembly);
    }
    if (!assembly || frame.index !== assembly.parts.length || frame.observerId !== assembly.observerId
      || frame.requestId !== assembly.requestId) throw new Error('trajectory_fragment_out_of_order');
    assembly.parts.push(frame.data);
    if (!frame.final) return;
    this.assemblies.delete(frame.transferId);
    const result = JSON.parse(assembly.parts.join(''));
    if (result?.observerId !== assembly.observerId || result?.requestId !== assembly.requestId) throw new Error('trajectory_fragment_identity_changed');
    return result;
  }

  /** Reject a stream that ended before its final fragment arrived. */
  finish(): void { if (this.assemblies.size) throw new Error('trajectory_incomplete_fragment'); }

  /** Discard partial transfers when their observer or native stream ends. */
  clear(): void { this.assemblies.clear(); }
}
