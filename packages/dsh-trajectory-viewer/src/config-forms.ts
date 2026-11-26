import * as Store from '@deepseek-ai/dsh-client-store';
import type { LocaleSettings } from '@deepseek-ai/dsh-client-locale';
import type { ConversationSettings } from '@deepseek-ai/dsh-client-ui-conversation';
import type { ThemePreference, ThemeSettings } from '@deepseek-ai/dsh-client-ui-theme';

const readonly = (): never => {
  throw new Error('Read-only trajectory viewer');
};

function normalizeThemePreference(value: string | undefined): ThemePreference {
  return value === 'dark' || value === 'system' ? value : 'light';
}

/**
 * Create a read-only `configForms` host projection satisfying DSH browser plugins.
 *
 * @param options - Optional viewer locale and theme preferences supplied by the parent frame.
 * @returns Read-only snapshot stores keyed by DSH settings namespace.
 */
export function createReadonlyConfigForms(options?: {
  language?: string;
  theme?: string;
}) {
  const localeValue: LocaleSettings = {
    preference: options?.language || 'zh',
  };
  const conversationValue: ConversationSettings = {
    busyEnter: 'queue',
  };
  const themeValue: ThemeSettings = {
    preference: normalizeThemePreference(options?.theme),
    fontSize: 14,
    codeFontSize: 11,
    terminalFontSize: 13,
    textFontFamily: '',
    codeFontFamily: '',
    terminalFontFamily: '',
  };

  return {
    get(namespace: string) {
      if (namespace === 'locale' || namespace.includes('locale')) {
        return Store.createSnapshotStore({ value: localeValue });
      }
      if (namespace === 'ui-conversation') {
        return Store.createSnapshotStore({ value: conversationValue });
      }
      return Store.createSnapshotStore({ value: themeValue });
    },
    set: readonly,
    patch: readonly,
    developerTools: { enabled: Store.createSnapshotStore(true) },
  };
}
