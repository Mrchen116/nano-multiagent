import { useState } from 'react';
import { ArrowDown, ArrowRight, BookOpen, Check, FileText, MessageCircle, MessagesSquare, Sparkles } from 'lucide-react';
import { useTranslation } from '../../i18n';
import './companion-scene.css';

const roles = ['personal', 'specialist'] as const;
const chats = ['first', 'second', 'third'] as const;

/** Show one persistent Agent coordinating related work across several IM conversations. */
export function CompanionScene() {
  const { t } = useTranslation();
  const [role, setRole] = useState<typeof roles[number]>('personal');
  const [chat, setChat] = useState<typeof chats[number]>('first');
  const text = (key: string) => t(`crewdenStory.companions.${key}`);
  const person = (key: string) => text(`${role}.${key}`);
  const scene = (key: string) => person(`chats.${chat}.${key}`);
  function selectRole(index: number) { setRole(roles[index]); setChat('first'); }
  return <section className="crew-companions" id="how-it-works" aria-labelledby="crew-companions-title">
    <div className="crew-companions-heading"><h2 id="crew-companions-title">{text('title')}</h2><p>{text('intro')}</p></div>
    <div className="crew-companion-picker" role="tablist" aria-label={text('rolePicker')}>
      {roles.map((item, index) => <button key={item} type="button" role="tab" id={`companion-${item}`} aria-selected={role === item} aria-controls="companion-workspace" tabIndex={role === item ? 0 : -1} onClick={() => selectRole(index)} onKeyDown={event => {
        const next = event.key === 'ArrowRight' || event.key === 'ArrowLeft' ? 1 - index : event.key === 'Home' ? 0 : event.key === 'End' ? 1 : null;
        if (next === null) return;
        event.preventDefault(); selectRole(next); document.getElementById(`companion-${roles[next]}`)?.focus();
      }}><span className={`crew-companion-face is-${item}`} aria-hidden="true"><CompanionFace specialist={item === 'specialist'} /></span><span><strong>{text(`${item}.title`)}</strong><small>{text(`${item}.subtitle`)}</small></span><ArrowRight aria-hidden="true" /></button>)}
    </div>
    <div className={`crew-im-demo is-${role}`} id="companion-workspace" role="tabpanel" aria-labelledby={`companion-${role}`} tabIndex={0}>
      <div className="crew-im-demo-bar"><span><MessagesSquare />{text('workspace')}</span><small>{text('example')}</small></div>
      <div className="crew-im-demo-body">
        <nav className="crew-demo-chats" aria-label={text('chatPicker')}>
          <div className="crew-demo-chats-label">{text('chats')}<span>3</span></div>
          {chats.map((item, index) => <button key={item} type="button" aria-pressed={chat === item} onClick={() => setChat(item)}><span className={`crew-chat-color tone-${index}`} aria-hidden="true"><MessageCircle /></span><span><strong>{person(`chats.${item}.channel`)}</strong><small>{person(`chats.${item}.preview`)}</small></span><i aria-hidden="true" /></button>)}
          <p className="crew-demo-switch-hint">{text('switchHint')}<ArrowRight aria-hidden="true" /></p>
        </nav>
        <div className="crew-demo-thread" aria-live="polite">
          <header><strong>{scene('channel')}</strong><span>{text('sharedChat')}</span></header>
          <div className="crew-demo-thread-content" key={`${role}-${chat}`}>
            <div className="crew-past-agreement"><BookOpen aria-hidden="true" /><div><small>{text('earlier')}</small><p>{scene('agreement')}</p></div></div>
            <div className="crew-new-message"><div className="crew-message-person"><span aria-hidden="true">{scene('author').slice(0,1)}</span><strong>{scene('author')}</strong><small>{text('newMessage')}</small></div><p>{scene('message')}</p></div>
            <div className="crew-thread-connection"><span /><ArrowDown aria-hidden="true" /><small>{text('proactive')}</small></div>
            <div className="crew-agent-result"><div className="crew-result-author"><span className={`crew-companion-face is-${role}`} aria-hidden="true"><CompanionFace specialist={role === 'specialist'} /></span><strong>{person('name')}</strong><small>{text('continued')}</small></div><p>{scene('result')}</p><div className="crew-result-file"><FileText aria-hidden="true" /><span>{scene('artifact')}</span><Check aria-hidden="true" /></div><div className="crew-result-destination"><ArrowRight aria-hidden="true" />{text('returnTo')} {scene('destination')}</div></div>
          </div>
        </div>
        <aside className="crew-persistent-agent" aria-label={text('sameAgent')}>
          <div className="crew-persistent-identity"><span className={`crew-companion-face is-${role}`} aria-hidden="true"><CompanionFace specialist={role === 'specialist'} /></span><div><strong>{person('name')}</strong><span>{person('identity')}</span></div></div>
          <p className="crew-persistent-duty">{person('duty')}</p>
          <div className="crew-concurrent-heading"><strong>{text('ongoing')}</strong><span>3</span></div>
          <ul className="crew-concurrent-work">{chats.map(item => <li key={item} className={item === chat ? 'is-related' : ''}><span aria-hidden="true" /><div><strong>{person(`chats.${item}.task`)}</strong><small>{person(`chats.${item}.progress`)}</small></div>{item === chat && <ArrowRight aria-hidden="true" />}</li>)}</ul>
          <div className="crew-agent-memory"><BookOpen aria-hidden="true" /><div><small>{text('memory')}</small><p>{person('memory')}</p></div></div>
          <div className="crew-agent-persistence"><span /><strong>{text('sameAgent')}</strong></div>
        </aside>
      </div>
    </div>
    <div className="crew-shared-qualities" id="capabilities"><span><BookOpen />{text('remember')}</span><span><Sparkles />{text('notice')}</span><span><MessagesSquare />{text('coordinate')}</span></div>
    <p className="crew-companions-note">{text('scope')}</p>
  </section>;
}

function CompanionFace({ specialist }: { specialist: boolean }) {
  return <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <path d={specialist ? 'M9 11h22v18H9z' : 'M9 27V16c0-7 22-7 22 0v11'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M15 19v3m10-3v3" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" />
    <path d={specialist ? 'M17 27h6' : 'M17 27q3 3 6 0'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    {specialist ? <path d="m27 8 4-3 3 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /> : <circle cx="30" cy="7" r="3" fill="#f0bb54" />}
  </svg>;
}
