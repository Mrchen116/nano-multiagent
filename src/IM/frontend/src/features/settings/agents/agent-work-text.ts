import { i18n } from "../../../i18n";

/** Translate work-view labels; model-authored text remains verbatim. */
export const tr = (label: string) => i18n.t(`agents.work.${label}`, { defaultValue: label });
