import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { NanoBrand } from '../../app/shell/nano-brand';
import { useTranslation } from '../../i18n';
import { ProductHeader } from './product-header';
import { accountEnabled, useAuthStore } from '../auth/auth-store';
import './public-home.css';

/** Explain the product before asking visitors to create an account. */
export function PublicHomePage({ restoreSession = false }: { restoreSession?: boolean }) {
  const { t } = useTranslation();
  const [scene, setScene] = useState(0);
  const scenes = ['ask', 'work', 'result'] as const;
  const current = scenes[scene];
  const [openQuestion, setOpenQuestion] = useState<number | null>(0);
  const user = useAuthStore(s => s.user);
  const hydrated = useAuthStore(s => s.hydrated);
  useEffect(() => { if (restoreSession && !hydrated) void useAuthStore.getState().hydrate(); }, [restoreSession, hydrated]);
  if (restoreSession && hydrated && user) return <Navigate to={accountEnabled(user) ? '/chat' : '/membership'} replace />;

  return <div className="public-home product-entry">
    <a className="home-skip" href="#home-main">{t('publicHome.skip')}</a>
    <ProductHeader />

    <main id="home-main">
      <section className="home-hero home-container" aria-labelledby="home-title">
        <div className="home-hero-copy">
          <p className="home-eyebrow"><span />{t('publicHome.eyebrow')}</p>
          <h1 id="home-title">{t('publicHome.titleBefore')}<em>{t('publicHome.titleAccent')}</em>{t('publicHome.titleAfter')}</h1>
          <p className="home-lead">{t('publicHome.intro')}</p>
          <div className="home-hero-actions"><Link className="home-button" to="/register">{t('publicHome.createSpace')}<Arrow /></Link><a className="home-text-link" href="#product-demo">{t('publicHome.watch')}<span aria-hidden="true">↘</span></a></div>
          <p className="home-prerequisite">{t('publicHome.prerequisite')}</p>
        </div>

        <section className="home-demo" id="product-demo" aria-labelledby="home-demo-title">
          <div className="home-demo-top"><div><span className="home-demo-mark" aria-hidden="true">✦</span><strong id="home-demo-title">{t('publicHome.demo.title')}</strong></div><span className="home-demo-label">{t('publicHome.demo.label')}</span></div>
          <div className="home-demo-tabs" role="tablist" aria-label={t('publicHome.demo.navigation')}>
            {scenes.map((key, i) => <button key={key} id={`demo-tab-${key}`} role="tab" tabIndex={scene === i ? 0 : -1} aria-selected={scene === i} aria-controls="home-demo-panel" onClick={() => setScene(i)} onKeyDown={event => {
              const next = event.key === 'ArrowRight' ? (i + 1) % scenes.length : event.key === 'ArrowLeft' ? (i + scenes.length - 1) % scenes.length : event.key === 'Home' ? 0 : event.key === 'End' ? scenes.length - 1 : null;
              if (next === null) return;
              event.preventDefault(); setScene(next); document.getElementById(`demo-tab-${scenes[next]}`)?.focus();
            }}><span>0{i + 1}</span>{t(`publicHome.demo.steps.${key}`)}</button>)}
          </div>
          <div className="home-demo-content" role="tabpanel" id="home-demo-panel" aria-labelledby={`demo-tab-${current}`}>
            <div className="home-demo-person"><span>{t('publicHome.demo.you')}</span><p>{t('publicHome.demo.request')}</p></div>
            <div className="home-demo-assistant"><span className="home-demo-avatar" aria-hidden="true">✦</span><div><strong>{t('publicHome.demo.assistant')}</strong><p>{t(`publicHome.demo.${current}.reply`)}</p></div></div>
            {scene === 0 ? <div className="home-demo-plan"><span>{t('publicHome.demo.ask.planLabel')}</span>{['first', 'second', 'third'].map((key, i) => <p key={key}><b>0{i + 1}</b>{t(`publicHome.demo.ask.${key}`)}</p>)}</div>
              : scene === 1 ? <div className="home-demo-work">{['research', 'writing', 'review'].map(key => <div key={key}><span className="home-demo-worker-icon" aria-hidden="true"><HomeIcon name={key === 'research' ? 'search' : key === 'writing' ? 'document' : 'check'} /></span><div><strong>{t(`publicHome.demo.work.${key}.name`)}</strong><small>{t(`publicHome.demo.work.${key}.task`)}</small></div><span className="home-demo-worker-state">{t(`publicHome.demo.work.${key}.state`)}</span></div>)}</div>
                : <div className="home-demo-result"><span className="home-demo-result-icon" aria-hidden="true"><HomeIcon name="document" /></span><div><strong>{t('publicHome.demo.result.document')}</strong><p>{t('publicHome.demo.result.description')}</p></div><span aria-hidden="true">↗</span></div>}
          </div>
          <div className="home-demo-bottom"><span>{t(`publicHome.demo.${current}.caption`)}</span><button onClick={() => setScene((scene + 1) % scenes.length)} aria-label={t(scene === 2 ? 'publicHome.demo.restart' : 'publicHome.demo.next')}><Arrow /></button></div>
          <p className="home-demo-disclosure">{t('publicHome.demo.disclosure')}</p>
        </section>
      </section>

      <section className="home-concepts home-container" id="how-it-works" aria-labelledby="home-concepts-title">
        <div className="home-section-heading"><p className="home-eyebrow">{t('publicHome.concepts.eyebrow')}</p><h2 id="home-concepts-title">{t('publicHome.concepts.title')}</h2><p>{t('publicHome.concepts.intro')}</p></div>
        <div className="home-concept-grid">{(['personal', 'specialist', 'computer'] as const).map((key, index) => <article key={key} className="home-concept">
          <div className="home-concept-top"><span className="home-concept-icon"><HomeIcon name={key === 'personal' ? 'person' : key === 'specialist' ? 'team' : 'computer'} /></span><span>0{index + 1}</span></div>
          <span className="home-concept-role">{t(`publicHome.concepts.${key}.role`)}</span><h3>{t(`publicHome.concepts.${key}.title`)}</h3><p>{t(`publicHome.concepts.${key}.body`)}</p><div className="home-concept-example">{t(`publicHome.concepts.${key}.example`)}</div>
        </article>)}</div>
      </section>

      <section className="home-space-section" id="your-space" aria-labelledby="home-space-title"><div className="home-container home-space-layout">
        <div className="home-section-heading"><p className="home-eyebrow">{t('publicHome.space.eyebrow')}</p><h2 id="home-space-title">{t('publicHome.space.title')}</h2><p>{t('publicHome.space.intro')}</p><a className="home-text-link" href="#getting-started">{t('publicHome.space.link')}<Arrow /></a></div>
        <div className="home-space-details">{(['context', 'progress', 'control'] as const).map(key => <article key={key}><span className="home-space-icon"><HomeIcon name={key === 'context' ? 'message' : key === 'progress' ? 'check' : 'shield'} /></span><div><h3>{t(`publicHome.space.${key}.title`)}</h3><p>{t(`publicHome.space.${key}.body`)}</p></div></article>)}</div>
      </div></section>

      <section className="home-start home-container" id="getting-started" aria-labelledby="home-start-title">
        <div className="home-section-heading"><p className="home-eyebrow">{t('publicHome.setup.eyebrow')}</p><h2 id="home-start-title">{t('publicHome.setup.title')}</h2><p>{t('publicHome.setup.intro')}</p></div>
        <ol className="home-start-steps">{['account', 'computer', 'model'].map((key, i) => <li key={key}><span>0{i + 1}</span><h3>{t(`publicHome.setup.${key}.title`)}</h3><p>{t(`publicHome.setup.${key}.body`)}</p></li>)}</ol>
        <div className="home-start-action"><Link className="home-button" to="/register">{t('publicHome.createSpace')}<Arrow /></Link><p>{t('publicHome.setup.note')}</p></div>
      </section>

      <section className="home-faq home-container" aria-labelledby="home-faq-title">
        <div className="home-section-heading"><p className="home-eyebrow">{t('publicHome.faq.eyebrow')}</p><h2 id="home-faq-title">{t('publicHome.faq.title')}</h2></div>
        <div className="home-faq-list">{['ready', 'phone', 'online', 'data', 'team', 'model'].map((key, index) => <div className="home-faq-item" key={key}><h3><button aria-expanded={openQuestion === index} aria-controls={`home-answer-${key}`} onClick={() => setOpenQuestion(openQuestion === index ? null : index)}>{t(`publicHome.faq.${key}.question`)}<span aria-hidden="true">{openQuestion === index ? '−' : '+'}</span></button></h3><p id={`home-answer-${key}`} hidden={openQuestion !== index}>{t(`publicHome.faq.${key}.answer`)}</p></div>)}</div>
      </section>
    </main>
    <footer className="home-footer home-container"><NanoBrand /><span>{t('publicHome.footer')}</span><Link to="/login">{t('publicHome.signIn')}<span aria-hidden="true"> ↗</span></Link></footer>
  </div>;
}

function Arrow() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>; }

function HomeIcon({ name }: { name: 'person' | 'team' | 'computer' | 'message' | 'check' | 'shield' | 'document' | 'search' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'person' ? <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2" /></>
      : name === 'team' ? <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v2m1-15a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 5v1" /></>
      : name === 'computer' ? <><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8m-4-4v4" /></>
      : name === 'message' ? <path d="M21 14a3 3 0 0 1-3 3H9l-6 4V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v8ZM7 8h10M7 12h6" />
      : name === 'check' ? <><rect x="4" y="4" width="16" height="16" rx="4" /><path d="m8 12 3 3 5-6" /></>
      : name === 'shield' ? <><path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>
      : name === 'search' ? <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></>
      : <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8m-8 4h5" /></>}
  </svg>;
}
