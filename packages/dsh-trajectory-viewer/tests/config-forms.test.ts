import { Config as LocaleConfig, LOCALE_SETTINGS_NAMESPACE } from '@deepseek-ai/dsh-client-locale';
import {
  Config as ConversationConfig,
  CONVERSATION_SETTINGS_NAMESPACE,
} from '@deepseek-ai/dsh-client-ui-conversation';
import { Config as ThemeConfig, THEME_SETTINGS_NAMESPACE } from '@deepseek-ai/dsh-client-ui-theme';
import { describe, expect, it } from 'vitest';
import { createReadonlyConfigForms } from '../src/config-forms.js';

function unwrapVolatile(record: Record<string, { get(): unknown }>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(record).map(([key, value]) => [key, value.get()]));
}

describe('read-only viewer configForms projection', () => {
  it('provides complete settings sections matching upstream locale, conversation, and theme schemas', () => {
    const forms = createReadonlyConfigForms({ language: 'zh', theme: 'light' });

    const locale = forms.get(LOCALE_SETTINGS_NAMESPACE).getSnapshot().value;
    const conversation = forms.get(CONVERSATION_SETTINGS_NAMESPACE).getSnapshot().value;
    const theme = forms.get(THEME_SETTINGS_NAMESPACE).getSnapshot().value;

    expect(unwrapVolatile(new LocaleConfig(locale) as unknown as Record<string, { get(): unknown }>)).toEqual(locale);
    expect(unwrapVolatile(new ConversationConfig(conversation) as unknown as Record<string, { get(): unknown }>)).toEqual(conversation);
    expect(unwrapVolatile(new ThemeConfig(theme) as unknown as Record<string, { get(): unknown }>)).toEqual(theme);
    expect(Object.keys(locale).sort()).toEqual(Object.keys(LocaleConfig.dict).sort());
    expect(Object.keys(conversation).sort()).toEqual(Object.keys(ConversationConfig.dict).sort());
    expect(Object.keys(theme).sort()).toEqual(Object.keys(ThemeConfig.dict).sort());
    expect(forms.developerTools.enabled.getSnapshot()).toBe(true);
    expect(() => forms.set()).toThrow(/read-only/i);
    expect(() => forms.patch()).toThrow(/read-only/i);
  });
});
