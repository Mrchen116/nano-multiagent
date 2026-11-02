export const withBase = (path: string) => `/im/v1/intelligent-ui${path}`;

/** Use Nano authentication for the upstream library’s resource routes. */
export async function resourceFetch(path: string, init?: RequestInit) {
  const {authFetch} = await import('../../../auth/auth-fetch');
  return authFetch(path, init);
}
