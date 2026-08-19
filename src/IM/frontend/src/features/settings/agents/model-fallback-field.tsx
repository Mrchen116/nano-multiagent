import * as Label from "@radix-ui/react-label";
import { useState, type ReactNode } from "react";

import { useTranslation } from "../../../i18n";
import type { ModelOption } from "./im-agent-config-api";

// 折叠入口必须停在「默认模型」标签行右侧，默认不占垂直空间。
// 主模型 select 仍由页面传入 children，避免把 2000 行详情页再堆一份备用编辑器。

function availableFallbacks(models: ModelOption[], primary: string | null, taken: string[]): ModelOption[] {
  return models.filter((model) => model.name !== primary && !taken.includes(model.name));
}

function modelLabel(model: ModelOption): string {
  return model.provider ? `${model.name} · ${model.provider}` : model.name;
}

interface ModelFallbackFieldProps {
  label: string;
  labelHtmlFor: string;
  models: ModelOption[];
  primary: string | null;
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
  children: ReactNode;
}

export function ModelFallbackField({
  label,
  labelHtmlFor,
  models,
  primary,
  value,
  onChange,
  disabled = false,
  children,
}: ModelFallbackFieldProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const remaining = availableFallbacks(models, primary, value);

  function updateAt(index: number, nextId: string) {
    const next = [...value];
    next[index] = nextId;
    onChange(next);
  }

  function removeAt(index: number) {
    onChange(value.filter((_, itemIndex) => itemIndex !== index));
  }

  function addFallback() {
    const nextModel = remaining[0];
    if (!nextModel) return;
    onChange([...value, nextModel.name]);
    setOpen(true);
  }

  return (
    <div className="im-agent-field">
      <div className="im-agent-label-row">
        <Label.Root htmlFor={labelHtmlFor}>{label}</Label.Root>
        <button
          type="button"
          className="im-agent-fallback-toggle"
          aria-expanded={open}
          disabled={disabled}
          onClick={() => setOpen((current) => !current)}
        >
          {open ? (
            t("agents.form.access.fallbackCollapse")
          ) : value.length === 0 ? (
            <>
              {t("agents.form.access.fallbackToggle")}{" "}
              <span className="im-agent-fallback-count">{t("agents.form.access.fallbackUnset")}</span>
            </>
          ) : (
            <>
              {t("agents.form.access.fallbackToggle")}{" "}
              <span className="im-agent-fallback-count">
                {t("agents.form.access.fallbackCount", { count: value.length })}
              </span>
            </>
          )}
        </button>
      </div>
      {children}
      {open ? (
        <div className="im-agent-fallback-panel">
          <p className="im-agent-field-help">
            {value.length === 0
              ? t("agents.form.access.fallbackHelpEmpty")
              : remaining.length === 0
                ? t("agents.form.access.fallbackHelpFull")
                : t("agents.form.access.fallbackHelpPartial")}
          </p>
          <div className="im-agent-fallback-list">
            {value.map((modelId, index) => {
              const taken = value.filter((other) => other !== modelId);
              const options = models.filter((model) => model.name !== primary);
              return (
                <div className="im-agent-fallback-row" key={`${modelId}-${index}`}>
                  <span className="im-agent-fallback-idx">{index + 1}</span>
                  <select
                    className="im-input"
                    aria-label={t("agents.form.access.fallbackRow", { index: index + 1 })}
                    value={modelId}
                    disabled={disabled}
                    autoFocus={index === value.length - 1}
                    onChange={(event) => updateAt(index, event.target.value)}
                  >
                    {options.map((model) => (
                      <option
                        key={model.name}
                        value={model.name}
                        disabled={taken.includes(model.name) && model.name !== modelId}
                      >
                        {modelLabel(model)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="im-agent-fallback-remove"
                    aria-label={t("agents.form.access.fallbackRemove")}
                    disabled={disabled}
                    onClick={() => removeAt(index)}
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
          {remaining.length > 0 ? (
            <button
              type="button"
              className="im-agent-fallback-add"
              disabled={disabled}
              onClick={addFallback}
            >
              {t("agents.form.access.fallbackAdd")}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function fallbacksAfterPrimaryChange(fallbacks: string[], primary: string | null): string[] {
  if (!primary) return fallbacks;
  return fallbacks.filter((modelId) => modelId !== primary);
}
