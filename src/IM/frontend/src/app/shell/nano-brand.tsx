type NanoBrandProps = {
  className?: string;
};

/** Display the shared Crewden identity throughout the Web product. */
export function NanoBrand({ className }: NanoBrandProps) {
  return <div className={`im-nano-brand${className ? ` ${className}` : ''}`}>
    <svg width="24" height="24" viewBox="0 0 64 64" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path fillRule="evenodd" d="M23 8H41C51.5 8 58 14.5 58 25V37C58 47.5 51.5 54 41 54H29L18.9 60.7C17.7 61.5 16 60.6 16 59.1V52.7C9.7 50.4 6 45.1 6 37V25C6 14.5 12.5 8 23 8ZM23 14C15.8 14 12 17.8 12 25V37C12 43.6 15 47 22 48.3V51.6L27 48H41C48.2 48 52 44.2 52 37V25C52 17.8 48.2 14 41 14H23Z" />
      <rect x="21" y="24" width="7" height="12" rx="3.5" /><rect x="36" y="24" width="7" height="12" rx="3.5" />
    </svg>
    <span>crewden</span>
  </div>;
}
