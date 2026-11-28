import type { DesktopUpdaterSnapshot } from "@nano/product-contracts/desktop-local";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useAuthStore } from "../features/auth/auth-store";
import {
  cancelNodeUpdate,
  listNodes,
  type NodeSettingsProfile,
  type NodeUpdateView,
} from "../features/settings/im-settings-api";
import {
  nodeUpdateActive,
  nodeUpdateNeedsRecovery,
} from "../features/settings/nodes/node-update-panel";
import {
  applyDesktopUpdate,
  cancelDesktopUpdate,
  checkDesktopUpdates,
  controlDesktopLocalNode,
  dismissDesktopUpdaterNotice,
  getDesktopUpdaterSnapshot,
  inspectDesktopLocalNode,
  openDesktopUpdaterInstaller,
  setDesktopAutoUpdatePreference,
} from "./desktop-api";
import { getDesktopBootContext, isDesktopClient } from "./desktop-context";

let userMenuOpenFlag = false;
const menuListeners = new Set<() => void>();

/** Notify `DesktopUpdatePill` whether `UserMenu` is currently open so duplicate popovers never compete. */
export function setDesktopUserMenuOpen(open: boolean): void {
  if (userMenuOpenFlag === open) return;
  userMenuOpenFlag = open;
  menuListeners.forEach((fn) => fn());
}

export function useDesktopUserMenuOpen(): boolean {
  return useSyncExternalStore(
    (cb) => {
      menuListeners.add(cb);
      return () => menuListeners.delete(cb);
    },
    () => userMenuOpenFlag,
    () => false,
  );
}

/** Build a route-preserving cache-busted relative URL when `--headless-host` advances `reload_generation`. */
export function buildReloadTargetUrl(pathname: string, search: string): string {
  const params = new URLSearchParams(search);
  params.set("_desktop_reload", String(Date.now()));
  const qs = params.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

export interface MergedDesktopUpdaterView {
  snapshot: DesktopUpdaterSnapshot | undefined;
  isLoading: boolean;
  manualCheckFeedback: boolean;
  remoteRecoveryRequired: boolean;
  remoteOperation: NodeUpdateView["operation"] | null;
  localNodeId: string | undefined;
  checkPending: boolean;
  applyPending: boolean;
  cancelPending: boolean;
  prefsPending: boolean;
  recoverPending: boolean;
  triggerCheck: () => Promise<void>;
  triggerApply: () => Promise<void>;
  triggerCancel: () => Promise<void>;
  triggerOpenInstaller: () => Promise<void>;
  triggerToggleAutoUpdate: (enabled: boolean) => Promise<void>;
  triggerDismiss: (kind: "just_updated" | "capsule" | "reopen_capsule") => Promise<void>;
  triggerRecoverLocalNode: () => Promise<void>;
}

/** Shared Desktop updater state, cross-surface mutations, headless reload convergence, and remote node-update fusion. */
export function useDesktopUpdater(): MergedDesktopUpdaterView {
  const desktop = isDesktopClient();
  const boot = getDesktopBootContext();
  const userId = useAuthStore((s) => s.user?.id);
  const client = useQueryClient();
  const [manualCheckFeedback, setManualCheckFeedback] = useState(false);
  const feedbackTimerRef = useRef<number | null>(null);
  const baselineGenRef = useRef<number | null>(null);
  const reloadingRef = useRef(false);

  const queryKey = ["desktop", "updater", boot?.imOrigin ?? "", boot?.contextEpoch ?? 0] as const;

  const updaterQuery = useQuery({
    queryKey,
    queryFn: getDesktopUpdaterSnapshot,
    enabled: desktop,
    refetchInterval: (q) => {
      const phase = q.state.data?.phase;
      if (
        phase === "checking" ||
        phase === "preparing" ||
        phase === "downloading_installer" ||
        phase === "waiting_for_tasks" ||
        phase === "switching"
      ) {
        return 1_000;
      }
      return 30_000;
    },
  });

  const localInspectQuery = useQuery({
    queryKey: ["desktop", "local-node", userId],
    queryFn: () => inspectDesktopLocalNode(),
    enabled: desktop && Boolean(userId),
    staleTime: 10_000,
  });

  const nodesQuery = useQuery({
    queryKey: ["settings", "nodes"],
    queryFn: listNodes,
    enabled: desktop && Boolean(userId),
    staleTime: 15_000,
    refetchInterval: (q) =>
      (q.state.data ?? []).some((n) => nodeUpdateActive(n.update)) ? 1_500 : false,
  });

  // Clean `_desktop_reload` cache-buster query param from address bar after reload without touching React Router state.
  useEffect(() => {
    if (!desktop || typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (url.searchParams.has("_desktop_reload")) {
      url.searchParams.delete("_desktop_reload");
      const clean = `${url.pathname}${url.search}${url.hash}`;
      window.history.replaceState(window.history.state, "", clean);
    }
  }, [desktop]);

  useEffect(() => {
    if (!desktop) return;
    const onChanged = () => {
      void client.invalidateQueries({ queryKey: ["desktop", "updater"] });
    };
    window.addEventListener("crewden:updater-changed", onChanged);
    return () => window.removeEventListener("crewden:updater-changed", onChanged);
  }, [client, desktop]);

  useEffect(
    () => () => {
      if (feedbackTimerRef.current !== null) {
        window.clearTimeout(feedbackTimerRef.current);
      }
    },
    [],
  );

  // Converge hot-bundle reloads even when running under `--headless-host` (`NoopUiBridge::reload_webview`).
  useEffect(() => {
    const snap = updaterQuery.data;
    if (!desktop || !snap || typeof window === "undefined") return;
    if (baselineGenRef.current === null) {
      baselineGenRef.current = snap.reload_generation;
      return;
    }
    if (snap.reload_generation > baselineGenRef.current && !reloadingRef.current) {
      reloadingRef.current = true;
      window.dispatchEvent(new Event("crewden:before-hot-reload"));
      const targetUrl = buildReloadTargetUrl(window.location.pathname, window.location.search);
      window.location.replace(targetUrl);
    }
  }, [desktop, updaterQuery.data]);

  const inspect = localInspectQuery.data;
  const sameOwnerLocalNodeId =
    inspect && (inspect.ownership === "managed_online" || inspect.ownership === "managed_stopped")
      ? inspect.node_id
      : undefined;
  const matchedNode: NodeSettingsProfile | undefined = sameOwnerLocalNodeId
    ? (nodesQuery.data ?? []).find((n) => n.node_id === sameOwnerLocalNodeId)
    : undefined;
  const remoteUpdate = matchedNode?.update;
  const remoteActive = nodeUpdateActive(remoteUpdate);
  const remoteRecoveryRequired = nodeUpdateNeedsRecovery(remoteUpdate);

  // Merge remote-initiated `NodeUpdateOperation` into snapshot so Web-triggered updates are visible & cancellable here too.
  let mergedSnapshot = updaterQuery.data;
  if (mergedSnapshot && remoteActive && remoteUpdate?.operation && !remoteUpdate.operation.cancel_requested) {
    const op = remoteUpdate.operation;
    const mappedPhase =
      op.state === "waiting"
        ? "waiting_for_tasks"
        : op.state === "switching" || op.state === "verifying" || op.state === "rolling_back"
          ? "switching"
          : "preparing";
    if (
      mergedSnapshot.phase === "idle" ||
      mergedSnapshot.phase === "up_to_date" ||
      mergedSnapshot.phase === "available" ||
      mergedSnapshot.phase === "ready_to_switch"
    ) {
      mergedSnapshot = {
        ...mergedSnapshot,
        phase: mappedPhase,
        mode: "hot_bundle",
        target: mergedSnapshot.target ?? {
          version: remoteUpdate.target?.version ?? matchedNode?.version ?? mergedSnapshot.current_version,
          release_notes: remoteUpdate.target?.release_notes ?? null,
        },
        active_tasks: Math.max(mergedSnapshot.active_tasks, inspect?.active_tasks ?? 0),
      };
    }
  }

  const syncSnapshot = (next: DesktopUpdaterSnapshot) => {
    client.setQueryData(queryKey, next);
  };

  const checkMutation = useMutation({
    mutationFn: () => checkDesktopUpdates(true),
    onSuccess: (next) => {
      syncSnapshot(next);
      if (next.phase === "up_to_date" || next.phase === "unpublished") {
        setManualCheckFeedback(true);
        if (feedbackTimerRef.current !== null) window.clearTimeout(feedbackTimerRef.current);
        feedbackTimerRef.current = window.setTimeout(() => setManualCheckFeedback(false), 4500);
      }
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => {
      window.dispatchEvent(new Event("crewden:before-hot-reload"));
      return applyDesktopUpdate();
    },
    onSuccess: syncSnapshot,
  });

  const cancelMutation = useMutation({
    mutationFn: async () => {
      if (remoteActive && sameOwnerLocalNodeId && remoteUpdate?.operation) {
        await cancelNodeUpdate(sameOwnerLocalNodeId, remoteUpdate.operation.id).catch(() => {});
      }
      const next = await cancelDesktopUpdate();
      await client.invalidateQueries({ queryKey: ["settings", "nodes"] });
      return next;
    },
    onSuccess: syncSnapshot,
  });

  const openInstallerMutation = useMutation({
    mutationFn: openDesktopUpdaterInstaller,
    onSuccess: syncSnapshot,
  });

  const prefsMutation = useMutation({
    mutationFn: (enabled: boolean) => setDesktopAutoUpdatePreference({ auto_update: enabled }),
    onSuccess: syncSnapshot,
  });

  const dismissMutation = useMutation({
    mutationFn: (kind: "just_updated" | "capsule" | "reopen_capsule") =>
      dismissDesktopUpdaterNotice({ kind }),
    onSuccess: syncSnapshot,
  });

  const recoverMutation = useMutation({
    mutationFn: () => controlDesktopLocalNode({ action: "restart" }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["desktop", "local-node", userId] }),
        client.invalidateQueries({ queryKey: ["settings", "nodes"] }),
        client.invalidateQueries({ queryKey: ["desktop", "updater"] }),
      ]);
    },
  });

  return {
    snapshot: mergedSnapshot,
    isLoading: updaterQuery.isLoading,
    manualCheckFeedback,
    remoteRecoveryRequired,
    remoteOperation: remoteUpdate?.operation ?? null,
    localNodeId: sameOwnerLocalNodeId,
    checkPending: checkMutation.isPending,
    applyPending: applyMutation.isPending,
    cancelPending: cancelMutation.isPending,
    prefsPending: prefsMutation.isPending,
    recoverPending: recoverMutation.isPending,
    triggerCheck: async () => {
      await checkMutation.mutateAsync();
    },
    triggerApply: async () => {
      await applyMutation.mutateAsync();
    },
    triggerCancel: async () => {
      await cancelMutation.mutateAsync();
    },
    triggerOpenInstaller: async () => {
      await openInstallerMutation.mutateAsync();
    },
    triggerToggleAutoUpdate: async (enabled: boolean) => {
      await prefsMutation.mutateAsync(enabled);
    },
    triggerDismiss: async (kind) => {
      await dismissMutation.mutateAsync(kind);
    },
    triggerRecoverLocalNode: async () => {
      await recoverMutation.mutateAsync();
    },
  };
}
