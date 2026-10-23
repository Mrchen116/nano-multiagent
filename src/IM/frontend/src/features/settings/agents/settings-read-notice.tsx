import {useTranslation} from "../../../i18n";
import type {SettingsRead} from "./im-agent-config-api";

/** Label historical and missing observations without replacing the existing section UI. */
export function SettingsReadNotice({read}: {read?: SettingsRead<unknown>}) {
  const {t} = useTranslation();
  if (!read || read.source === "current") return null;
  return <p className="im-agent-field-help" role="status">
    {read.data === null ? t("agents.settings.unavailable") : t("agents.settings.lastKnown", {
      time: read.captured_at ? new Date(read.captured_at).toLocaleString() : "—",
    })}
    {read.error && !["agent_node_offline", "offline"].includes(read.error.code) && ` ${t("agents.settings.failed")}`}
  </p>;
}
