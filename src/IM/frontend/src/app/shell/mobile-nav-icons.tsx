import type { ReactNode } from "react";

type MobileNavIconProps = {
  name: "chat" | "people" | "agents" | "me" | "tasks";
  children: ReactNode;
};

function MobileNavIcon({ name, children }: MobileNavIconProps) {
  return (
    <svg
      aria-hidden="true"
      data-mobile-nav-icon={name}
      fill="none"
      focusable="false"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      {children}
    </svg>
  );
}

export function ChatNavIcon() {
  return (
    <MobileNavIcon name="chat">
      <path
        d="M6.75 5.25h10.5A2.75 2.75 0 0 1 20 8v6a2.75 2.75 0 0 1-2.75 2.75h-5.4L7 20v-3.25h-.25A2.75 2.75 0 0 1 4 14V8a2.75 2.75 0 0 1 2.75-2.75Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path d="M8.25 11h7.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </MobileNavIcon>
  );
}

export function AgentsNavIcon() {
  return (
    <MobileNavIcon name="agents">
      <path
        d="M6.3 14.9V9.7A2.6 2.6 0 0 1 7.6 7.45l3.1-1.8a2.6 2.6 0 0 1 2.6 0l3.15 1.82"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M17.7 9.1v5.2a2.6 2.6 0 0 1-1.3 2.25l-3.1 1.8a2.6 2.6 0 0 1-2.6 0l-3.15-1.82"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="m12 8.7 2.85 1.65v3.3L12 15.3l-2.85-1.65v-3.3L12 8.7Z"
        fill="currentColor"
      />
      <circle cx="17.75" cy="7.55" r="1.45" fill="currentColor" />
      <circle cx="6.25" cy="16.45" r="1.45" fill="currentColor" />
    </MobileNavIcon>
  );
}

export function MeNavIcon() {
  return (
    <MobileNavIcon name="me">
      <circle cx="12" cy="8" r="3" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M5.75 19.25v-1.1C5.75 15.15 8.55 13 12 13s6.25 2.15 6.25 5.15v1.1"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </MobileNavIcon>
  );
}

export function PeopleNavIcon() {
  return (
    <MobileNavIcon name="people">
      <circle cx="9.25" cy="8.25" r="2.75" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M4 18.75v-.85C4 15.35 6.35 13.5 9.25 13.5s5.25 1.85 5.25 4.4v.85"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <circle cx="16.25" cy="9" r="2.25" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M16.5 13.75c2 .15 3.5 1.65 3.5 3.8v1.2"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </MobileNavIcon>
  );
}

export function TasksNavIcon() {
  return <MobileNavIcon name="tasks">
    <rect x="3" y="4" width="6" height="5" rx="1" stroke="currentColor" strokeWidth="1.8" />
    <rect x="15" y="15" width="6" height="5" rx="1" stroke="currentColor" strokeWidth="1.8" />
    <path d="M9 6.5h5a4 4 0 0 1 4 4V15M6 9v8.5h9" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  </MobileNavIcon>;
}
