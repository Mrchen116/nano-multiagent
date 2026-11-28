import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { setLanguage } from '../../i18n';
import { useAuthStore } from '../auth/auth-store';
import { PublicHomePage } from './public-home-page';
import { detectVisitorPlatform } from './public-download-section';
import { UserMenu } from '../../app/shell/user-menu';

const SAMPLE_MATERIALS = {
  available: true,
  origin: 'https://crewden.example',
  command: "curl -fsSL 'https://crewden.example/install.sh' -o /tmp/nano-install.sh && bash /tmp/nano-install.sh",
  script_url: 'https://crewden.example/install.sh',
  windows_x64: {
    download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v0.2.0/Crewden-Setup-x64.exe',
    connect_url: 'crewden://connect?origin=https%3A%2F%2Fcrewden.example',
  },
  desktop_darwin_arm64: {
    download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v0.2.0/Crewden-Desktop-arm64.dmg',
    connect_url: 'crewden-desktop://connect?origin=https%3A%2F%2Fcrewden.example',
    version: '0.2.0',
  },
  desktop_win32_x64: {
    download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v0.2.0/Crewden-Desktop-Setup-x64.exe',
    connect_url: 'crewden-desktop://connect?origin=https%3A%2F%2Fcrewden.example',
    version: '0.2.0',
  },
  ios: null as { download_url: string } | null,
};

function stubNavigator(ua: string, platform: string, maxTouchPoints = 0) {
  vi.stubGlobal('navigator', {
    ...window.navigator,
    userAgent: ua,
    platform,
    maxTouchPoints,
    clipboard: { writeText: vi.fn(async () => {}) },
  });
}

function injectPublicInstall(payload: unknown) {
  document.getElementById('nano-public-install')?.remove();
  const script = document.createElement('script');
  script.id = 'nano-public-install';
  script.type = 'application/json';
  script.textContent = JSON.stringify(payload);
  document.body.appendChild(script);
}

describe('PublicHomePage multi-platform client download entry', () => {
  beforeEach(() => {
    setLanguage('zh');
    document.getElementById('nano-public-install')?.remove();
    useAuthStore.setState({ user: null, accessToken: null, hydrated: true, hydrationError: false });
  });

  afterEach(() => {
    document.getElementById('nano-public-install')?.remove();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('detects macOS, Windows, iPhone, iPadOS desktop-mode, and Linux accurately', () => {
    expect(detectVisitorPlatform({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', platform: 'MacIntel', maxTouchPoints: 0 })).toBe('macos');
    expect(detectVisitorPlatform({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', platform: 'Win32', maxTouchPoints: 0 })).toBe('windows');
    expect(detectVisitorPlatform({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)', platform: 'iPhone', maxTouchPoints: 5 })).toBe('ios');
    expect(detectVisitorPlatform({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', platform: 'MacIntel', maxTouchPoints: 5 })).toBe('ios');
    expect(detectVisitorPlatform({ userAgent: 'Mozilla/5.0 (X11; Linux x86_64)', platform: 'Linux x86_64', maxTouchPoints: 0 })).toBe('other');
  });

  it.each([
    [undefined, '未经 Apple 公证'],
    ['unnotarized', '未经 Apple 公证'],
    ['developer-id-notarized', '已通过 Apple 公证'],
    ['unsigned-test', '测试包 · 未经 Apple 公证'],
  ] as const)('shows the Mac distribution status for %s inside the installation guide', async (mode, label) => {
    stubNavigator('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 'MacIntel');
    injectPublicInstall({ ...SAMPLE_MATERIALS, desktop_darwin_arm64: { ...SAMPLE_MATERIALS.desktop_darwin_arm64, macos_distribution: mode } });

    render(
      <MemoryRouter initialEntries={['/about']}>
        <Routes>
          <Route path="/about" element={<PublicHomePage />} />
        </Routes>
      </MemoryRouter>,
    );

    const heroMacLink = within(screen.getByTestId('hero-smart-download')).getByRole('link', { name: '下载 Mac 版' });
    expect(heroMacLink).toHaveAttribute('href', SAMPLE_MATERIALS.desktop_darwin_arm64.download_url);
    expect(screen.getByRole('link', { name: '网页版直接使用' })).toHaveAttribute('href', '/register');

    const macCard = screen.getByTestId('download-card-macos');
    expect(screen.queryByText(label)).not.toBeInTheDocument();
    for (const entry of [screen.getByTestId('hero-smart-download'), macCard]) {
      await userEvent.click(within(entry).getByRole('button', { name: '安装说明' }));
      const guide = screen.getByRole('dialog', { name: 'Mac 安装说明' });
      expect(within(guide).getByText(label)).toBeVisible();
      expect(Boolean(within(guide).queryByText(/仍要打开/))).toBe(mode !== 'developer-id-notarized');
      await userEvent.keyboard('{Escape}');
    }
    expect(within(macCard).getByText('当前设备')).toBeInTheDocument();
    expect(within(macCard).getByText(/macOS 15\.0\+ · Apple Silicon/)).toBeInTheDocument();
    expect(within(macCard).getByRole('link', { name: '下载 Mac 版' })).toHaveAttribute(
      'href',
      SAMPLE_MATERIALS.desktop_darwin_arm64.download_url,
    );

    const winCard = screen.getByTestId('download-card-windows');
    expect(within(winCard).getByRole('link', { name: '下载 Windows 版' })).toHaveAttribute(
      'href',
      SAMPLE_MATERIALS.desktop_win32_x64.download_url,
    );

    const iosCard = screen.getByTestId('download-card-ios');
    expect(within(iosCard).getByText('即将上线')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /查看轻量后台节点安装方式/ }));
    expect(screen.getByText(/curl -fsSL/)).toBeInTheDocument();
  });

  it('recommends Windows Desktop in Hero when visited from Windows', async () => {
    stubNavigator('Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Win32');
    injectPublicInstall(SAMPLE_MATERIALS);

    render(
      <MemoryRouter initialEntries={['/about']}>
        <Routes>
          <Route path="/about" element={<PublicHomePage />} />
        </Routes>
      </MemoryRouter>,
    );

    const heroWinLink = await screen.findByRole('link', { name: '下载 Windows 客户端' });
    expect(heroWinLink).toHaveAttribute('href', SAMPLE_MATERIALS.desktop_win32_x64.download_url);
    expect(within(screen.getByTestId('download-card-windows')).getByText('当前设备')).toBeInTheDocument();
  });

  it('keeps honest coming-soon state on iPhone until IM_IOS_DOWNLOAD_URL is configured, then activates store links', async () => {
    stubNavigator('Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X)', 'iPhone', 5);
    injectPublicInstall(SAMPLE_MATERIALS);

    const { unmount } = render(
      <MemoryRouter initialEntries={['/about']}>
        <Routes>
          <Route path="/about" element={<PublicHomePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/iOS 客户端即将上线/)).toBeInTheDocument();
    expect(within(screen.getByTestId('download-card-ios')).getByText('当前设备')).toBeInTheDocument();
    expect(within(screen.getByTestId('download-card-ios')).getByText('即将上线')).toBeInTheDocument();
    unmount();

    const iosUrl = 'https://testflight.apple.com/join/crewden';
    injectPublicInstall({ ...SAMPLE_MATERIALS, ios: { download_url: iosUrl } });

    render(
      <MemoryRouter initialEntries={['/about']}>
        <Routes>
          <Route path="/about" element={<PublicHomePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: '获取 iOS 客户端' })).toHaveAttribute('href', iosUrl);
    expect(within(screen.getByTestId('download-card-ios')).getByRole('link', { name: '获取 iOS 版' })).toHaveAttribute(
      'href',
      iosUrl,
    );
  });

  it('exposes a Download apps entry inside the authenticated UserMenu', async () => {
    useAuthStore.setState({
      hydrated: true,
      hydrationError: false,
      accessToken: 'tok',
      user: {
        id: 'u-1',
        username: 'lin',
        display_name: '林岚',
        owner_id: 'u-1',
        locale: 'zh',
        default_entry_node_id: null,
        membership_status: 'active',
        is_company_admin: false,
        owned_node_ids: [],
        created_at: '',
      },
    });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/chat']}>
          <UserMenu />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await userEvent.click(screen.getByRole('button', { name: '林岚' }));
    expect(screen.getByRole('menuitem', { name: /下载客户端/ })).toHaveAttribute('href', '/about#download');
  });
});
