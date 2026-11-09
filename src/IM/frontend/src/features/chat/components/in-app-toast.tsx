import { useEffect } from "react";
import { Link } from "react-router-dom";

/** Auto-dismiss delay in milliseconds. */
const AUTO_DISMISS_MS = 4000;

interface InAppToastProps {
  /** Current name of the conversation that received the message. */
  conversationTitle: string;
  /** Group message sender; omitted for direct conversations. */
  senderName?: string;
  /** Short preview text of the message. */
  preview: string;
  /** Conversation to navigate to when the toast is clicked. */
  conversationId: string;
  /** Called when the toast should be removed (auto-dismiss or user action). */
  onDismiss: () => void;
}

/**
 * In-app notification toast shown in the top-left corner when a new message
 * arrives while the user is viewing a different page.
 *
 * Does not require browser Notification permission — purely in-app.
 * Auto-dismisses after AUTO_DISMISS_MS milliseconds.
 */
export function InAppToast({ conversationTitle, senderName, preview, conversationId, onDismiss }: InAppToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed left-4 top-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] items-start gap-3 rounded-2xl border border-[var(--im-border)] bg-white px-4 py-3 shadow-lg"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-semibold text-slate-900" title={conversationTitle}>{conversationTitle}</p>
        <p className="mt-0.5 line-clamp-2 break-words text-xs text-slate-600">
          {senderName ? `${senderName}: ${preview}` : preview}
        </p>
        <Link
          to={`/chat/${conversationId}`}
          aria-label="View message"
          className="mt-1 block text-xs font-semibold text-emerald-700 underline underline-offset-2"
          onClick={onDismiss}
        >
          View message
        </Link>
      </div>
      <button
        type="button"
        aria-label="Dismiss notification"
        className="shrink-0 rounded-full p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
        onClick={onDismiss}
      >
        ×
      </button>
    </div>
  );
}
