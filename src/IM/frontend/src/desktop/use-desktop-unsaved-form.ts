import { useEffect, useSyncExternalStore } from "react";
import { isDesktopClient } from "./desktop-context";

const dirtySources = new Set<symbol>();
const subscribers = new Set<() => void>();

function emitChange(): void {
  subscribers.forEach((fn) => fn());
}

function subscribe(listener: () => void): () => void {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
}

function getSnapshot(): boolean {
  return dirtySources.size > 0;
}

/** Register an editable form's unsaved dirty state so Desktop background auto-updates never reload over unsaved edits.
 *
 * Args:
 *   isDirty: Whether the current form has unsaved user edits.
 */
export function useDesktopUnsavedForm(isDirty: boolean): void {
  useEffect(() => {
    if (!isDesktopClient() || !isDirty) return;
    const token = Symbol("desktop-unsaved-form");
    dirtySources.add(token);
    emitChange();
    return () => {
      if (dirtySources.delete(token)) {
        emitChange();
      }
    };
  }, [isDirty]);
}

/** Subscribe to aggregate unsaved-form state across mounted Desktop pages. */
export function useHasDesktopUnsavedForm(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
