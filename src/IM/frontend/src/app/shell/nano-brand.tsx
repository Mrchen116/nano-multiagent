type NanoBrandProps = {
  className?: string;
};

/** Shared nano IM brand used by authenticated and unauthenticated top bars. */
export function NanoBrand({ className }: NanoBrandProps) {
  return (
    <div className={`im-nano-brand${className ? ` ${className}` : ""}`}>
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <rect width="24" height="24" rx="6" fill="var(--im-brand)" />
        <path
          d="M7 12.5L10.5 16L17 9.5"
          stroke="var(--im-brand-mark)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>nano IM</span>
      <span data-testid="shell-internal-badge" className="im-shell-internal-badge">
        internal
      </span>
    </div>
  );
}
