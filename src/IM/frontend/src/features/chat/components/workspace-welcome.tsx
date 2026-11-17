import { Link } from 'react-router-dom';
import { ArrowUpRight, MessagesSquare } from 'lucide-react';
import { NanoBrand } from '../../../app/shell/nano-brand';
import { useTranslation } from '../../../i18n';
import './workspace-welcome.css';

/** Offer real starting points when no conversation is selected. */
export function WorkspaceWelcome({ assistant, onNewChat }: {
  assistant: { display_name: string; conversation_id: string } | null;
  onNewChat(): void;
}) {
  const { t } = useTranslation();
  return <section className="workspace-welcome" aria-labelledby="workspace-welcome-title">
    <div className="workspace-welcome-content">
      <div className="workspace-welcome-drawing" aria-hidden="true">
        <span className="workspace-welcome-paper"><span /><span /><span /></span>
        <span className="workspace-welcome-pal"><NanoBrand /></span>
        <span className="workspace-welcome-reply"><MessagesSquare /></span>
        <span className="workspace-welcome-dot" />
      </div>
      <h1 id="workspace-welcome-title">{t('workspaceWelcome.title')}</h1>
      <p>{t('workspaceWelcome.intro')}</p>
      <div className="workspace-welcome-actions">
        <Link className="workspace-welcome-personal" to={assistant ? `/chat/${assistant.conversation_id}` : '/onboarding'}>
          <span className="workspace-welcome-action-icon" aria-hidden="true"><NanoBrand /></span>
          <span><strong>{assistant?.display_name || t('workspaceWelcome.setup')}</strong><small>{t('workspaceWelcome.personal')}</small></span><ArrowUpRight aria-hidden="true" />
        </Link>
        <button type="button" onClick={onNewChat}>
          <span className="workspace-welcome-action-icon" aria-hidden="true"><MessagesSquare /></span>
          <span><strong>{t('workspaceWelcome.newChat')}</strong><small>{t('workspaceWelcome.team')}</small></span><ArrowUpRight aria-hidden="true" />
        </button>
      </div>
    </div>
  </section>;
}
