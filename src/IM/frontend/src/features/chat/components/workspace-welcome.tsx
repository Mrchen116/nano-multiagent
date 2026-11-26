import { AssistantIllustration, Avatar, agentAvatarId } from "./avatar";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, MessagesSquare } from 'lucide-react';
import { useTranslation } from '../../../i18n';
import type { Conversation } from '../chat-types';
import { conversationPreview } from './conversation-preview';
import { AssistantStarters } from './assistant-starters';
import './workspace-welcome.css';

/** Surface a real recent conversation and editable starting points. */
export function WorkspaceWelcome({ assistant, conversation, onStart, onNewChat }: {
  assistant: { display_name: string; conversation_id: string; agent_id: string; avatar_variant?: number | null } | null;
  conversation?: Conversation;
  onStart(text: string): Promise<void>;
  onNewChat(): void;
}) {
  const { t } = useTranslation();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const preview = conversation ? conversationPreview(conversation, t) : '';
  const returning = !!conversation?.last_message_at;
  async function start(text: string) {
    setStarting(true); setError(null);
    try { await onStart(text); }
    catch { setError(t('assistantStart.openError')); }
    finally { setStarting(false); }
  }
  return <section className="workspace-welcome" aria-labelledby="workspace-welcome-title">
    <div className="workspace-welcome-content">
      <div className="workspace-welcome-drawing" aria-hidden="true">
        <span className="workspace-welcome-paper"><span /><span /><span /></span>
        <span className="workspace-welcome-pal">{assistant ? <Avatar id={agentAvatarId(assistant.agent_id)} size={88} /> : <AssistantIllustration size={88} />}</span>
        <span className="workspace-welcome-reply"><MessagesSquare /></span>
        <span className="workspace-welcome-dot" />
      </div>
      <h1 id="workspace-welcome-title">{t(returning ? 'workspaceWelcome.returnTitle' : 'workspaceWelcome.title')}</h1>
      <p>{t(returning ? 'workspaceWelcome.returnIntro' : 'workspaceWelcome.intro')}</p>
      <div className="workspace-welcome-actions">
        <Link className="workspace-welcome-personal" to={assistant ? `/chat/${assistant.conversation_id}` : '/onboarding'}>
          <span className="workspace-welcome-action-icon" aria-hidden="true">{assistant ? <Avatar id={agentAvatarId(assistant.agent_id)} size={42} /> : <AssistantIllustration size={42} />}</span>
          <span><strong>{conversation?.title || assistant?.display_name || t('workspaceWelcome.setup')}{returning && <small className="workspace-welcome-recent-label">{t('workspaceWelcome.recent')}</small>}</strong><small className="workspace-welcome-preview">{preview || t('workspaceWelcome.personal')}</small></span><ArrowUpRight aria-hidden="true" />
        </Link>
      </div>
      {assistant && <AssistantStarters disabled={starting} onStart={text => void start(text)} />}
      {error && <p role="alert" className="workspace-welcome-error">{error}</p>}
      <button className="workspace-welcome-team" type="button" onClick={onNewChat}><MessagesSquare size={16} aria-hidden="true" />{t('workspaceWelcome.newChat')}<ArrowUpRight size={14} aria-hidden="true" /></button>
    </div>
  </section>;
}
