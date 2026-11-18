import * as Select from '@radix-ui/react-select';
import { Check, ChevronDown, Globe2 } from 'lucide-react';
import { getCurrentLanguage, setLanguage, useTranslation } from '../../i18n';

/** Keep language selection compact while preserving keyboard and touch access. */
export function LanguageSelect() {
  const { t } = useTranslation();
  return <Select.Root value={getCurrentLanguage()} onValueChange={value => setLanguage(value === 'zh' ? 'zh' : 'en')}>
    <Select.Trigger className="im-language-select" aria-label={t('auth.language.label')}>
      <Globe2 aria-hidden="true" />
      <Select.Value />
      <Select.Icon className="im-language-chevron"><ChevronDown aria-hidden="true" /></Select.Icon>
    </Select.Trigger>
    <Select.Portal>
      <Select.Content className="im-language-menu" position="popper" align="end" sideOffset={6} collisionPadding={12}>
        <Select.Viewport>
          {[['en', 'English'], ['zh', '简体中文']].map(([value, label]) => <Select.Item className="im-language-option" key={value} value={value}>
            <Select.ItemText>{label}</Select.ItemText>
            <Select.ItemIndicator><Check aria-hidden="true" /></Select.ItemIndicator>
          </Select.Item>)}
        </Select.Viewport>
      </Select.Content>
    </Select.Portal>
  </Select.Root>;
}
