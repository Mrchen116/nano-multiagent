import type {BrowserSession} from './auth-store';

interface PageBootstrap {session:BrowserSession; data:Record<string,unknown>}
let bootstrap:PageBootstrap | null | undefined;
let loadedAt = 0;

/** Consume only the current document's server-authorized initial reads. */
export function readPageBootstrap():PageBootstrap | null {
  if (bootstrap !== undefined) return bootstrap;
  const element = document.getElementById('nano-page-bootstrap');
  bootstrap = element ? JSON.parse(element.textContent ?? 'null') as PageBootstrap : null;
  element?.remove();
  loadedAt = Date.now();
  return bootstrap;
}

/** Bind one-shot page data to the exact authenticated access token. */
export function takePageRead(path:string,token:string|null):Response | undefined {
  const page = readPageBootstrap();
  if (!page || page.session.access_token !== token || Date.now()-loadedAt>5000 || !(path in page.data)) return;
  const data=page.data[path];
  delete page.data[path];
  return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
}
