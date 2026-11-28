import { useEffect, useSyncExternalStore } from "react";
import { authFetch } from "../../auth/auth-fetch";
import { useAuthStore } from "../../auth/auth-store";

const MAX_AVATAR_BLOB_ENTRIES = 256;

const blobUrls = new Map<string, string>();
const inFlight = new Map<string, { promise: Promise<void>; controller: AbortController }>();
const failedKeys = new Set<string>();
const listeners = new Set<() => void>();

function notifyListeners(): void {
  listeners.forEach((listener) => listener());
}

function currentViewerScope(): string {
  return useAuthStore.getState().user?.id ?? "__anon__";
}

function cacheKeyFor(viewerScope: string, userId: string, avatarVersion: string): string {
  return `${viewerScope}|${userId}:${avatarVersion}`;
}

function storeBlobUrl(key: string, objectUrl: string): void {
  const previous = blobUrls.get(key);
  if (previous && previous !== objectUrl) {
    URL.revokeObjectURL(previous);
  }
  blobUrls.delete(key);
  blobUrls.set(key, objectUrl);
  while (blobUrls.size > MAX_AVATAR_BLOB_ENTRIES) {
    const oldestKey = blobUrls.keys().next().value;
    if (oldestKey === undefined) break;
    const oldestUrl = blobUrls.get(oldestKey);
    blobUrls.delete(oldestKey);
    if (oldestUrl) URL.revokeObjectURL(oldestUrl);
  }
}

function ensureAvatarBlobLoaded(userId: string, avatarVersion: string): void {
  const viewerScope = currentViewerScope();
  const key = cacheKeyFor(viewerScope, userId, avatarVersion);
  if (blobUrls.has(key)) {
    // Refresh LRU recency without notifying.
    const existing = blobUrls.get(key)!;
    blobUrls.delete(key);
    blobUrls.set(key, existing);
    return;
  }
  if (inFlight.has(key) || failedKeys.has(key)) return;

  const controller = new AbortController();
  const path = `/im/v1/users/${encodeURIComponent(userId)}/avatar?v=${encodeURIComponent(avatarVersion)}`;
  const promise = authFetch(path, {
    method: "GET",
    cache: "no-store",
    redirect: "error",
    signal: controller.signal,
  })
    .then(async (response) => {
      if (controller.signal.aborted || currentViewerScope() !== viewerScope) return;
      const contentType = (response.headers.get("content-type") ?? "").toLowerCase();
      if (!response.ok || !contentType.startsWith("image/")) {
        failedKeys.add(key);
        notifyListeners();
        return;
      }
      const blob = await response.blob();
      if (controller.signal.aborted || currentViewerScope() !== viewerScope) return;
      if (!blob.size) {
        failedKeys.add(key);
        notifyListeners();
        return;
      }
      const objectUrl = URL.createObjectURL(blob);
      failedKeys.delete(key);
      storeBlobUrl(key, objectUrl);
      notifyListeners();
    })
    .catch(() => {
      if (controller.signal.aborted) return;
      failedKeys.add(key);
      notifyListeners();
    })
    .finally(() => {
      const current = inFlight.get(key);
      if (current?.controller === controller) {
        inFlight.delete(key);
      }
    });

  inFlight.set(key, { promise, controller });
}

function subscribeAvatarBlob(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getAvatarBlobSnapshot(userId?: string, avatarVersion?: string | null): string | null {
  if (!userId || typeof avatarVersion !== "string" || !avatarVersion) return null;
  const key = cacheKeyFor(currentViewerScope(), userId, avatarVersion);
  return blobUrls.get(key) ?? null;
}

/** Subscribe to an account-scoped, single-flight in-memory `ObjectURL` for a human user's custom avatar. */
export function useUserAvatarUrl(userId?: string, avatarVersion?: string | null): string | null {
  const url = useSyncExternalStore(
    subscribeAvatarBlob,
    () => getAvatarBlobSnapshot(userId, avatarVersion),
    () => null,
  );

  useEffect(() => {
    if (!userId || typeof avatarVersion !== "string" || !avatarVersion) return;
    ensureAvatarBlobLoaded(userId, avatarVersion);
  }, [userId, avatarVersion]);

  return url;
}

/** Mark a specific cached avatar `ObjectURL` broken on `<img onError>` and revert to initials fallback. */
export function markAvatarBlobBroken(userId: string, avatarVersion: string): void {
  const key = cacheKeyFor(currentViewerScope(), userId, avatarVersion);
  const existing = blobUrls.get(key);
  if (existing) {
    blobUrls.delete(key);
    URL.revokeObjectURL(existing);
  }
  failedKeys.add(key);
  notifyListeners();
}

/** Evict stale avatar `ObjectURL` entries for `userId` while optionally keeping `keepVersion`. */
export function evictUserAvatarBlobs(userId: string, keepVersion?: string | null): void {
  let changed = false;
  const needle = `|${userId}:`;
  const keepSuffix = typeof keepVersion === "string" && keepVersion ? `|${userId}:${keepVersion}` : null;

  for (const [key, entry] of inFlight.entries()) {
    if (key.includes(needle) && (!keepSuffix || !key.endsWith(keepSuffix))) {
      entry.controller.abort();
      inFlight.delete(key);
      changed = true;
    }
  }
  for (const [key, url] of blobUrls.entries()) {
    if (key.includes(needle) && (!keepSuffix || !key.endsWith(keepSuffix))) {
      blobUrls.delete(key);
      URL.revokeObjectURL(url);
      changed = true;
    }
  }
  for (const key of [...failedKeys]) {
    if (key.includes(needle)) {
      failedKeys.delete(key);
      changed = true;
    }
  }
  if (changed) notifyListeners();
}

/** Clear negative failure markers after stream recovery so mounted avatars retry cleanly. */
export function resetFailedAvatarBlobs(): void {
  if (!failedKeys.size) return;
  failedKeys.clear();
  notifyListeners();
}

/** Abort all in-flight avatar fetches and revoke all cached `ObjectURL`s on sign-out or session switch. */
export function clearAvatarBlobStore(): void {
  const hadState = blobUrls.size > 0 || inFlight.size > 0 || failedKeys.size > 0;
  for (const entry of inFlight.values()) {
    entry.controller.abort();
  }
  inFlight.clear();
  for (const url of blobUrls.values()) {
    URL.revokeObjectURL(url);
  }
  blobUrls.clear();
  failedKeys.clear();
  if (hadState) notifyListeners();
}
