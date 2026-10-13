/** Shared outline icons for the desktop user menu and mobile Me page. */
export function UserMenuIcon({ kind }: { kind: "account" | "nodes" | "models" | "policies" | "members" | "language" | "logout" }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {kind === "account" && <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>}
      {kind === "nodes" && <><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8m-4-4v4" /></>}
      {kind === "models" && <><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" /></>}
      {kind === "policies" && <><path d="M4 7h6m4 0h6M4 17h10m4 0h2" /><circle cx="12" cy="7" r="2" /><circle cx="16" cy="17" r="2" /></>}
      {kind === "members" && <><circle cx="9" cy="8" r="3" /><path d="M3 21v-2a6 6 0 0 1 12 0v2m1-16a3 3 0 0 1 0 6m5 10v-2a6 6 0 0 0-4-5.66" /></>}
      {kind === "language" && <><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18" /></>}
      {kind === "logout" && <><path d="M9 4H4v16h5m4-12 4 4-4 4m-5-4h13" /></>}
    </svg>
  );
}
