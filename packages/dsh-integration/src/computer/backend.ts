/** An operation on one task's target, prepared by a trusted backend before review. */
export interface PreparedAction {
  access: 'observe' | 'review' | 'system_clipboard';
  evidence: string;
  window?: { title: string; candidates: number };
  run(signal: AbortSignal): Promise<ComputerContent[]>;
}

export type ComputerContent = { type: 'text'; text: string } | { type: 'image'; data: string; mimeType: string };

/** One backend instance belongs to exactly one host-issued seat. */
export interface ComputerBackend {
  prepare(action: string, input: Record<string, unknown>, signal: AbortSignal): Promise<PreparedAction>;
  close(): Promise<void>;
}
