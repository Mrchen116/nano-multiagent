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
 *
 * Visual: 方案 B 深色卡，对齐 chat-tool-calls-* 体系。All styles live in global.css
 * under the chat-permission-* prefix — no inline Tailwind utilities.
 */
import React, { useState } from "react";

import { authFetch } from "../../../auth/auth-fetch";
import { useTranslation } from "../../../../i18n";

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
  const { t } = useTranslation();
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
      const message = err instanceof Error ? err.message : t("chat.permission.submitError");
      setCardState({ kind: "error", chosenId: option.id, message });
    }
  }

  if (cardState.kind === "resolved") {
    const isDeny = cardState.decision === "deny";
    return (
      <div className="chat-permission-card chat-permission-card--resolved">
        <span
          data-testid="permission-resolved"
          className={`chat-permission-resolved-label${isDeny ? " chat-permission-resolved-label--deny" : ""}`}
        >
          {isDeny
            ? `${t("chat.permission.denied")} · ${request.tool_name}`
            : `${t("chat.permission.allowed")} · ${request.tool_name}`}
        </span>
      </div>
    );
  }

  const isSubmitting = cardState.kind === "submitting";
  const errorMessage = cardState.kind === "error" ? cardState.message : null;

  return (
    <div
      className="chat-permission-card"
      role="region"
      aria-label={t("chat.permission.ariaCard", { toolName: request.tool_name })}
    >
      <div className="chat-permission-header">
        <span aria-hidden="true">🔒</span>
        <span className="chat-permission-tool-name">{request.tool_name}</span>
        <span className="chat-permission-hint">{t("chat.permission.hint")}</span>
      </div>
      <p className="chat-permission-question">{request.question}</p>
      {errorMessage && (
        <div role="alert" className="chat-permission-error">
          {errorMessage}
        </div>
      )}
      <div className="chat-permission-options" role="group" aria-label={t("chat.permission.ariaOptions")}>
        {request.options.map((opt) => {
          const isChosen = isSubmitting && (cardState as { chosenId: string }).chosenId === opt.id;
          // Determine button variant: allow_once → primary, deny → danger, others → default
          const variant =
            opt.id === "allow_once" ? " chat-permission-btn--primary"
            : opt.id === "deny" ? " chat-permission-btn--danger"
            : "";
          return (
            <button
              key={opt.id}
              type="button"
              className={`chat-permission-btn${variant}`}
              onClick={() => handleChoice(opt)}
              disabled={isSubmitting}
              aria-busy={isChosen}
              title={opt.description}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
