/** A definite conflict can be resolved without replaying an uncertain request. */
export class InteractionSubmissionError extends Error {
  constructor(readonly reason: 'alreadySubmitted' | 'stale', readonly submissionMessageId?: string) {
    super(reason);
  }
}
