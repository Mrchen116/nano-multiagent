import { macDistributionLabel } from '../../desktop/mac-distribution-label';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronDown, Copy, Play } from 'lucide-react';
import { isDesktopClient } from '../../desktop/desktop-context';
import { useTranslation } from '../../i18n';
import { accountEnabled, useAuthStore } from '../auth/auth-store';
import type { PublicInstallMaterials } from '../onboarding/onboarding-api';
import './public-download-section.css';

export type VisitorPlatform = 'macos' | 'windows' | 'ios' | 'other';

/** Detect the visitor's current client OS so the homepage recommends the matching build first. */
export function detectVisitorPlatform(
  nav?: Pick<Navigator, 'userAgent' | 'platform' | 'maxTouchPoints'>,
): VisitorPlatform {
  const target = nav ?? (typeof navigator !== 'undefined' ? navigator : undefined);
  if (!target) return 'other';
  const ua = target.userAgent ?? '';
  const platform = target.platform ?? '';
  if (/iPhone|iPad|iPod/i.test(ua) || (platform === 'MacIntel' && (target.maxTouchPoints ?? 0) > 1)) {
    return 'ios';
  }
  if (/Windows/i.test(ua) || /^Win/i.test(platform)) {
    return 'windows';
  }
  if (/Macintosh|Mac OS X/i.test(ua) || /^Mac/i.test(platform)) {
    return 'macos';
  }
  return 'other';
}

function readPublicInstallBootstrap(): PublicInstallMaterials | null {
  if (typeof document === 'undefined') return null;
  const el = document.getElementById('nano-public-install');
  if (!el?.textContent) return null;
  try {
    const parsed = JSON.parse(el.textContent) as PublicInstallMaterials;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

/** Load public client download metadata from HTML bootstrap (0 network calls on Web) or loopback/dev API. */
export function usePublicInstallMaterials() {
  const [materials, setMaterials] = useState<PublicInstallMaterials | null>(() => readPublicInstallBootstrap());
  const [loaded, setLoaded] = useState<boolean>(() => readPublicInstallBootstrap() !== null);

  useEffect(() => {
    const bootstrapped = readPublicInstallBootstrap();
    if (bootstrapped) {
      setMaterials(bootstrapped);
      setLoaded(true);
      return;
    }
    const shouldFetchFallback = isDesktopClient() || Boolean(import.meta.env.DEV && !import.meta.env.VITEST);
    if (!shouldFetchFallback || typeof globalThis.fetch !== 'function') {
      setLoaded(true);
      return;
    }
    const controller = new AbortController();
    Promise.resolve(
      globalThis.fetch('/im/v1/public/install', {
        credentials: 'same-origin',
        signal: controller.signal,
      }),
    )
      .then(async response => {
        if (!response || !response.ok) return null;
        return (await response.json()) as PublicInstallMaterials;
      })
      .then(data => {
        if (!controller.signal.aborted && data && typeof data === 'object') {
          setMaterials(data);
        }
      })
      .catch(() => {
        /* Keep graceful fallback actions when offline. */
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoaded(true);
      });

    return () => controller.abort();
  }, []);

  return { materials, loaded };
}

function AppleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.96 6.32c.67-.81 1.12-1.94 1-3.07-.96.04-2.13.64-2.82 1.45-.61.7-.15 1.85-1.01 2.96 1.07.08 2.16-.53 2.83-1.34" />
    </svg>
  );
}

function WindowsGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M3 3h8.5v8.5H3V3zm9.5 0H21v8.5h-8.5V3zM3 12.5h8.5V21H3v-8.5zm9.5 0H21V21h-8.5v-8.5z" />
    </svg>
  );
}

function IphoneGlyph() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="6" y="2" width="12" height="20" rx="3" />
      <line x1="10" y1="18" x2="14" y2="18" />
    </svg>
  );
}

function BouncyWinkMark() {
  return (
    <svg className="crew-download-mark" viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <clipPath id="crew-dl-sq">
          <path d="M 50,0 C 79,0 89.5,0 94.75,5.25 C 100,10.5 100,21 100,50 C 100,79 100,89.5 94.75,94.75 C 89.5,100 79,100 50,100 C 21,100 10.5,100 5.25,94.75 C 0,89.5 0,79 0,50 C 0,21 0,10.5 5.25,5.25 C 10.5,0 21,0 50,0 Z" />
        </clipPath>
      </defs>
      <g clipPath="url(#crew-dl-sq)">
        <rect width="100" height="100" fill="#FFF0B5" />
        <g transform="translate(51 49) rotate(-9) translate(-50 -50)">
          <path
            fill="#6B43D8"
            d="M 33,12 H 67 C 82.5,12 91,20.5 91,36 V 52 C 91,67.5 82.5,76 67,76 H 44 L 23.5,90.5 C 20.6,92.5 17,90.4 17,86.9 V 73.2 C 11.2,68.8 9,61.5 9,52 V 36 C 9,20.5 17.5,12 33,12 Z"
          />
          <rect x="32.5" y="33" width="12" height="19" rx="6" fill="#FFF0B5" />
          <path
            d="M 55.5,44.5 Q 63,34.5 70.5,44.5"
            fill="none"
            stroke="#FFF0B5"
            strokeWidth="8.5"
            strokeLinecap="round"
          />
        </g>
      </g>
    </svg>
  );
}

/** Render the Hero primary/secondary CTA pair matched to the visitor's detected OS. */
export function HeroDownloadActions({
  materials,
  onWatch,
}: {
  materials: PublicInstallMaterials | null;
  onWatch(): void;
}) {
  const { t } = useTranslation();
  const dl = (key: string, opts?: Record<string, unknown>) => t(`crewdenDownload.${key}`, opts);
  const user = useAuthStore(s => s.user);
  const [platform] = useState<VisitorPlatform>(() => detectVisitorPlatform());
  const webEntryPath = user ? (accountEnabled(user) ? '/chat' : '/membership') : '/register';
  const webEntryLabel = user ? dl('openWorkspace') : dl('useInBrowser');

  if (isDesktopClient()) {
    return (
      <div className="crew-hero-cta-group">
        <div className="crew-actions">
          <Link className="crew-primary" to={user ? (accountEnabled(user) ? '/chat' : '/membership') : '/login'}>
            {user ? dl('openWorkspace') : t('auth.login.submit')}
          </Link>
          <button type="button" className="crew-watch" onClick={onWatch}>
            <Play />
            {t('crewdenHome.watch')}
          </button>
        </div>
      </div>
    );
  }

  const mac = platform === 'macos' ? materials?.desktop_darwin_arm64 : null;
  const macDownload = mac?.download_url;
  const winDownload = platform === 'windows' ? materials?.desktop_win32_x64?.download_url : undefined;
  const iosDownload = platform === 'ios' ? materials?.ios?.download_url : undefined;
  const matchedDownload = macDownload || winDownload || iosDownload;

  if (matchedDownload) {
    const heroCtaLabel =
      platform === 'macos'
        ? dl('heroMac')
        : platform === 'windows'
          ? dl('heroWindows')
          : dl('heroIos');
    const heroMeta =
      platform === 'macos'
        ? dl('heroMetaMac')
        : platform === 'windows'
          ? dl('heroMetaWindows')
          : dl('heroMetaIos');
    const otherPlatformsLabel =
      platform === 'macos'
        ? dl('otherFromMac')
        : platform === 'windows'
          ? dl('otherFromWindows')
          : dl('otherFromIos');

    return (
      <div className="crew-hero-cta-group" data-testid="hero-smart-download">
        <div className="crew-actions">
          <a
            className="crew-primary crew-primary--download"
            href={matchedDownload}
            target="_blank"
            rel="noreferrer"
          >
            {platform === 'macos' ? <AppleGlyph /> : platform === 'windows' ? <WindowsGlyph /> : <IphoneGlyph />}
            <span>{heroCtaLabel}</span>
          </a>
          <Link className="crew-secondary-cta" to={webEntryPath}>
            {webEntryLabel}
          </Link>
          <button type="button" className="crew-watch" onClick={onWatch}>
            <Play />
            {t('crewdenHome.watch')}
          </button>
        </div>
        <div className="crew-hero-platforms">
          <span>{heroMeta}{mac && ` · ${t(macDistributionLabel(mac))}`}</span>
          <span className="crew-hero-platforms-sep" aria-hidden="true">·</span>
          <a className="crew-hero-platforms-link" href="#download">
            {otherPlatformsLabel}
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="crew-hero-cta-group" data-testid="hero-default-actions">
      <div className="crew-actions">
        <Link className="crew-primary" to={webEntryPath}>
          {user ? dl('openWorkspace') : t('auth.register.submit')}
        </Link>
        <button type="button" className="crew-watch" onClick={onWatch}>
          <Play />
          {t('crewdenHome.watch')}
        </button>
      </div>
      <div className="crew-hero-platforms">
        {platform === 'ios' && (
          <>
            <span>{dl('iosSoonHeroHint')}</span>
            <span className="crew-hero-platforms-sep" aria-hidden="true">·</span>
          </>
        )}
        <a className="crew-hero-platforms-link" href="#download">
          {platform === 'ios' ? dl('otherFromIos') : dl('allPlatformsLink')}
        </a>
      </div>
    </div>
  );
}

/** Multi-platform client download hub (macOS · Windows · iOS + lightweight background node). */
export function PublicDownloadSection({ materials }: { materials: PublicInstallMaterials | null }) {
  const { t } = useTranslation();
  const dl = (key: string, opts?: Record<string, unknown>) => t(`crewdenDownload.${key}`, opts);
  const [platform] = useState<VisitorPlatform>(() => detectVisitorPlatform());
  const [headlessOpen, setHeadlessOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const mac = materials?.desktop_darwin_arm64 ?? null;
  const win = materials?.desktop_win32_x64 ?? null;
  const ios = materials?.ios ?? null;
  const unixCommand = materials?.available ? materials.command : '';

  async function copyCommand() {
    if (!unixCommand) return;
    try {
      await navigator.clipboard.writeText(unixCommand);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="crew-download-section" id="download" aria-labelledby="crew-download-title">
      <div className="crew-download-shell">
        <div className="crew-download-head">
          <BouncyWinkMark />
          <div className="crew-download-head-copy">
            <h2 id="crew-download-title">{dl('sectionTitle')}</h2>
            <p>{dl('sectionSubtitle')}</p>
          </div>
        </div>

        <div className="crew-download-grid">
          <article
            className={`crew-plat-card${platform === 'macos' ? ' is-detected' : ''}`}
            data-testid="download-card-macos"
          >
            <div className="crew-plat-top">
              <span className="crew-plat-glyph">
                <AppleGlyph />
              </span>
              {platform === 'macos' && <span className="crew-plat-badge">{dl('currentDevice')}</span>}
            </div>
            <h3>macOS</h3>
            <div className="crew-plat-req">
              {dl('macosReq')}{mac && ` · v${mac.version} · ${t(macDistributionLabel(mac))}`}
            </div>
            <p className="crew-plat-desc">{dl('macosDesc')}</p>
            {mac?.download_url ? (
              <a className="crew-plat-btn" href={mac.download_url} target="_blank" rel="noreferrer">
                {dl('macosAction')}
              </a>
            ) : (
              <span className="crew-plat-btn is-muted" aria-disabled="true">
                {dl('desktopUnpublished')}
              </span>
            )}
          </article>

          <article
            className={`crew-plat-card${platform === 'windows' ? ' is-detected' : ''}`}
            data-testid="download-card-windows"
          >
            <div className="crew-plat-top">
              <span className="crew-plat-glyph">
                <WindowsGlyph />
              </span>
              {platform === 'windows' && <span className="crew-plat-badge">{dl('currentDevice')}</span>}
            </div>
            <h3>Windows</h3>
            <div className="crew-plat-req">
              {win?.version ? `${dl('windowsReq')} · v${win.version}` : dl('windowsReq')}
            </div>
            <p className="crew-plat-desc">{dl('windowsDesc')}</p>
            {win?.download_url ? (
              <a className="crew-plat-btn" href={win.download_url} target="_blank" rel="noreferrer">
                {dl('windowsAction')}
              </a>
            ) : (
              <span className="crew-plat-btn is-muted" aria-disabled="true">
                {dl('desktopUnpublished')}
              </span>
            )}
          </article>

          <article
            className={`crew-plat-card${platform === 'ios' ? ' is-detected' : ''}`}
            data-testid="download-card-ios"
          >
            <div className="crew-plat-top">
              <span className="crew-plat-glyph">
                <IphoneGlyph />
              </span>
              {platform === 'ios' && <span className="crew-plat-badge">{dl('currentDevice')}</span>}
            </div>
            <h3>iOS</h3>
            <div className="crew-plat-req">{dl('iosReq')}</div>
            <p className="crew-plat-desc">{dl('iosDesc')}</p>
            {ios?.download_url ? (
              <a className="crew-plat-btn" href={ios.download_url} target="_blank" rel="noreferrer">
                {dl('iosAction')}
              </a>
            ) : (
              <span className="crew-plat-btn is-soon" aria-disabled="true">
                {dl('iosComingSoon')}
              </span>
            )}
          </article>
        </div>

        <div className="crew-headless-bar">
          <span>{dl('headlessPrompt')}</span>
          <button
            type="button"
            className="crew-headless-toggle"
            aria-expanded={headlessOpen}
            aria-controls="crew-headless-panel"
            onClick={() => setHeadlessOpen(prev => !prev)}
          >
            <span>{dl('headlessToggle')}</span>
            <ChevronDown />
          </button>
        </div>

        {headlessOpen && (
          <div className="crew-headless-panel" id="crew-headless-panel">
            <p>{dl('headlessBody')}</p>
            {unixCommand ? (
              <div className="crew-headless-cmd-row">
                <pre>
                  <code>{unixCommand}</code>
                </pre>
                <button type="button" className="crew-headless-copy" onClick={() => void copyCommand()}>
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  <span>{copied ? t('nodeUpdate.copied') : t('computers.copyCommand')}</span>
                </button>
              </div>
            ) : (
              <p>{t('computers.noInstaller')}</p>
            )}
            {materials?.windows_x64?.download_url && (
              <div className="crew-headless-win-note">
                <span>{dl('headlessWindowsPrefix')} </span>
                <a href={materials.windows_x64.download_url} target="_blank" rel="noreferrer">
                  {dl('headlessWindowsLink')}
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
