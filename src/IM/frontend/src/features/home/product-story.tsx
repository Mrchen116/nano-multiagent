import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Check, ChevronDown, FileText, GitBranch, Laptop, LockKeyhole, MessageCircle, MessagesSquare, SlidersHorizontal, Sparkles, Users } from 'lucide-react';
import { useTranslation } from '../../i18n';
import './product-story.css';

const participants = ['people', 'assistant', 'colleagues'] as const;
type Participant = typeof participants[number];
type Text = (key: string) => string;

/** Explain product roles and ongoing work using explicitly illustrative product surfaces. */
export function ProductStorySections() {
  const { t } = useTranslation();
  const text: Text = key => t(`crewdenStory.${key}`);
  const [participant, setParticipant] = useState<Participant>('assistant');
  return <>
    <section className="crew-team-section" id="how-it-works" aria-labelledby="crew-team-title">
      <div className="crew-section-heading"><h2 id="crew-team-title">{text('team.title')}</h2><p>{text('team.intro')}</p></div>
      <div className="crew-team-layout">
        <div className="crew-role-choices" role="tablist" aria-label={text('team.navigation')} aria-orientation="vertical">
          {participants.map((key, index) => <button type="button" key={key} id={`crew-role-${key}`} role="tab" aria-selected={participant === key} aria-controls="crew-role-panel" tabIndex={participant === key ? 0 : -1} onClick={() => setParticipant(key)} onKeyDown={event => {
            const next = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? (index + 1) % participants.length : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? (index + participants.length - 1) % participants.length : event.key === 'Home' ? 0 : event.key === 'End' ? participants.length - 1 : null;
            if (next === null) return;
            event.preventDefault(); setParticipant(participants[next]); document.getElementById(`crew-role-${participants[next]}`)?.focus();
          }}>
            <span className={`crew-role-icon crew-role-icon--${key}`}>{key === 'people' ? <Users /> : key === 'assistant' ? <Sparkles /> : <GitBranch />}</span>
            <span><strong>{text(`team.${key}.title`)}</strong><span>{text(`team.${key}.summary`)}</span></span>
          </button>)}
        </div>
        <div className="crew-role-panel" id="crew-role-panel" role="tabpanel" tabIndex={0} aria-labelledby={`crew-role-${participant}`}>
          <div className="crew-workplace">
            <div className="crew-workplace-top"><span><MessagesSquare />{text('team.workspace')}</span><small>{text('example')}</small></div>
            <div className="crew-workplace-layout">
              <aside className="crew-workplace-sidebar" aria-label={text('team.workspace')}>
                <span>{text('team.private')}</span><div className={participant === 'assistant' ? 'is-current' : ''}><Sparkles />{text('team.pa')}</div>
                <span>{text('team.shared')}</span><div className={participant === 'people' ? 'is-current' : ''}><span>#</span>{text('team.release')}</div><div className={participant === 'colleagues' ? 'is-current' : ''}><span>#</span>{text('team.quality')}</div>
                <p><LockKeyhole />{text('team.privateNote')}</p>
              </aside>
              <RoleConversation participant={participant} text={text} />
            </div>
          </div>
          <p className="crew-role-explanation">{text(`team.${participant}.detail`)}</p>
        </div>
      </div>
    </section>

    <section className="crew-continuity-section" id="capabilities" aria-labelledby="crew-continuity-title">
      <div className="crew-continuity-layout">
        <div className="crew-continuity-copy"><h2 id="crew-continuity-title">{text('continuity.title')}</h2><p>{text('continuity.intro')}</p>
          <dl>{(['context', 'parallel', 'memory', 'control'] as const).map((key, index) => <div key={key}>
            <dt>{index === 0 ? <MessagesSquare /> : index === 1 ? <GitBranch /> : index === 2 ? <BookOpen /> : <SlidersHorizontal />}{text(`continuity.${key}.title`)}</dt><dd>{text(`continuity.${key}.body`)}</dd>
          </div>)}</dl>
        </div>
        <div className="crew-work-journal" aria-label={text('continuity.exampleLabel')}>
          <div className="crew-journal-heading"><div><Sparkles /><strong>{text('continuity.journalTitle')}</strong></div><small>{text('example')}</small></div>
          <p className="crew-journal-date">{text('continuity.today')}</p>
          <div className="crew-journal-event"><span className="crew-event-dot" /><div><strong>{text('continuity.changeTitle')}</strong><p>{text('continuity.changeBody')}</p><span className="crew-source"><MessageCircle />{text('continuity.changeSource')}</span></div></div>
          <div className="crew-journal-tasks">
            <div><span className="crew-work-state is-running">{text('continuity.running')}</span><div><strong>{text('continuity.taskOne')}</strong><small>{text('continuity.taskOneNote')}</small></div></div>
            <div><span className="crew-work-state is-waiting">{text('continuity.waiting')}</span><div><strong>{text('continuity.taskTwo')}</strong><small>{text('continuity.taskTwoNote')}</small></div></div>
            <div><span className="crew-work-state is-done">{text('continuity.prepared')}</span><div><strong>{text('continuity.taskThree')}</strong><small>{text('continuity.taskThreeNote')}</small></div></div>
          </div>
          <div className="crew-journal-memory"><BookOpen /><div><strong>{text('continuity.memoryLabel')}</strong><p>{text('continuity.memoryExample')}</p><small>{text('continuity.memorySource')}</small></div></div>
          <div className="crew-journal-delivery"><FileText /><span>{text('continuity.delivery')}</span><Check /></div>
        </div>
      </div>
    </section>

    <section className="crew-use-section" aria-labelledby="crew-use-title">
      <div className="crew-section-heading"><h2 id="crew-use-title">{text('uses.title')}</h2><p>{text('uses.intro')}</p></div>
      <div className="crew-use-columns">{['product', 'projects', 'research'].map(key => <article key={key}>
        <h3>{text(`uses.${key}.title`)}</h3><blockquote>{text(`uses.${key}.request`)}</blockquote><p>{text(`uses.${key}.outcome`)}</p><div><FileText />{text(`uses.${key}.artifact`)}</div>
      </article>)}</div>
    </section>

    <section className="crew-setup-section" id="getting-started" aria-labelledby="crew-setup-title">
      <div className="crew-section-heading"><h2 id="crew-setup-title">{text('setup.title')}</h2><p>{text('setup.intro')}</p></div>
      <ol className="crew-setup-steps">{['account', 'computer', 'assistant'].map((key, index) => <li key={key}><span>{index + 1}</span><div><h3>{text(`setup.${key}.title`)}</h3><p>{text(`setup.${key}.body`)}</p></div></li>)}</ol>
      <div className="crew-setup-bottom"><div className="crew-setup-requirements"><Laptop /><p>{text('setup.requirements')}</p></div><Link className="crew-primary" to="/register">{t('auth.register.submit')}</Link></div>
    </section>

    <section className="crew-questions-section" id="questions" aria-labelledby="crew-questions-title">
      <div className="crew-section-heading"><h2 id="crew-questions-title">{text('questions.title')}</h2><p>{text('questions.intro')}</p></div>
      <div className="crew-questions">{['solo', 'ready', 'models', 'privacy', 'offline', 'roles'].map(key => <details key={key}><summary>{text(`questions.${key}.question`)}<ChevronDown /></summary><p>{text(`questions.${key}.answer`)}</p></details>)}</div>
    </section>
  </>;
}

function RoleConversation({ participant, text }: { participant: Participant; text: Text }) {
  const privateView = participant === 'assistant';
  return <div className="crew-conversation-example">
    <header>{privateView ? <LockKeyhole /> : <MessagesSquare />}<strong>{text(`team.${participant}.channel`)}</strong><small>{text(privateView ? 'team.onlyYou' : 'team.group')}</small></header>
    <div className="crew-example-messages">
      <div className="crew-example-message"><span className="crew-example-person">{text('team.youInitial')}</span><div><strong>{text('team.you')}</strong><p>{text(`team.${participant}.request`)}</p></div></div>
      <div className="crew-example-message"><span className={`crew-example-bot ${privateView ? 'is-personal' : ''}`}>{privateView ? <Sparkles /> : <GitBranch />}</span><div><strong>{text(`team.${participant}.replyName`)}</strong><p>{text(`team.${participant}.reply`)}</p></div></div>
      <div className="crew-example-result"><span>{participant === 'assistant' ? <BookOpen /> : participant === 'colleagues' ? <Check /> : <FileText />}</span><div><strong>{text(`team.${participant}.result`)}</strong><small>{text(`team.${participant}.resultNote`)}</small></div></div>
    </div>
    <div className="crew-example-composer" aria-hidden="true"><span>{text('team.composer')}</span><span>↵</span></div>
  </div>;
}
