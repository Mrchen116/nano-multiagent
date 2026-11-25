/** Send a Node request to IM with the current gateway credential.
 *
 * Args:
 *   baseUrl: Configured HTTP or WebSocket IM URL.
 *   token: Current registered gateway token, or its configured fallback.
 *   path: IM route and query string.
 *   options: Caller request, including JSON or binary content headers.
 * Returns:
 *   The decoded successful IM response.
 */
export type ImRequestOptions = RequestInit & { timeoutMs?: number };

export async function requestIm(baseUrl: string, token: string, path: string, options?: ImRequestOptions): Promise<unknown> {
  const url = new URL(path, baseUrl);
  url.protocol = url.protocol === 'wss:' ? 'https:' : url.protocol === 'ws:' ? 'http:' : url.protocol;
  const headers = new Headers(options?.headers);
  headers.set('Authorization', `Bearer ${token}`);
  const timeoutMs = options?.timeoutMs ?? 10000;
  const { timeoutMs: _timeoutMs, ...init } = options ?? {};
  const response = await fetch(url, { ...init, signal: AbortSignal.any([AbortSignal.timeout(timeoutMs), ...(init.signal ? [init.signal] : [])]), headers });
  if (!response.ok) {
    const error = await response.json().catch(() => undefined) as {detail?:unknown; message?:unknown} | undefined;
    const detail = error?.detail ?? error?.message;
    throw new Error(`IM request failed (${response.status})${typeof detail === 'string' ? `: ${detail}` : ''}`);
  }
  return response.json();
}
