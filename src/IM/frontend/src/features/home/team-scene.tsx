import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, FileText, MessagesSquare, Pause, Play, RotateCcw, Send, ShieldCheck } from 'lucide-react';
import { useTranslation } from '../../i18n';
import './team-scene.css';

const actors = ['you', 'milo', 'qing', 'noah', 'lan'] as const;
type Actor = typeof actors[number];
const duration = [2600, 1800, 3800, 0, 2600, 0];
const activeActors: Actor[][] = [['you'], ['milo'], ['milo', 'qing', 'noah'], ['you', 'lan'], ['milo', 'qing', 'noah'], [...actors]];

/** Play a local collaboration illustration, stopping for the visitor's decision. */
export function TeamScene() {
  const { t } = useTranslation();
  const text = (key: string) => t(`crewdenStory.team.${key}`);
  const [phase, setPhase] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [visible, setVisible] = useState(false);
  const [foreground, setForeground] = useState(true);
  const [reduced, setReduced] = useState(false);
  const stage = useRef<HTMLDivElement>(null);
  const running = playing && visible && foreground && !reduced;

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const motion = () => setReduced(media?.matches ?? false);
    const visibility = () => setForeground(!document.hidden);
    motion(); visibility();
    media?.addEventListener('change', motion);
    document.addEventListener('visibilitychange', visibility);
    return () => {
      media?.removeEventListener('change', motion);
      document.removeEventListener('visibilitychange', visibility);
    };
  }, []);

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') { setVisible(true); return; }
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting && entry.intersectionRatio >= .45), { threshold: .45 });
    if (stage.current) observer.observe(stage.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!running || !duration[phase]) return;
    const timer = window.setTimeout(() => setPhase(current => current + 1), duration[phase]);
    return () => window.clearTimeout(timer);
  }, [phase, running]);

  function advance() { setPhase(current => current + 1); setPlaying(true); }
  function replay() { setPhase(0); setPlaying(true); }

  return <section className="crew-team-film" id="teamwork" aria-labelledby="crew-team-title">
    <div className="team-film-heading"><h2 id="crew-team-title">{text('title')}</h2><p>{text('intro')}</p></div>
    <div ref={stage} className={`team-film phase-${phase}`} data-running={running} data-reduced={reduced}>
      <div className="team-film-channel"><MessagesSquare aria-hidden="true" /><span>{text('channel')}</span><small>{text('example')}</small></div>
      <div className="team-film-artboard">
        <div className="team-film-orbit orbit-you" aria-hidden="true" /><div className="team-film-orbit orbit-lan" aria-hidden="true" />
        <svg className="team-film-wires wires-wide" viewBox="0 0 1000 560" preserveAspectRatio="none" aria-hidden="true">
          <path className="owner-link" d="M100 308 Q150 195 280 196 M760 196 Q865 195 910 308" />
          <path className={`work-link ${phase === 2 ? 'is-active' : ''}`} d="M280 196 Q360 94 520 95 M280 196 Q520 170 760 196" />
          <path className={`work-link ${phase === 4 || phase === 5 ? 'is-active' : ''}`} d="M520 95 L520 300 M760 196 Q720 335 600 364 M280 196 Q290 335 420 364" />
          <path className={`decision-link ${phase === 3 ? 'is-active' : ''}`} d="M910 308 Q900 445 625 402 M100 308 Q120 445 395 402" />
        </svg>
        <svg className="team-film-wires wires-small" viewBox="0 0 360 640" preserveAspectRatio="none" aria-hidden="true">
          <path className="owner-link" d="M50 77 L158 77 M144 499 L281 499" />
          <path className={`work-link ${phase === 2 ? 'is-active' : ''}`} d="M158 77 L295 77 M158 77 Q8 260 144 499" />
          <path className={`work-link ${phase === 4 || phase === 5 ? 'is-active' : ''}`} d="M295 77 Q340 230 230 295 M144 499 Q144 425 180 360 M158 77 L158 250" />
          <path className={`decision-link ${phase === 3 ? 'is-active' : ''}`} d="M281 499 Q340 440 230 350 M50 77 Q10 240 110 290" />
        </svg>
        {actors.map(actor => <div key={actor} className={`team-film-person person-${actor} ${activeActors[phase].includes(actor) ? 'is-active' : ''}`}>
          <span className="team-film-avatar" aria-hidden="true">{actor === 'qing' ? <ShieldCheck /> : actor === 'milo' || actor === 'noah' ? <span className="team-bot-face"><i /><i /><b /></span> : <span className="team-human-face"><i /><b /><em /></span>}{phase === 5 && <span className="team-avatar-check"><Check /></span>}</span>
          <strong>{text(`actors.${actor}.name`)}</strong><small>{text(`actors.${actor}.role`)}</small>
          <span className="team-actor-status">{text(`states.${phase}.${actor}`)}</span>
        </div>)}
        {(phase === 1 || phase === 2 || phase === 4) && <div className="team-film-packets" key={phase} aria-hidden="true">
          {phase === 1 && <span className="team-packet packet-request"><MessagesSquare />{text('packets.request')}</span>}
          {phase === 2 && <><span className="team-packet packet-check"><ShieldCheck />{text('packets.check')}</span><span className="team-packet packet-scope"><MessagesSquare />{text('packets.scope')}</span></>}
          {phase === 4 && <><span className="team-packet packet-result"><Check />{text('packets.result')}</span><span className="team-packet packet-plan"><FileText />{text('packets.plan')}</span></>}
        </div>}
        <div className={`team-film-object ${phase === 5 ? 'is-delivered' : ''}`}>
          <div className="team-object-sheet" aria-hidden="true" />
          <div className="team-object-content" key={phase}>
            {phase < 2 ? <>
              <div className="team-object-origin"><span className="team-mini-human">{text('you')}</span>{text('requestTo')}</div>
              <p className="team-film-request">{text('request')}</p>
              {phase === 0 ? <button className="team-film-action" onClick={advance}>{text('start')}<Send aria-hidden="true" /></button> : <div className="team-request-received"><Check aria-hidden="true" />{text('received')}</div>}
            </> : phase === 2 ? <>
              <div className="team-object-label"><MessagesSquare aria-hidden="true" />{text('parallel')}</div>
              <div className="team-preparations">{['brief', 'scope', 'check'].map((item, index) => <div key={item}><span className={`team-work-dot dot-${index}`} /><strong>{text(`work.${item}`)}</strong><span className="team-working-dots" aria-label={text('working')}><i /><i /><i /></span></div>)}</div>
            </> : phase === 3 ? <>
              <div className="team-object-origin"><span className="team-mini-human is-lan">{text('lanInitial')}</span>{text('suggestionFrom')}</div>
              <p className="team-film-request">{text('suggestion')}</p>
              <span className="team-decision-reason">{text('risk')}</span>
              <button className="team-film-action" onClick={advance}>{text('approve')}<ArrowRight aria-hidden="true" /></button>
            </> : <>
              <div className="team-delivery-heading"><span className="team-delivery-file"><FileText aria-hidden="true" /></span><div><small>{text('sharedResult')}</small><strong>{text('artifact')}</strong></div>{phase === 5 && <Check className="team-delivery-check" aria-hidden="true" />}</div>
              <div className="team-deliverables">{['steps', 'proof', 'brief'].map(item => <div key={item}><Check aria-hidden="true" /><span>{text(`deliverables.${item}`)}</span></div>)}</div>
              <div className="team-result-owners"><span>{text('you')}</span><span className="is-lan">{text('lanInitial')}</span><small>{text(phase === 5 ? 'together' : 'aligning')}</small></div>
            </>}
          </div>
        </div>
      </div>
      <div className="team-film-footer">
        <p className="team-film-caption" aria-live="polite">{text(`captions.${phase}`)}</p>
        <div className="team-film-controls">
          {phase !== 3 && phase !== 5 && (reduced ? phase > 0 && <button onClick={advance}>{text('continue')}<ArrowRight aria-hidden="true" /></button> : <button onClick={() => setPlaying(!playing)} aria-label={text(playing ? 'pause' : 'play')}>{playing ? <Pause /> : <Play />}</button>)}
          <button onClick={replay} aria-label={text('replay')}><RotateCcw aria-hidden="true" />{phase === 5 && <span>{text('replay')}</span>}</button>
        </div>
      </div>
    </div>
    <p className="team-film-note">{text('scope')}</p>
  </section>;
}
