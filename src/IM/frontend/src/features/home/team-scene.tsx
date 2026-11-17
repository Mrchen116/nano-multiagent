import { useState } from 'react';
import { ArrowLeft, ArrowRight, Check, FileText, LockKeyhole, MessagesSquare, RotateCcw, ShieldCheck, Sparkles } from 'lucide-react';
import { useTranslation } from '../../i18n';
import './team-scene.css';

const steps = ['goal', 'parallel', 'decision', 'ready'] as const;
type Actor = 'you' | 'milo' | 'lan' | 'noah' | 'qing';
const rooms = ['personal', 'project', 'colleague'] as const;
const speakers: Record<typeof steps[number], Record<typeof rooms[number], readonly Actor[]>> = {
  goal: { personal: ['you', 'milo'], project: ['milo', 'noah'], colleague: ['lan', 'noah'] },
  parallel: { personal: ['milo', 'you'], project: ['qing', 'noah'], colleague: ['noah', 'lan'] },
  decision: { personal: ['milo', 'you'], project: ['lan', 'you'], colleague: ['lan', 'noah'] },
  ready: { personal: ['milo', 'you'], project: ['qing', 'milo'], colleague: ['noah', 'lan'] },
};

/** Illustrate a team handoff locally, without creating work or publishing messages. */
export function TeamScene() {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const current = steps[step];
  const text = (key: string) => t(`crewdenStory.team.${key}`);
  const scene = (key: string) => text(`stages.${current}.${key}`);
  function moveTo(next: number) {
    setStep(next);
    // The next chapter must be visible when controls sit below long mobile chats.
    const content = document.getElementById('team-scene-content');
    if (content && content.getBoundingClientRect().top < 0) content.scrollIntoView({ behavior: 'instant', block: 'start' });
  }
  function face(actor: Actor) {
    return <span className={`team-face team-face--${actor}`} aria-hidden="true">{actor === 'qing' ? <ShieldCheck /> : actor === 'milo' || actor === 'noah' ? <Sparkles /> : text(`actors.${actor}.initial`)}</span>;
  }
  return <section className="crew-team" id="teamwork" aria-labelledby="crew-team-title">
    <div className="crew-team-heading"><h2 id="crew-team-title">{text('title')}</h2><p>{text('intro')}</p></div>
    <div className="crew-team-story">
      <div className="team-story-top"><span><MessagesSquare aria-hidden="true" />{text('scenario')}</span><small>{text('example')}</small></div>
      <div className="team-steps" role="group" aria-label={text('stepPicker')}>
        {steps.map((item, index) => <button type="button" key={item} aria-pressed={step === index} aria-controls="team-scene-content" onClick={() => setStep(index)}><span>{index < step ? <Check aria-hidden="true" /> : index + 1}</span>{text(`stages.${item}.label`)}{index < 3 && <ArrowRight aria-hidden="true" />}</button>)}
      </div>
      <div id="team-scene-content" className={`team-scene-content is-${current}`}>
        <div className="team-scene-summary" aria-live="polite"><span>{text('chapter')} {step + 1} / 4</span><h3>{scene('title')}</h3><p>{scene('summary')}</p></div>
        <div className="team-rooms">
          {rooms.map(room => <section className={`team-room team-room--${room}`} key={room} aria-labelledby={`team-room-${room}`}>
            <header>
              <div className="team-room-icon" aria-hidden="true">{room === 'project' ? <MessagesSquare /> : <LockKeyhole />}</div>
              <div><h4 id={`team-room-${room}`}>{text(`rooms.${room}.title`)}</h4><p>{text(`rooms.${room}.subtitle`)}</p></div>
            </header>
            <div className="team-room-messages">
              {speakers[current][room].map((actor, index) => <article className="team-message" key={`${actor}-${index}`}>
                <div className="team-message-author">{face(actor)}<div><strong>{text(`actors.${actor}.name`)}</strong><small>{text(`actors.${actor}.role`)}</small></div></div>
                <p>{scene(`${room}.${index}`)}</p>
              </article>)}
            </div>
            <div className="team-room-handoff"><ArrowRight aria-hidden="true" /><span>{scene(`handoffs.${room}`)}</span></div>
          </section>)}
        </div>
        <div className="team-shared-plan">
          <span className="team-plan-icon"><FileText aria-hidden="true" /></span>
          <div><strong>{text('plan')}</strong><p>{scene('plan')}</p></div>
          <span className={`team-plan-status ${step === 3 ? 'is-ready' : ''}`}>{step === 3 && <Check aria-hidden="true" />}{scene('status')}</span>
        </div>
      </div>
      <div className="team-story-controls"><p>{scene('benefit')}</p><div><button type="button" className="team-back" aria-label={text('previous')} disabled={step === 0} onClick={() => moveTo(step - 1)}><ArrowLeft aria-hidden="true" /></button><button type="button" className="team-next" onClick={() => moveTo((step + 1) % steps.length)}>{text(step === 3 ? 'restart' : 'next')}{step === 3 ? <RotateCcw aria-hidden="true" /> : <ArrowRight aria-hidden="true" />}</button></div></div>
    </div>
    <p className="team-scene-note">{text('scope')}</p>
  </section>;
}
