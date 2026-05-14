/**
 * PermissionCard: inline permission request card rendered inside agent message bubbles.
 *
 * Design: decisions 7 & 8 of feat-333 design.md.
 * State machine: pending → submitting → resolved (or pending → error → pending).
 *
 * The card POSTs the user's decision to
 *   POST /im/v1/conversations/{conversationId}/permissions/{requestId}
 * which the IM backend forwards to PA → agent inbound to unpark the hook.
 *
 * The default fetchFn uses authFetch (which injects the Authorization: Bearer header
 * from the auth store) so the IM backend's JWT guard does not reject the request.
 * Tests can override fetchFn to inject a mock without touching the auth store.
 */
import React, { useState } from "react";

import { authFetch } from "../../../auth/auth-fetch";

import type { PermissionOption, PermissionRequest } from "../chat-types";

export interface PermissionCardProps {
  request: PermissionRequest;
  conversationId: string;
  messageId: string;
  /** Called with the chosen decision string after a successful POST. */
  onResolved(decision: string): void;
  /** Test seam: override fetch. Defaults to authFetch (injects Authorization header). */
  fetchFn?: (url: string, init?: RequestInit) => Promise<Response>;
}

type CardState =
  | { kind: "pending" }
  | { kind: "submitting"; chosenId: string }
  | { kind: "resolved"; decision: string }
  | { kind: "error"; chosenId: string; message: string };

function initialState(request: PermissionRequest): CardState {
  if (request.status === "resolved") {
    return { kind: "resolved", decision: request.decision ?? "" };
  }
  return { kind: "pending" };
}

/**
 * Inline permission request card shown below an agent message while the agent
 * is awaiting a user decision (auto_mode_gate ask flow).
 */
export function PermissionCard({
  request,
  conversationId,
  messageId,
  onResolved,
  // authFetch is the default so that the IM backend's JWT guard sees the
  // Authorization header.  Tests inject a mock via this prop to avoid
  // touching the auth store in jsdom.
  fetchFn = authFetch,
}: PermissionCardProps) {
  const [cardState, setCardState] = useState<CardState>(() => initialState(request));

  async function handleChoice(option: PermissionOption) {
    setCardState({ kind: "submitting", chosenId: option.id });
    try {
      const resp = await fetchFn(
        `/im/v1/conversations/${conversationId}/permissions/${request.request_id}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message_id: messageId, decision: option.id }),
        }
      );
      if (!resp.ok) {
        const text = await resp.text().catch(() => "Unknown error");
        throw new Error(text || `HTTP ${resp.status}`);
      }
      setCardState({ kind: "resolved", decision: option.id });
      onResolved(option.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to submit decision";
      setCardState({ kind: "error", chosenId: option.id, message });
    }
  }

  if (cardState.kind === "resolved") {
    const isDeny = cardState.decision === "deny";
    return (
      <div className="permission-card permission-card--resolved">
        <span
          data-testid="permission-resolved"
          className={`permission-card__resolved-label ${isDeny ? "permission-card__resolved-label--deny" : "permission-card__resolved-label--allow"}`}
        >
          {isDeny ? `Denied · ${request.tool_name}` : `Allowed · ${request.tool_name}`}
        </span>
      </div>
    );
  }

  const isSubmitting = cardState.kind === "submitting";
  const errorMessage = cardState.kind === "error" ? cardState.message : null;

  return (
    <div className="permission-card permission-card--pending" role="region" aria-label={`Permission request: ${request.tool_name}`}>
      <div className="permission-card__header">
        <span className="permission-card__tool-icon" aria-hidden="true">🔒</span>
        <span className="permission-card__tool-name">{request.tool_name}</span>
      </div>
      <p className="permission-card__question">{request.question}</p>
      {errorMessage && (
        <div role="alert" className="permission-card__error">
          {errorMessage}
        </div>
      )}
      {/* gap-2 provides 0.5rem between option buttons; matches project button-group spacing convention */}
      <div className="permission-card__options flex flex-wrap gap-2" role="group" aria-label="Permission options">
        {request.options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            className={`permission-card__option-btn permission-card__option-btn--${opt.id}`}
            onClick={() => handleChoice(opt)}
            disabled={isSubmitting}
            aria-busy={isSubmitting && (cardState as { chosenId: string }).chosenId === opt.id}
            title={opt.description}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
