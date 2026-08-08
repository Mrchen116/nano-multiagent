import * as Label from "@radix-ui/react-label";

import type { TFunction } from "i18next";
import type { ReactNode } from "react";

import { useTranslation } from "../../../i18n";
import type { ModelOption, ModelReasoningDescriptor } from "./im-agent-config-api";

const KNOWN_REASONING_LEVELS = new Set(["none", "low", "medium", "high", "xhigh", "max"]);

export function reasoningLevelLabel(level: string, t: TFunction): string {
  return KNOWN_REASONING_LEVELS.has(level)
    ? t(`agents.form.access.reasoning.levels.${level}`)
    : level;
}

function descriptorForModel(
  modelOptions: ModelOption[],
  modelName: string | null,
): ModelReasoningDescriptor | undefined {
  if (!modelName) return undefined;
  return modelOptions.find((option) => option.name === modelName)?.reasoning;
}

export function effectiveReasoningModel(
  selectedModel: string | null,
  platformDefaultModel: string | null,
): string | null {
  return selectedModel ?? platformDefaultModel;
}

export function reasoningEffortAfterModelChange(
  modelOptions: ModelOption[],
  modelName: string | null,
  currentEffort: string | null,
): string | null {
  const descriptor = descriptorForModel(modelOptions, modelName);
  if (descriptor?.kind !== "selectable") return null;
  return currentEffort && descriptor.levels.includes(currentEffort)
    ? currentEffort
    : descriptor.default;
}

export function normalizeReasoningEffort(
  modelOptions: ModelOption[],
  modelName: string | null,
  currentEffort: string | null,
): string | null {
  const descriptor = descriptorForModel(modelOptions, modelName);
  return descriptor?.kind === "selectable" ? (currentEffort ?? descriptor.default) : currentEffort;
}

export function isStaleReasoningEffort(
  modelOptions: ModelOption[],
  modelName: string | null,
  currentEffort: string | null,
): boolean {
  if (!currentEffort) return false;
  const descriptor = descriptorForModel(modelOptions, modelName);
  return descriptor?.kind !== "selectable" || !descriptor.levels.includes(currentEffort);
}

interface ModelReasoningFieldProps {
  idPrefix: string;
  modelOptions: ModelOption[];
  selectedModel: string | null;
  value: string | null;
  disabled?: boolean;
  applyPending?: boolean;
  onChange: (value: string | null) => void;
}

export function ModelReasoningField({
  idPrefix,
  modelOptions,
  selectedModel,
  value,
  disabled = false,
  applyPending = false,
  onChange,
}: ModelReasoningFieldProps) {
  const { t } = useTranslation();
  const descriptor = descriptorForModel(modelOptions, selectedModel);
  const selectId = `${idPrefix}-reasoning-effort`;
  const stale = isStaleReasoningEffort(modelOptions, selectedModel, value);

  let field: ReactNode;
  if (!selectedModel) {
    field = (
      <>
        <span className="im-agent-reasoning-label">{t("agents.form.access.reasoning.label")}</span>
        <div className="im-agent-reasoning-readonly">
          {t("agents.form.access.reasoning.selectModelFirst")}
        </div>
        <p className="im-agent-field-help">{t("agents.form.access.reasoning.platformDefaultHelp")}</p>
      </>
    );
  } else if (descriptor?.kind === "fixed") {
    field = (
      <>
        <span className="im-agent-reasoning-label">{t("agents.form.access.reasoning.shortLabel")}</span>
        <div className="im-agent-reasoning-readonly">
          <strong>{t("agents.form.access.reasoning.fixedState")}</strong>
        </div>
        <p className="im-agent-field-help">{t("agents.form.access.reasoning.fixedHelp")}</p>
      </>
    );
  } else if (!descriptor) {
    field = (
      <>
        <span className="im-agent-reasoning-label">{t("agents.form.access.reasoning.label")}</span>
        <div className="im-agent-reasoning-readonly">
          {t("agents.form.access.reasoning.unavailableState")}
        </div>
        <p className="im-agent-field-help">{t("agents.form.access.reasoning.unavailableHelp")}</p>
      </>
    );
  } else {
    const selectedValue = value ?? descriptor.default;
    const levels = stale && value ? [value, ...descriptor.levels] : descriptor.levels;
    field = (
      <>
        <Label.Root htmlFor={selectId}>{t("agents.form.access.reasoning.label")}</Label.Root>
        <select
          id={selectId}
          className="im-input"
          value={selectedValue}
          disabled={disabled}
          aria-invalid={stale}
          aria-describedby={`${selectId}-help${stale ? ` ${selectId}-error` : ""}`}
          onChange={(event) => onChange(event.target.value)}
        >
          {levels.map((level) => (
            <option key={level} value={level}>
              {reasoningLevelLabel(level, t)}
            </option>
          ))}
        </select>
        <p id={`${selectId}-help`} className="im-agent-field-help">
          {t("agents.form.access.reasoning.selectableHelp", {
            level: reasoningLevelLabel(descriptor.default, t),
          })}
        </p>
        {stale ? (
          <p id={`${selectId}-error`} className="im-agent-reasoning-error" role="alert">
            {t("agents.form.access.reasoning.staleError")}
          </p>
        ) : null}
      </>
    );
  }

  return (
    <div className="im-agent-field im-agent-reasoning-field" data-testid={`${idPrefix}-reasoning-field`}>
      {field}
      {stale && descriptor?.kind !== "selectable" ? (
        <>
          <p className="im-agent-reasoning-error" role="alert">
            {t("agents.form.access.reasoning.staleUnavailableError")}
          </p>
          <button
            className="im-btn im-btn-muted w-fit"
            type="button"
            disabled={disabled}
            onClick={() => onChange(null)}
          >
            {t("agents.form.access.reasoning.clearUnavailable")}
          </button>
        </>
      ) : null}
      {applyPending ? (
        <p className="im-agent-reasoning-pending" role="status">
          {t("agents.form.access.reasoning.applyPending")}
        </p>
      ) : null}
    </div>
  );
}
