import { Ref, useState } from "react";

type AuthTextFieldProps = {
  id: string;
  label: string;
  optionalLabel?: string;
  value: string;
  onValueChange: (value: string) => void;
  autoComplete: string;
  hint?: string;
  error?: string;
  inputRef?: Ref<HTMLInputElement>;
  disabled?: boolean;
  maxLength?: number;
  required?: boolean;
};

export function AuthTextField({
  id,
  label,
  optionalLabel,
  value,
  onValueChange,
  autoComplete,
  hint,
  error,
  inputRef,
  disabled = false,
  maxLength,
  required = true
}: AuthTextFieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="im-auth-field">
      <label className="im-auth-label-row" htmlFor={id}>
        <span>{label}</span>
        {optionalLabel && <span className="im-auth-optional">{optionalLabel}</span>}
      </label>
      <input
        id={id}
        ref={inputRef}
        type="text"
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        aria-describedby={describedBy}
        aria-invalid={Boolean(error)}
        disabled={disabled}
        maxLength={maxLength}
        required={required}
      />
      {hint && (
        <p id={hintId} className="im-auth-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="im-auth-field-error">
          {error}
        </p>
      )}
    </div>
  );
}

type AuthPasswordFieldProps = Omit<AuthTextFieldProps, "optionalLabel"> & {
  showLabel: string;
  hideLabel: string;
};

export function AuthPasswordField({ showLabel, hideLabel, ...props }: AuthPasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  const hintId = props.hint ? `${props.id}-hint` : undefined;
  const errorId = props.error ? `${props.id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="im-auth-field">
      <label className="im-auth-label-row" htmlFor={props.id}>
        <span>{props.label}</span>
      </label>
      <span className="im-auth-input-shell">
        <input
          id={props.id}
          ref={props.inputRef}
          className="im-auth-password-input"
          type={visible ? "text" : "password"}
          autoComplete={props.autoComplete}
          value={props.value}
          onChange={(event) => props.onValueChange(event.target.value)}
          aria-describedby={describedBy}
          aria-invalid={Boolean(props.error)}
          disabled={props.disabled}
          maxLength={props.maxLength}
          required={props.required ?? true}
        />
        <button
          type="button"
          className="im-auth-password-toggle"
          aria-label={visible ? hideLabel : showLabel}
          onClick={() => setVisible((current) => !current)}
          disabled={props.disabled}
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </span>
      {props.hint && (
        <p id={hintId} className="im-auth-hint">
          {props.hint}
        </p>
      )}
      {props.error && (
        <p id={errorId} className="im-auth-field-error">
          {props.error}
        </p>
      )}
    </div>
  );
}

function EyeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
      <circle cx="12" cy="12" r="2.5" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m3 3 18 18M10.6 6.2A9.9 9.9 0 0 1 12 6c6.5 0 10 6 10 6a16 16 0 0 1-3 3.7M6.4 6.4C3.6 8.2 2 12 2 12s3.5 6 10 6a9.4 9.4 0 0 0 3.2-.5" />
    </svg>
  );
}
