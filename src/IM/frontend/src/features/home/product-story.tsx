import { Link } from 'react-router-dom';
import { ChevronDown, Laptop } from 'lucide-react';
import { useTranslation } from '../../i18n';
import { CompanionScene } from './companion-scene';
import './product-story.css';

/** Keep the public story centered on visible ongoing work and a clear way to start. */
export function ProductStorySections() {
  const { t } = useTranslation();
  const text = (key: string) => t(`crewdenStory.${key}`);
  return <>
    <CompanionScene />
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
