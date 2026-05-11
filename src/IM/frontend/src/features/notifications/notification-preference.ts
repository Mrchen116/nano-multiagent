import { useSyncExternalStore } from "react";

export const NOTIFICATION_PREFERENCE_STORAGE_KEY = "im_notifications_enabled";

type Listener = () => void;
const listeners = new Set<Listener>();

function readStored(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(NOTIFICATION_PREFERENCE_STORAGE_KEY) === "1";
}

export function getNotificationPreference(): boolean {
  return readStored();
}

export function setNotificationPreference(enabled: boolean): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(NOTIFICATION_PREFERENCE_STORAGE_KEY, enabled ? "1" : "0");
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useNotificationPreference(): [boolean, (enabled: boolean) => void] {
  const enabled = useSyncExternalStore(subscribe, readStored, () => false);
  return [enabled, setNotificationPreference];
}
