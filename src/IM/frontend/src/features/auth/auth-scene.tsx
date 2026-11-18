import { Check, FileText, GitBranch, Sparkles } from 'lucide-react';
import { useTranslation } from '../../i18n';

/** Continue the site's collaboration story as an illustration, never as account activity. */
export function AuthScene() {
  const { t } = useTranslation();
  const text = (key: string) => t(`auth.scene.${key}`);
  return <aside className="crew-account-story" aria-labelledby="account-story-title">
    <h2 id="account-story-title">{text('title')}</h2>
    <p className="crew-account-story-intro">{text('intro')}</p>
    <div className="crew-account-illustration" role="img" aria-label={text('description')}>
      <div aria-hidden="true">
        <div className="crew-account-note"><span className="crew-account-human">{text('you')}</span><p>{text('request')}</p></div>
        <div className="crew-account-connection"><span /><span /><span /></div>
        <div className="crew-account-crew">
          <div><span className="is-personal"><Sparkles /></span><small>{text('assistant')}</small></div>
          <div><span className="is-specialist"><GitBranch /></span><small>{text('colleague')}</small></div>
          <div><span className="is-quality"><Check /></span><small>{text('quality')}</small></div>
        </div>
        <div className="crew-account-result">
          <div><span><FileText /></span><strong>{text('document')}</strong><Check /></div>
          <p>{text('result')}</p>
          <span>{text('review')}</span>
        </div>
      </div>
    </div>
    <p className="crew-account-story-caption">{text('caption')}</p>
  </aside>;
}
