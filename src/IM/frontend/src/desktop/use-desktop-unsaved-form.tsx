import { useEffect, useSyncExternalStore } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { reportDesktopAttention } from "./desktop-api";
import { getDesktopBootContext, isDesktopClient } from "./desktop-context";

const dirtySources = new Set<symbol>();
const subscribers = new Set<() => void>();
let lastReportedSignature: string | null = null;

/** Reset cached attention report signature between unit tests. */
export function resetDesktopAttentionReporterForTest(): void {
  lastReportedSignature = null;
}

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

/** Synchronize active route (`pathname + search`) and aggregate `has_unsaved_form` to the Desktop loopback host across all routes (including `/onboarding`, `/login`, `/register`, and `/bind/confirm` outside `AppShell`). */
export function useDesktopAttentionReporter(): void {
  const location = useLocation();
  const navigate = useNavigate();
  const hasUnsavedForm = useHasDesktopUnsavedForm();

  useEffect(() => {
    if (!isDesktopClient()) return;
    const boot = getDesktopBootContext();
    const current_route = `${location.pathname}${location.search}`;
    const sig = `${boot?.imOrigin ?? ""}|${boot?.contextEpoch ?? 0}|${current_route}|${hasUnsavedForm ? "1" : "0"}`;
    if (lastReportedSignature === sig) return;
    lastReportedSignature = sig;
    void reportDesktopAttention({
      loaded_ui_sha: boot?.bundleSha,
      current_route,
      has_unsaved_form: hasUnsavedForm,
    })
      .then((data) => {
        if (data?.navigate_to && data.navigate_to !== current_route) {
          navigate(data.navigate_to);
        }
      })
      .catch(() => {
        if (lastReportedSignature === sig) {
          lastReportedSignature = null;
        }
      });
  }, [hasUnsavedForm, location.pathname, location.search, navigate]);
}

/** Root router layout wrapper ensuring standalone routes outside `AppShell` report Desktop route & dirty form state. */
export function DesktopRouteAttentionLayout() {
  useDesktopAttentionReporter();
  return <Outlet />;
}
