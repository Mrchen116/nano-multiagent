import { create } from "zustand";

export const AUTH_STORAGE_KEY = "im_auth_v1";
if (typeof window !== "undefined") window.localStorage.removeItem(AUTH_STORAGE_KEY);

export interface AuthUser {
  membership_status: "none" | "pending" | "active" | "suspended";
  personal_space_enabled?: boolean;
  account_status?: "active" | "pending" | "suspended";
  is_company_admin: boolean;
  id: string;
  username: string;
  display_name: string;
  owner_id: string;
  locale: string;
  timezone?: string | null;
  default_entry_node_id: string | null;
  owned_node_ids: string[];
  created_at: string;
}

/** Accept legacy company snapshots while distinguishing personal access from team approval. */
export function accountEnabled(user: AuthUser | null | undefined): boolean {
  return !!user && (user.account_status === "active" || !!user.personal_space_enabled || user.membership_status === "active");
}

export interface BrowserSession {
  access_token: string;
  user: AuthUser;
}

interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
  hydrated: boolean;
  hydrationError: boolean;
  revision: number;
  isAuthenticated(): boolean;
  setSession(session: BrowserSession): void;
  setTokens(tokens: { access_token: string }): void;
  replaceUser(user: AuthUser): boolean;
  clear(): void;
  hydrate(): Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  hydrated: false,
  hydrationError: false,
  revision: 0,
  isAuthenticated() { return Boolean(get().accessToken && get().user); },
  setSession(session) {
    set({ accessToken: session.access_token, user: session.user, hydrated: true,
      hydrationError: false, revision: get().revision + 1 });
  },
  setTokens(tokens) {
    if (get().user) set({ accessToken: tokens.access_token });
  },
  replaceUser(user) {
    if (get().user?.id !== user.id || !get().accessToken) return false;
    set({ user });
    return true;
  },
  clear() {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    set({ accessToken: null, user: null, hydrated: true, hydrationError: false, revision: get().revision + 1 });
  },
  async hydrate() {
    // Old script-readable credentials are deliberately discarded, never exchanged.
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    const { restoreSession } = await import("./auth-session");
    await restoreSession();
  }
}));
