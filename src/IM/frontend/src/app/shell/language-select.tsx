import { ChevronDown, Globe2 } from 'lucide-react';
import { getCurrentLanguage, setLanguage, useTranslation } from '../../i18n';

/** Use full language names and the platform's keyboard and touch selection. */
export function LanguageSelect() {
  const { t } = useTranslation();
  return <label className="im-language-select">
    <Globe2 aria-hidden="true" />
    <select aria-label={t('auth.language.label')} value={getCurrentLanguage()} onChange={event => setLanguage(event.target.value === 'zh' ? 'zh' : 'en')}>
      <option value="en">English</option><option value="zh">简体中文</option>
    </select>
    <ChevronDown className="im-language-chevron" aria-hidden="true" />
  </label>;
}
