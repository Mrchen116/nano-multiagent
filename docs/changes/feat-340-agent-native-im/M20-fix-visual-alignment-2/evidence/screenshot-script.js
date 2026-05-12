const { chromium } = require('playwright');
const path = require('path');

const OUT = '/Users/czj/Repos/nano-multiagent/docs/changes/feat-340-agent-native-im/M20-fix-visual-alignment-2/evidence/actual-r12bis-fixed';

const shots = [
  { name: 'chat-1440', url: 'http://127.0.0.1:8011/chat', viewport: { width: 1440, height: 900 } },
  { name: 'chat-375', url: 'http://127.0.0.1:8011/chat', viewport: { width: 375, height: 812 } },
  { name: 'agents-detail-1440', url: 'http://127.0.0.1:8011/settings/agents/agent-core-1', viewport: { width: 1440, height: 900 } },
  { name: 'agents-375', url: 'http://127.0.0.1:8011/settings/agents', viewport: { width: 375, height: 812 } },
  { name: 'nodes-1440', url: 'http://127.0.0.1:8011/settings/nodes', viewport: { width: 1440, height: 900 } },
  { name: 'nodes-375', url: 'http://127.0.0.1:8011/settings/nodes', viewport: { width: 375, height: 812 } },
  { name: 'account-1440', url: 'http://127.0.0.1:8011/settings/account', viewport: { width: 1440, height: 900 } },
  { name: 'account-375', url: 'http://127.0.0.1:8011/settings/account', viewport: { width: 375, height: 812 } },
  { name: 'me-375', url: 'http://127.0.0.1:8011/me', viewport: { width: 375, height: 812 } },
];

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // login first
  await page.goto('http://127.0.0.1:8011/login');
  await page.fill('input[name="username"]', 'r12review');
  await page.fill('input[name="password"]', 'password123');
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(chat|me)$/, { timeout: 10000 });

  for (const s of shots) {
    await page.setViewportSize(s.viewport);
    await page.goto(s.url);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(OUT, `${s.name}.png`), fullPage: false });
    console.log('saved', s.name);
  }

  await browser.close();
})();
