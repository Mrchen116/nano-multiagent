import { nativeRequest } from './bridge';

export const withBase = (path: string) => `/im/v1/intelligent-ui${path}`;

export async function resourceFetch(path: string, init?: RequestInit) {
  init?.signal?.throwIfAborted();
  const result = await nativeRequest({type: 'resource', path});
  init?.signal?.throwIfAborted();
  return new Response(JSON.stringify(result), {headers: {'Content-Type': 'application/json'}});
}
