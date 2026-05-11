import { create } from "zustand";

export const AUTH_STORAGE_KEY = "im_auth_v1";

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  owner_id: string;
  locale: string;
  default_entry_node_id: string | null;
  owned_node_ids: string[];
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
}

interface PersistedAuth {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  hydrated: boolean;

  isAuthenticated(): boolean;
  setSession(pair: TokenPair): void;
  setTokens(tokens: { access_token: string; refresh_token: string }): void;
  clear(): void;
  hydrate(): void;
}

function readPersisted(): PersistedAuth | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<PersistedAuth>;
    if (
      typeof parsed.access_token === "string" &&
      typeof parsed.refresh_token === "string" &&
      parsed.user &&
      typeof parsed.user.id === "string"
    ) {
      return parsed as PersistedAuth;
    }
    return null;
  } catch {
    return null;
  }
}

function writePersisted(value: PersistedAuth | null) {
  if (typeof window === "undefined") return;
  if (value === null) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  } else {
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(value));
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  hydrated: false,

  isAuthenticated() {
    return Boolean(get().accessToken && get().user);
  },

  setSession(pair) {
    writePersisted({
      access_token: pair.access_token,
      refresh_token: pair.refresh_token,
      user: pair.user
    });
    set({
      accessToken: pair.access_token,
      refreshToken: pair.refresh_token,
      user: pair.user,
      hydrated: true
    });
  },

  setTokens(tokens) {
    const current = get();
    if (!current.user) return;
    writePersisted({
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      user: current.user
    });
    set({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token
    });
  },

  clear() {
    writePersisted(null);
    set({ accessToken: null, refreshToken: null, user: null, hydrated: true });
  },

  hydrate() {
    const persisted = readPersisted();
    if (persisted) {
      set({
        accessToken: persisted.access_token,
        refreshToken: persisted.refresh_token,
        user: persisted.user,
        hydrated: true
      });
    } else {
      set({ hydrated: true });
    }
  }
}));
