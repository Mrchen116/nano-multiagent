import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import * as Dialog from '@radix-ui/react-dialog';
import { ArrowRight, Check, Clock3, FileText, GitBranch, Sparkles, X } from 'lucide-react';
import { NanoBrand } from '../../app/shell/nano-brand';
import { useTranslation } from '../../i18n';
import { ProductHeader } from './product-header';
import { ProductStorySections } from './product-story';
import { HeroDownloadActions, PublicDownloadSection, usePublicInstallMaterials } from './public-download-section';
import { accountEnabled, useAuthStore } from '../auth/auth-store';
import './public-home.css';

const stages = ['change', 'progress', 'ready'] as const;
const roles = ['personal', 'engineering', 'quality'] as const;

/** Present the public product story while preserving returning users' entry route. */
export function PublicHomePage({ restoreSession = false }: { restoreSession?: boolean }) {
  const { t } = useTranslation();
  const location = useLocation();
  const text = (key: string) => t(`crewdenHome.${key}`);
  const [stage, setStage] = useState(2);
  const user = useAuthStore(s => s.user);
  const hydrated = useAuthStore(s => s.hydrated);
  const { materials } = usePublicInstallMaterials();
  const scene = (key: string) => text(`scenes.${stages[stage]}.${key}`);
  useEffect(() => { if (restoreSession && !hydrated) void useAuthStore.getState().hydrate(); }, [restoreSession, hydrated]);
  useEffect(() => {
    if (!location.hash) return;
    const targetId = location.hash.slice(1);
    if (!targetId) return;
    const el = document.getElementById(targetId);
    if (el && typeof el.scrollIntoView === 'function') {
      const reduced = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      el.scrollIntoView({ behavior: reduced ? 'instant' : 'smooth', block: 'start' });
    }
  }, [location.hash]);
  if (restoreSession && hydrated && user) return <Navigate to={accountEnabled(user) ? '/chat' : '/membership'} replace />;

  function watch() {
    document.getElementById('teamwork')?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start',
    });
  }

  return <div className="public-home product-entry">
    <a className="crew-skip" href="#home-main">{t('publicHome.skip')}</a>
    <ProductHeader />
    <main id="home-main">
      <section className="crew-hero" aria-labelledby="home-title">
        <div className="crew-intro">
          <h1 id="home-title">{text('titleFirst')}<br />{text('titleSecond')}</h1>
          <p className="crew-product-definition">{text('definition')}</p>
          <p className="crew-lead">{text('intro')}</p>
          <HeroDownloadActions materials={materials} onWatch={watch} />
          <div className="crew-controls" id="product-demo">
            <p>{text('scenario')}</p>
            <div className="crew-steps" role="group" aria-label={text('navigation')}>
              {stages.map((key, i) => <button key={key} aria-pressed={stage === i} aria-controls="crew-stage" onClick={() => setStage(i)}><span />{text(`steps.${key}`)}</button>)}
            </div>
            <button className="crew-next" onClick={() => setStage((stage + 1) % stages.length)}>{text(stage === 2 ? 'restart' : 'next')}<ArrowRight /></button>
          </div>
          <div className="crew-actors">
            <span><Avatar kind="human" />{text('actors.human')}</span><i>+</i>
            <span><Avatar kind="personal" />{text('actors.personal')}</span><i>+</i>
            <span><Avatar kind="engineering" />{text('actors.specialist')}</span>
          </div>
        </div>
        <div className="crew-stage" id="crew-stage" role="region" aria-label={text('stageLabel')}>
          <div className="crew-stage-caption"><span>{text('stageLabel')}</span><span>{text('example')}</span></div>
          <div className="crew-message">
            <div className="crew-person"><Avatar kind="human" /><strong>{text('person')}</strong><time>09:41</time></div>
            <p>{text('message')}</p>
          </div>
          <div className="crew-work" aria-label={text('workLabel')}>
            {roles.map(key => <div key={key}><Avatar kind={key} /><div><strong>{text(`roles.${key}`)}</strong><span>{scene(`work.${key}`)}</span></div></div>)}
          </div>
          <div className="crew-paper-wrap">
            <div className="crew-paper-back" aria-hidden="true" />
            <article className="crew-paper">
              <div className="crew-paper-top"><span><FileText />{text('document')}</span><span>{scene('version')}</span></div>
              <div className="crew-paper-body">
                <div className="crew-paper-heading"><span>{text('project')}</span><span className="crew-status" role="status">{scene('state')}</span></div>
                <h2>{text('documentTitleFirst')}<br />{text('documentTitleSecond')}</h2>
                <div className="crew-date"><span>{text('newDate')}</span><div><del>{text('wednesday')}</del><ArrowRight /><strong>{text('friday')}</strong><span>{text('updated')}</span></div></div>
                <div className="crew-week" aria-label={text('dateChange')}>
                  {['mon', 'tue', 'wed', 'thu', 'fri'].map((day, i) => <span key={day} className={i === 2 ? 'was-planned' : i === 4 ? 'is-launch' : ''}>{text(`week.${day}`)}<small>{i === 2 ? text('original') : i === 4 ? text('launch') : '\u00a0'}</small></span>)}
                </div>
                {['customer', 'verification'].map((key, i) => <div className="crew-deliverable" key={key}>
                  {i === 0 ? <FileText /> : <Check />}<div><strong>{text(`deliverables.${key}`)}</strong><small>{text(`deliverables.${key}Note`)}</small></div><span>{scene(key)}</span>
                </div>)}
                <p className="crew-document-note">{stage === 2 ? <Check /> : <Clock3 />}<span>{scene('note')}</span></p>
              </div>
              <Dialog.Root>
                <Dialog.Trigger className="crew-open-document">{text('openDocument')}<ArrowRight /></Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="crew-dialog-overlay" />
                  <Dialog.Content className="crew-dialog">
                    <span className="crew-dialog-kicker">{text('example')} / {scene('version')}</span>
                    <Dialog.Title>{text('dialogTitle')}</Dialog.Title>
                    <Dialog.Description>{scene('detail')}</Dialog.Description>
                    <div className="crew-dialog-date">{text('newDate')}<strong>{text('friday')}</strong></div>
                    <h3>{text('deliverableList')}</h3>
                    <ul><li>{text('deliverables.customer')}: {scene('customer')}</li><li>{text('deliverables.verification')}: {scene('verification')}</li><li>{text('releaseDecision')}</li></ul>
                    <p className="crew-disclosure">{text('disclosure')}</p>
                    <Dialog.Close className="crew-dialog-close" aria-label={text('close')}><X /></Dialog.Close>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
            </article>
            {stage === 2 && <div className="crew-receipt"><Avatar kind="personal" /><div><strong>{text('receiptTitle')}</strong><small>{text('receiptNote')}</small></div><Check /></div>}
          </div>
        </div>
      </section>
      <PublicDownloadSection materials={materials} />
      <ProductStorySections />
    </main>
    <footer className="crew-footer"><Link to="/about" aria-label={t('publicHome.home')}><NanoBrand /></Link><span>{text('footer')}</span><a href="#download">{t('crewdenStory.nav.download')}</a><a href="#questions">{t('crewdenStory.nav.faq')}</a><Link to="/login">{t('publicHome.signIn')}</Link></footer>
  </div>;
}

function Avatar({ kind }: { kind: 'human' | typeof roles[number] }) {
  const { t } = useTranslation();
  return <span className={`crew-avatar crew-avatar--${kind}`} aria-hidden="true">{kind === 'human' ? t('crewdenHome.initial') : kind === 'engineering' ? <GitBranch /> : kind === 'quality' ? <Check /> : <Sparkles />}</span>;
}
