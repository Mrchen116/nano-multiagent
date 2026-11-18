import { ArrowUpRight, CalendarDays, ListChecks, PencilLine } from 'lucide-react';
import { useTranslation } from '../../../i18n';
import './assistant-starters.css';

/** Offer editable drafts; the caller owns navigation and existing-draft protection. */
export function AssistantStarters({ disabled = false, onStart }: {
  disabled?: boolean;
  onStart(text: string): void;
}) {
  const { t } = useTranslation();
  return <div className="assistant-starters">
    <div className="assistant-starters-options">
      {([['untangle', PencilLine], ['plan', CalendarDays], ['next', ListChecks]] as const).map(([key, Icon]) =>
        <button type="button" key={key} className={`assistant-starter assistant-starter--${key}`} disabled={disabled}
          onClick={() => onStart(t(`assistantStart.${key}.prompt`))}>
          <span className="assistant-starter-icon"><Icon size={19} aria-hidden="true" /></span>
          <span><strong>{t(`assistantStart.${key}.title`)}</strong><small>{t(`assistantStart.${key}.hint`)}</small></span>
          <ArrowUpRight size={15} aria-hidden="true" />
        </button>)}
    </div>
    <p className="assistant-starters-note">{t(disabled ? 'assistantStart.keepDraft' : 'assistantStart.note')}</p>
  </div>;
}
