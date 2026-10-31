/** Evaluation vocabulary shared by runners and candidate adapters; no runtime internals. */
export interface EvaluationHistory {
  caseKey: string;
  sessions: Array<{
    id: string;
    /** Original session-level date, retained alongside its UTC interpretation. */
    date: string;
    timestamp: number;
    turns: Array<{ role: 'user' | 'assistant'; content: string }>;
  }>;
}
export interface EvaluationQuestion { id: string; text: string; date: string }
export interface EvaluationLimits {
  timeoutMs: number;
  maxModelCalls: number;
  /** Per-request output ceiling; input tokens and fees are measured separately. */
  maxOutputTokens: number;
}
export interface EvaluationUsage {
  modelCalls: number;
  inputTokens: number | null;
  outputTokens: number | null;
  costUsd: number | null;
  elapsedMs: number;
}
export interface PreparationReceipt {
  candidateId: string;
  /** SHA-256 of UTF-8 JSON.stringify of the received EvaluationHistory. */
  historyDigest: string;
  importedSessions: number;
  importedMessages: number;
  evidenceRef: string;
  usage: EvaluationUsage;
}
export type PreparationResult = {
  status: 'ready'; preparedRef: string; receipt: PreparationReceipt;
} | {
  status: 'incomplete' | 'failed'; preparedRef?: string; receipt?: PreparationReceipt; reason: string;
};
export type EvaluationAnswer = {
  status: 'completed'; text: string; evidenceRef: string; usage: EvaluationUsage;
} | {
  status: 'failed'; reason: string; evidenceRef?: string; usage?: EvaluationUsage;
};
/** Each operation owns its limits; close also cancels an unfinished operation. */
export interface MemoryCandidate {
  readonly id: string;
  prepare(history: EvaluationHistory, limits: EvaluationLimits): Promise<PreparationResult>;
  answer(preparedRef: string, question: EvaluationQuestion, limits: EvaluationLimits): Promise<EvaluationAnswer>;
  /** Release handles after success, rejection or timeout; omitted ref covers failed preparation. */
  close(preparedRef?: string): Promise<void>;
}
