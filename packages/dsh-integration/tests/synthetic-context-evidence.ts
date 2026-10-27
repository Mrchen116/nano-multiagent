import { createHash } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { strictEqual } from 'node:assert';

/** Keep complete synthetic Context evidence without repeating large policy strings.
 * Args:
 *   path: Explicit optional test-artifact destination.
 *   evidence: Entirely fixture-generated data, never product Work or live conversations.
 */
export async function writeSyntheticContextEvidence(path: string, evidence: Record<string, unknown>) {
  strictEqual(evidence.syntheticOnly, true, 'This helper is only for synthetic fixtures');
  const textPool: Record<string, string> = {};
  const map = (value: any, encode: boolean): any => {
    if (encode && typeof value === 'string' && value.length >= 1024) {
      const id = createHash('sha256').update(value).digest('hex');
      textPool[id] = value; return { $syntheticText: id };
    }
    if (Array.isArray(value)) return value.map(item => map(item, encode));
    if (!value || typeof value !== 'object') return value;
    if (!encode && Object.keys(value).length === 1 && '$syntheticText' in value) return textPool[value.$syntheticText];
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, map(item, encode)]));
  };
  const payload = map(evidence, true);
  const original = JSON.stringify(evidence);
  strictEqual(JSON.stringify(map(payload, false)), original, 'Evidence must reconstruct losslessly');
  await writeFile(path, JSON.stringify({ format: 'synthetic-context-text-pool-v1', syntheticOnly: true,
    payloadSha256: createHash('sha256').update(original).digest('hex'), payload, textPool }, null, 2));
}
