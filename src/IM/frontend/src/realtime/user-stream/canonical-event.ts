/** Raised when a known canonical event cannot safely enter shared fan-out. */
export class UserStreamRecoveryError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UserStreamRecoveryError";
  }
}

const CHAT_STREAM_EVENT_TYPES = new Set([
  "message.created",
  "message.reconciled",
  "message.delta",
  "message.completed",
  "message.discarded",
  "tool_call.upserted",
  "tool_call.completed",
  "thinking.segment",
  "permission.request",
  "permission.resolved",
  "agent.config.changed"
]);

export function isCanonicalChatStreamEventType(eventType: string): boolean {
  return CHAT_STREAM_EVENT_TYPES.has(eventType);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isNullableRecord(value: unknown): boolean {
  return value === null || isRecord(value);
}

function isToolCall(value: unknown): boolean {
  return isRecord(value)
    && isText(value.id)
    && isText(value.name)
    && isText(value.status)
    && (value.input === undefined || isRecord(value.input));
}

function isThinkingSegment(value: unknown): boolean {
  return isRecord(value)
    && typeof value.seq === "number"
    && Number.isFinite(value.seq)
    && typeof value.text === "string";
}

const BACKGROUND_RETURN_TYPES = new Set(["subagent", "workflow"]);
const BACKGROUND_RETURN_STATUSES = new Set(["completed", "failed", "stopped", "killed"]);

function isOptionalText(value: unknown): boolean {
  return value === undefined || value === null || typeof value === "string";
}

function isOptionalNonNegativeNumber(value: unknown): boolean {
  return value === undefined
    || value === null
    || (typeof value === "number" && Number.isInteger(value) && value >= 0);
}

function isBackgroundReturn(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return isText(value.task_id)
    && typeof value.task_type === "string"
    && BACKGROUND_RETURN_TYPES.has(value.task_type)
    && typeof value.status === "string"
    && BACKGROUND_RETURN_STATUSES.has(value.status)
    && isText(value.description)
    && isOptionalText(value.agent_id)
    && isOptionalText(value.workflow_run_id)
    && isOptionalText(value.result)
    && isOptionalText(value.error)
    && (value.usage === undefined || value.usage === null || isRecord(value.usage))
    && isOptionalNonNegativeNumber(value.tool_use_count)
    && isOptionalNonNegativeNumber(value.duration_ms)
    && isOptionalText(value.output_file)
    && isOptionalText(value.diagnostics)
    && isOptionalText(value.resume_hint)
    && isOptionalNonNegativeNumber(value.seq);
}

function malformed(eventType: string): never {
  throw new UserStreamRecoveryError(`invalid ${eventType} payload`);
}

/** Validate known shared event shapes before cursor advance and subscriber fan-out. */
export function validateCanonicalUserStreamEvent(
  eventType: string,
  payload: Record<string, unknown>
): void {
  if (!isCanonicalChatStreamEventType(eventType)) return;
  if (!isText(payload.conversation_id)) malformed(eventType);
  if (eventType === "agent.config.changed") {
    if (
      !isText(payload.id)
      || !isText(payload.agent_id)
      || !isText(payload.before_message_id)
      || !isText(payload.applied_at)
    ) malformed(eventType);
    return;
  }
  if (!isText(payload.message_id)) malformed(eventType);
  switch (eventType) {
    case "message.created":
    case "message.reconciled":
      if (
        !isText(payload.sender_user_id)
        || !isText(payload.sender_type)
        || typeof payload.content !== "string"
        || !Array.isArray(payload.tool_calls)
        || !payload.tool_calls.every(isToolCall)
        || !isNullableRecord(payload.token_usage)
        || !isText(payload.delivery_status)
        || !isText(payload.created_at)
        || (payload.attachments !== undefined && !Array.isArray(payload.attachments))
        || (payload.thinking !== undefined
          && (!Array.isArray(payload.thinking) || !payload.thinking.every(isThinkingSegment)))
        || (payload.background_returns !== undefined
          && (!Array.isArray(payload.background_returns)
            || !payload.background_returns.every(isBackgroundReturn)))
        || (payload.elapsed_ms !== undefined
          && payload.elapsed_ms !== null
          && (typeof payload.elapsed_ms !== "number" || !Number.isFinite(payload.elapsed_ms)))
        || (payload.kernel_message_id !== undefined
          && payload.kernel_message_id !== null
          && typeof payload.kernel_message_id !== "string")
      ) malformed(eventType);
      if (
        eventType === "message.reconciled"
        && payload.delivery_status !== "completed"
        && payload.delivery_status !== "failed"
      ) malformed(eventType);
      return;
    case "message.delta":
      if (typeof payload.delta_text !== "string") malformed(eventType);
      return;
    case "message.completed":
      if (
        typeof payload.content !== "string"
        || !isNullableRecord(payload.token_usage)
        || (payload.delivery_status !== undefined
          && payload.delivery_status !== "completed"
          && payload.delivery_status !== "failed")
      ) malformed(eventType);
      return;
    case "message.discarded":
      if (!isText(payload.reason)) malformed(eventType);
      return;
    case "tool_call.upserted":
    case "tool_call.completed":
      if (!isToolCall(payload.tool_call)) malformed(eventType);
      return;
    case "thinking.segment":
      if (!isThinkingSegment(payload.thinking_segment)) malformed(eventType);
      return;
    case "permission.request": {
      const request = payload.permission_request;
      if (
        !isRecord(request)
        || !isText(request.request_id)
        || !isText(request.tool_name)
        || !isRecord(request.tool_input)
        || typeof request.question !== "string"
        || !Array.isArray(request.options)
        || (request.status !== "pending" && request.status !== "resolved")
      ) malformed(eventType);
      return;
    }
    case "permission.resolved":
      if (!isText(payload.request_id) || !isText(payload.decision)) malformed(eventType);
  }
}
