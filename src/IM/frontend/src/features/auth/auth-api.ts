import type { TokenPair } from "./auth-store";

function apiBase() {
  return (import.meta.env.VITE_IM_API_BASE_URL ?? "").replace(/\/$/, "");
}

export function withBase(path: string) {
  return `${apiBase()}${path}`;
}

export class AuthApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`auth request failed: ${status} (${detail})`);
    this.name = "AuthApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(withBase(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text();
    let detail = text || res.statusText;
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (typeof parsed.detail === "string" && parsed.detail.length > 0) detail = parsed.detail;
    } catch {
      // ignore json parse failure; raw text is the detail
    }
    throw new AuthApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function login(input: { username: string; password: string }) {
  return postJson<TokenPair>("/im/v1/auth/login", input);
}

export function register(input: { username: string; password: string; display_name: string; locale?: string }) {
  return postJson<TokenPair>("/im/v1/auth/register", {
    username: input.username,
    password: input.password,
    display_name: input.display_name,
    locale: input.locale ?? "en"
  });
}

export function refreshTokens(refresh_token: string) {
  return postJson<TokenPair>("/im/v1/auth/refresh", { refresh_token });
}

export function logoutApi(refresh_token: string) {
  return postJson<{ ok: boolean }>("/im/v1/auth/logout", { refresh_token });
}
