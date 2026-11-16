import { useState } from 'react';
import { useTranslation } from '../../i18n';
import './product-demo.css';

const scenes = ['discuss', 'change', 'parallel', 'followup'] as const;
type Scene = typeof scenes[number];
const people = ['lin', 'linPa', 'zhou', 'zhouPa', 'engineering', 'quality'] as const;
type Person = typeof people[number];
const speakers: Record<Exclude<Scene, 'parallel'>, Person[]> = {
  discuss: ['lin', 'zhou', 'quality'],
  change: ['linPa', 'lin', 'linPa'],
  followup: ['engineering', 'quality', 'linPa'],
};

/** A local, explicitly illustrative story; scene changes never create product work. */
export function ProductDemo() {
  const { t } = useTranslation();
  const [index, setIndex] = useState(0);
  const scene = scenes[index];
  const [openDeliverable, setOpenDeliverable] = useState(false);
  function select(next: number) { setIndex(next); setOpenDeliverable(false); }
  const person = (id: Person, key: string) => t(`publicHome.demo.people.${id}.${key}`);
  const sceneText = (key: string) => t(`publicHome.demo.${scene}.${key}`);
  return <section className="product-demo home-container" id="product-demo" aria-labelledby="product-demo-title">
    <div className="product-demo-heading"><div><p className="home-eyebrow">{t('publicHome.demo.eyebrow')}</p><h2 id="product-demo-title">{t('publicHome.demo.title')}</h2></div><span className="product-demo-label">{t('publicHome.demo.label')}</span></div>
    <div className="product-demo-tabs" role="tablist" aria-label={t('publicHome.demo.navigation')}>
      {scenes.map((key, i) => <button type="button" key={key} id={`demo-tab-${key}`} role="tab" tabIndex={index === i ? 0 : -1} aria-selected={index === i} aria-controls="product-demo-panel" onClick={() => select(i)} onKeyDown={event => {
        const next = event.key === 'ArrowRight' ? (i + 1) % scenes.length : event.key === 'ArrowLeft' ? (i + scenes.length - 1) % scenes.length : event.key === 'Home' ? 0 : event.key === 'End' ? scenes.length - 1 : null;
        if (next === null) return;
        event.preventDefault(); select(next); document.getElementById(`demo-tab-${scenes[next]}`)?.focus();
      }}><span>0{i + 1}</span><span>{t(`publicHome.demo.${key}.tab`)}</span></button>)}
    </div>
    <div className="product-demo-window">
      <aside className="product-demo-roster" aria-label={t('publicHome.demo.roster')}>
        <div className="product-demo-team"><span aria-hidden="true">N</span><div><strong>{t('publicHome.demo.team')}</strong><small>{t('publicHome.demo.teamNote')}</small></div></div>
        <p className="product-demo-roster-label">{t('publicHome.demo.roster')}</p>
        {people.map(id => <div key={id} className={`product-demo-member${(scene === 'change' && id === 'linPa') || (scene === 'parallel' && id === 'quality') ? ' is-active' : ''}`}>
          <span className={`product-demo-avatar person-${id}`} aria-hidden="true">{person(id, 'avatar')}</span><div><strong>{person(id, 'name')}</strong><small>{person(id, 'role')}</small></div>
        </div>)}
        <p className="product-demo-roster-note">{t('publicHome.demo.rosterNote')}</p>
      </aside>
      <div className="product-demo-panel" id="product-demo-panel" role="tabpanel" tabIndex={0} aria-labelledby={`demo-tab-${scene}`}>
        <header className="product-demo-channel"><div><span className="product-demo-surface">{sceneText('surface')}</span><h3>{sceneText('channel')}</h3></div><span className="product-demo-time">{sceneText('time')}</span></header>
        <div className="product-demo-scene">
          <div className="product-demo-thread">
            <p className="product-demo-scene-intro">{sceneText('intro')}</p>
            {scene === 'parallel' ? <div className="product-demo-work-list">
              {['waiting', 'running', 'recorded'].map(key => <article className={`product-demo-work-item work-${key}`} key={key}>
                <div className="product-demo-work-heading"><span>{sceneText(`tasks.${key}.status`)}</span><small>{sceneText(`tasks.${key}.source`)}</small></div>
                <h4>{sceneText(`tasks.${key}.title`)}</h4><p>{sceneText(`tasks.${key}.body`)}</p>
              </article>)}
            </div> : <>
              {scene === 'change' && <blockquote className="product-demo-source"><span>{sceneText('sourceLabel')}</span><p>{sceneText('source')}</p></blockquote>}
              <div className="product-demo-messages">{speakers[scene].map((id, i) => <article className="product-demo-message" key={`${scene}-${i}`}>
                <span className={`product-demo-avatar person-${id}`} aria-hidden="true">{person(id, 'avatar')}</span><div><header><strong>{person(id, 'name')}</strong><span>{person(id, 'kind')}</span></header><p>{sceneText(`messages.${i}`)}</p></div>
              </article>)}</div>
              {scene === 'followup' && <div className="product-demo-delivery">
                <button type="button" aria-expanded={openDeliverable} aria-controls="demo-deliverable" onClick={() => setOpenDeliverable(!openDeliverable)}><span aria-hidden="true">▤</span><span><strong>{sceneText('document')}</strong><small>{sceneText('documentHint')}</small></span><span aria-hidden="true">{openDeliverable ? '−' : '+'}</span></button>
                <div id="demo-deliverable" hidden={!openDeliverable}><p>{sceneText('documentBody')}</p></div>
              </div>}
            </>}
          </div>
          <aside className="product-demo-context" aria-label={sceneText('asideTitle')}><span className="product-demo-context-label">{sceneText('asideLabel')}</span><h4>{sceneText('asideTitle')}</h4>
            {['first', 'second', 'third'].map(key => <div key={key}><strong>{sceneText(`notes.${key}.title`)}</strong><p>{sceneText(`notes.${key}.body`)}</p></div>)}
          </aside>
        </div>
      </div>
    </div>
    <div className="product-demo-bottom"><p><span>0{index + 1} / 04</span>{sceneText('takeaway')}</p><button type="button" onClick={() => select((index + 1) % scenes.length)}>{t(index === scenes.length - 1 ? 'publicHome.demo.restart' : 'publicHome.demo.next')} <span aria-hidden="true">→</span></button></div>
    <p className="product-demo-disclosure">{t('publicHome.demo.disclosure')}</p>
  </section>;
}
