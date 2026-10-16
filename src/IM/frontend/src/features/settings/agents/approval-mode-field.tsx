import * as Label from "@radix-ui/react-label";
import { useTranslation } from "../../../i18n";

export type ApprovalMode = "cc" | "codex" | null;

/** Shared choice for creation and editing, applied at the next task boundary. */
export function ApprovalModeField({ value, onChange }: { value?: ApprovalMode; onChange: (value: ApprovalMode) => void }) {
  const { t } = useTranslation();
  return (
    <div className="im-agent-field">
      <Label.Root htmlFor="approval-mode">{t("agents.form.behavior.approvalMode")}</Label.Root>
      <select id="approval-mode" value={value ?? ""} onChange={(event) => onChange((event.target.value || null) as ApprovalMode)} aria-describedby="approval-mode-description approval-mode-timing" className="im-input">
        <option value="">{t("agents.form.behavior.approvalInherit")}</option>
        <option value="cc">CC</option>
        <option value="codex">Codex</option>
      </select>
      <p id="approval-mode-description" className="im-agent-field-help">{t(`agents.form.behavior.approvalDescription.${value ?? "inherit"}`)}</p>
      <p id="approval-mode-timing" className="im-agent-field-help">{t("agents.form.behavior.approvalTiming")}</p>
    </div>
  );
}
