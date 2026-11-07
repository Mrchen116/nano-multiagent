import { useState } from 'react';
import { useTranslation } from '../../../i18n';
import { adoptRemoteDraft, describeDraftConflict, retryDraft, useDraftFailures } from '../interaction-background';

/** Tell the user, at the send button, why this conversation cannot send yet.
 *
 * A card can be scrolled out of view, so its own inline save error is not enough: without
 * this bar the user presses send and gets a message that silently lacks the edit. Copy and
 * actions follow the failure cause, because retrying a 409 with a stale revision can only
 * fail again — that path must offer "look, then explicitly discard".
 */
export function DraftFailureNotice({ conversationId }: { conversationId: string }) {
  const { t } = useTranslation();
  const failures = useDraftFailures(conversationId);
  const [compareFor, setCompareFor] = useState<string | null>(null);
  const [columns, setColumns] = useState<{ label: string; remote: string; local: string }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [readFailed, setReadFailed] = useState(false);
  if (!failures.length) return null;
  // A conflict needs a decision, so it takes over the bar until it is resolved.
  const entry = failures.find(failure => failure.reason === 'conflict') ?? failures[0];
  const conflict = entry.reason === 'conflict';
  const card = t('chat.messagePane.untitledCard');
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false;

  async function look() {
    setBusy(true); setReadFailed(false);
    try { setColumns((await describeDraftConflict(conversationId, entry.messageId)).columns); setCompareFor(entry.messageId); }
    catch { setColumns(null); setReadFailed(true); }
    finally { setBusy(false); }
  }
  async function adopt() {
    setBusy(true); setReadFailed(false);
    try { await adoptRemoteDraft(conversationId, entry.messageId); setColumns(null); setCompareFor(null); }
    catch { setReadFailed(true); }
    finally { setBusy(false); }
  }

  return <div className={`draft-failure draft-failure-${entry.reason}`} role="alert">
    <strong>{t(conflict ? 'chat.messagePane.conflictTitle' : 'chat.messagePane.transientTitle')}</strong>
    <span>{t(conflict ? 'chat.messagePane.conflictBody' : 'chat.messagePane.transientBody', { card })}</span>
    {!conflict && offline && <span>{t('chat.messagePane.transientOffline')}</span>}
    {readFailed && <span>{t('chat.interactive.loadError')}</span>}
    {conflict ? <>
      {compareFor !== entry.messageId && <button type="button" disabled={busy} onClick={() => void look()}>
        {t('chat.messagePane.viewLatest')}</button>}
      {compareFor === entry.messageId && columns && <table className="draft-failure-compare">
        <thead><tr>
          <th>{t('chat.messagePane.conflictField')}</th>
          <th>{t('chat.messagePane.conflictRemote')}</th>
          <th>{t('chat.messagePane.conflictLocal')}</th>
        </tr></thead>
        <tbody>{columns.map(column => <tr key={column.label}>
          <td>{column.label}</td><td>{column.remote}</td><td>{column.local}</td>
        </tr>)}</tbody>
      </table>}
      {compareFor === entry.messageId && <button type="button" disabled={busy} onClick={() => void adopt()}>
        {t('chat.messagePane.adoptRemote')}</button>}
    </> : <button type="button" disabled={busy} onClick={() => void retryDraft(conversationId, entry.messageId)}>
      {t('chat.messagePane.retrySave')}</button>}
  </div>;
}
