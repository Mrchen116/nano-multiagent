import { chromium } from "playwright";
import { existsSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const IM_URL = process.env.IM_URL || "http://127.0.0.1:53722";
const USERNAME = "nano";
const PASSWORD = "nano1234";
const EVIDENCE_DIR = __dirname;

if (!existsSync(EVIDENCE_DIR)) mkdirSync(EVIDENCE_DIR, { recursive: true });

async function getToken() {
  const resp = await fetch(`${IM_URL}/im/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  });
  const data = await resp.json();
  return data.access_token;
}

async function getConfig(token, agentId) {
  const resp = await fetch(`${IM_URL}/im/v1/agents/${agentId}/config?source=live`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return resp.json();
}

async function updateConfig(token, agentId, patch) {
  const resp = await fetch(`${IM_URL}/im/v1/agents/${agentId}/config`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ ...patch, profile_version: patch.profile_version }),
  });
  if (!resp.ok) throw new Error(`updateConfig failed: ${resp.status} ${await resp.text()}`);
  return resp.json();
}

async function login(page) {
  await page.goto(`${IM_URL}/login`);
  await page.fill('input[name="username"], #username', USERNAME);
  await page.fill('input[name="password"], #password', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(chat|settings)/, { timeout: 10000 });
}

async function screenshotElement(page, name, selector) {
  const el = await page.locator(selector).first();
  await el.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(EVIDENCE_DIR, name), fullPage: false });
}

async function captureState(page, token, agentId, fileName, selector = 'data-testid=pill-selector-tools') {
  await page.goto(`${IM_URL}/settings/agents/${agentId}`);
  await page.waitForSelector('[data-testid="agent-detail"]', { timeout: 15000 });
  await page.waitForSelector(`[data-testid="pill-selector-tools"] [data-pill-name]`, { timeout: 15000 });
  // Give React Query a moment to settle.
  await page.waitForTimeout(300);
  await screenshotElement(page, fileName, selector);
}

async function main() {
  const token = await getToken();

  // 1. Non-empty allowlist shows stored values.
  const cfg = await getConfig(token, "default-agent");
  await updateConfig(token, "default-agent", { ...cfg, tool_allowlist: ["read", "write"] });

  const browser = await chromium.launch({ headless: true });

  // Desktop: non-empty.
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await login(page);
    await captureState(page, token, "default-agent", "01-non-empty-desktop.png");
    await context.close();
  }

  // Mobile: non-empty.
  {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
    const page = await context.newPage();
    await login(page);
    await captureState(page, token, "default-agent", "02-non-empty-mobile.png");
    await context.close();
  }

  // 2. Empty allowlist renders all pills unselected.
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await login(page);
    await captureState(page, token, "plato", "03-empty-desktop.png");
    await context.close();
  }

  // 3. Clear, save, refresh keeps all unselected.
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await login(page);
    await page.goto(`${IM_URL}/settings/agents/default-agent`);
    await page.waitForSelector('[data-testid="agent-detail"]', { timeout: 15000 });
    await page.waitForSelector(`[data-testid="pill-selector-tools"] [data-pill-name]`, { timeout: 15000 });
    // Deselect read and write.
    for (const name of ["read", "write"]) {
      const pill = page.locator(`[data-testid="pill-selector-tools"] [data-pill-name="${name}"]`);
      await pill.click();
    }
    await page.click('button[type="submit"]');
    await page.waitForTimeout(800);
    await page.reload();
    await page.waitForSelector('[data-testid="agent-detail"]', { timeout: 15000 });
    await page.waitForSelector(`[data-testid="pill-selector-tools"] [data-pill-name]`, { timeout: 15000 });
    await page.waitForTimeout(300);
    await screenshotElement(page, "04-cleared-refreshed-desktop.png", 'data-testid=pill-selector-tools');
    await context.close();
  }

  // 4. Create page preselection unchanged.
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await login(page);
    await page.goto(`${IM_URL}/settings/agents/new`);
    await page.waitForSelector('[data-testid="agent-create"]', { timeout: 15000 });
    await page.selectOption('#owning-node', 'wt-bugfix-468-M1-98490');
    await page.waitForSelector(`[data-testid="pill-selector-tools"] [data-pill-name]`, { timeout: 15000 });
    await page.waitForTimeout(300);
    await screenshotElement(page, "05-create-preselect-desktop.png", 'data-testid=pill-selector-tools');
    await context.close();
  }

  await browser.close();
  console.log("Browser QA screenshots saved to", EVIDENCE_DIR);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
