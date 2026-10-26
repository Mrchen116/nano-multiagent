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
export async function requestIm(baseUrl: string, token: string, path: string, options?: RequestInit): Promise<unknown> {
  const url = new URL(path, baseUrl);
  url.protocol = url.protocol === 'wss:' ? 'https:' : url.protocol === 'ws:' ? 'http:' : url.protocol;
  const headers = new Headers(options?.headers);
  headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(10000), headers });
  if (!response.ok) throw new Error(`IM external projection failed: ${response.status}`);
  return response.json();
}
