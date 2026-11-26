import { AssistantIllustration } from "../chat/components/avatar";
import "../chat/components/assistant-starters.css";
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../i18n';
import { useAuthStore } from '../auth/auth-store';
import { getOnboarding, setupNode } from './onboarding-api';
import '../home/product-entry.css';
import './first-use-welcome.css';

/** Give an empty personal workspace a useful next step without blocking other chats. */
export function FirstUseWelcome({ onNewChat }: { onNewChat(): void }) {
  const { t } = useTranslation();
  const user = useAuthStore(s => s.user)!;
  const progress = useQuery({ queryKey: ['onboarding', user.id], queryFn: getOnboarding });
  let preferredNode: string | undefined;
  try { preferredNode = JSON.parse(localStorage.getItem(`nano-onboarding:${user.id}`) ?? '{}').nodeId; } catch { /* No saved setup yet. */ }
  const node = progress.data?.nodes.find(n => n.node_id === preferredNode)
    ?? progress.data?.nodes.find(n => n.status === 'online') ?? progress.data?.nodes[0];
  const online = node?.status === 'online';
  const model = useQuery({
    queryKey: ['node-setup', user.id, node?.node_id],
    queryFn: () => setupNode(node!.node_id, { action: 'status' }),
    enabled: online,
    retry: false,
  });
  const configured = online && !!model.data?.default_model && model.data.models.some(m => m.model === model.data?.default_model);
  const checking = progress.isPending || (online && model.isPending);
  const failed = progress.isError || (online && model.isError);
  const step = online ? configured ? 2 : 1 : 0;
  const labels = ['computer', 'model', 'assistant'] as const;

  return <section className="first-use product-entry" aria-labelledby="first-use-title">
    <div className="first-use-inner">
      <header className="first-use-heading">
        <AssistantIllustration size={72} />
        <span className="first-use-eyebrow">{t('firstUse.eyebrow')}</span>
        <h1 id="first-use-title">{t('firstUse.title')}</h1>
        <p>{t('firstUse.intro')}</p>
      </header>
      <div className="first-use-layout">
        <section className="first-use-setup" aria-labelledby="first-use-setup-title">
          <div className="first-use-setup-heading">
            <span className="first-use-symbol" aria-hidden="true"><WelcomeIcon name="spark" /></span>
            <div><h2 id="first-use-setup-title">{t('firstUse.setupTitle')}</h2><p><span aria-hidden="true">✓</span> {t('firstUse.accountReady')}</p></div>
          </div>
          <ol className="first-use-steps">
            {labels.map((label, i) => <li key={label} className={!checking && !failed && i < step ? 'complete' : i === step ? 'current' : ''}>
              <span className="first-use-step-number" aria-hidden="true">{!checking && !failed && i < step ? '✓' : `0${i + 1}`}</span>
              <div><h3>{t(`firstUse.steps.${label}.title`)}</h3><p>{i === 0 && online ? node.alias || node.node_name : t(`firstUse.steps.${label}.body`)}</p></div>
              {!checking && !failed && i < step && <span className="first-use-step-done">{t('firstUse.done')}</span>}
            </li>)}
          </ol>
          {failed && <p className="first-use-feedback" role="alert">{t('firstUse.progressError')} <button onClick={() => { void progress.refetch(); if (online) void model.refetch(); }}>{t('common.retry')}</button></p>}
          <Link className="first-use-primary" to="/onboarding">{t(checking || failed ? 'firstUse.continue' : `firstUse.actions.${labels[step]}`)}<span aria-hidden="true">→</span></Link>
          <p className="first-use-resume">{t('firstUse.resume')}</p>
        </section>
        <section className="first-use-ideas" aria-labelledby="first-use-ideas-title">
          <span className="first-use-section-label">{t('firstUse.examplesLabel')}</span>
          <h2 id="first-use-ideas-title">{t('firstUse.examplesTitle')}</h2>
          <p className="first-use-ideas-intro">{t('firstUse.examplesIntro')}</p>
          {(['plan', 'organize', 'start'] as const).map((idea) => <article className="first-use-example" key={idea}>
            <span className="first-use-example-icon" aria-hidden="true"><WelcomeIcon name={idea} /></span>
            <div><h3>{t(`firstUse.examples.${idea}.title`)}</h3><p>{t(`firstUse.examples.${idea}.prompt`)}</p></div>
          </article>)}
          <p className="first-use-example-note">{t('firstUse.examplesNote')}</p>
        </section>
      </div>
      <footer className="first-use-footer"><span>{t('firstUse.peopleHint')}</span><button onClick={onNewChat}>{t('firstUse.newChat')} <span aria-hidden="true">↗</span></button></footer>
    </div>
  </section>;
}

function WelcomeIcon({ name }: { name: 'spark' | 'plan' | 'organize' | 'start' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    {name === 'spark' ? <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" /></>
      : name === 'plan' ? <><rect x="4" y="5" width="16" height="16" rx="3" /><path d="M8 3v4m8-4v4M4 11h16m-12 4h3m-3 3h6" /></>
      : name === 'organize' ? <><path d="m4 6 1 1 2-2m3 1h10M4 12l1 1 2-2m3 1h10M4 18l1 1 2-2m3 1h10" /></>
      : <><path d="M5 19V8a3 3 0 0 1 3-3h11m-5-3 5 3-5 3M5 19h14m-4-5 4 5-4 3" /></>}
  </svg>;
}
