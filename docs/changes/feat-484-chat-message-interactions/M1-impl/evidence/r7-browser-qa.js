/**
 * feat-484-M1 R7 真浏览器验收脚本（一次性证据，不进测试套件）.
 *
 * 运行前须先 source <worktree>/.e2e-ports.env 以拿到 IM_URL.
 */

const { chromium, webkit } = require("playwright");

const IM_URL = process.env.IM_URL || "http://127.0.0.1:8011";
const USERNAME = "nano";
const PASSWORD = "nano1234";
const AGENT_ID = process.env.AGENT_ID || "default-agent";
const EVIDENCE_DIR = process.env.EVIDENCE_DIR || ".";

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function login(page) {
  await page.goto(`${IM_URL}/login`);
  const fields = page.locator('.im-auth-field input');
  await fields.nth(0).fill(USERNAME);
  await fields.nth(1).fill(PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/chat/, { timeout: 10000 });
}

async function openAgentChat(page) {
  await page.goto(`${IM_URL}/settings/agents/${AGENT_ID}`);
  await page.waitForSelector('button:has-text("Open chat")', { timeout: 10000 });
  await page.click('button:has-text("Open chat")');
  await page.waitForURL(/\/chat\//, { timeout: 10000 });
  await page.waitForSelector('.chat-pane', { timeout: 10000 });
}

async function sendMessage(page, text) {
  const composer = page.locator('.chat-pane-composer-input').first();
  await composer.fill(text);
  await composer.press("Enter");
}

async function waitForAgentReply(page, timeoutMs = 120000) {
  const composer = page.locator('.chat-pane-composer-input').first();
  await composer.waitFor({ timeout: timeoutMs });
  await page.waitForFunction(
    () => !document.querySelector('[data-testid^="message-elapsed-"]'),
    null,
    { timeout: timeoutMs }
  );
  await sleep(500);
}

async function screenshot(page, name) {
  const path = `${EVIDENCE_DIR}/${name}.png`;
  await page.screenshot({ path, fullPage: false });
  console.log(`saved ${path}`);
  return path;
}

async function runDesktopChromium() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await login(page);
  await openAgentChat(page);
  const conversationUrl = page.url();
  await sendMessage(
    page,
    "Please reply with a short markdown message that includes:\n" +
      "- A paragraph\n" +
      "- A bullet list with one nested item\n" +
      "- A named external link to https://example.com as [Example](https://example.com)\n" +
      "- A bare URL https://example.org\n" +
      "- Two fenced code blocks\n" +
      "Keep it concise."
  );
  await waitForAgentReply(page, 180000);

  await screenshot(page, "r7-desktop-default");

  const bubbles = await page.locator('[data-testid^="message-bubble-"]').all();
  let lastAgentBubble = bubbles[bubbles.length - 1];
  for (const b of bubbles) {
    const cls = await b.getAttribute("class");
    if (cls?.includes("chat-bubble--agent")) {
      lastAgentBubble = b;
    }
  }

  await lastAgentBubble.hover();
  await sleep(300);
  await screenshot(page, "r7-desktop-hover-toolbar");

  const body = lastAgentBubble.locator(".chat-message-body").first();
  await body.click({ button: "right" });
  await sleep(300);
  await screenshot(page, "r7-desktop-context-menu");

  await page.click('[data-testid^="message-copy-"]:visible');
  await sleep(600);
  await screenshot(page, "r7-desktop-copy-success");
  // Dismiss the context menu by clicking a blank area of the pane.
  await page.click('.chat-pane-messages, .chat-pane', { position: { x: 20, y: 20 } });
  await sleep(200);

  const externalLink = page.locator('a.im-md-link--external').first();
  if (await externalLink.count() > 0) {
    await externalLink.hover();
    await sleep(300);
    await screenshot(page, "r7-desktop-external-link");
  }

  const codeBlock = page.locator('.im-code-block').first();
  if (await codeBlock.count() > 0) {
    await codeBlock.hover();
    await sleep(300);
    await screenshot(page, "r7-desktop-code-block");
  }

  await browser.close();
  return conversationUrl;
}

async function runHybridChromium(conversationUrl) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, hasTouch: true });
  const page = await context.newPage();

  await login(page);
  await page.goto(conversationUrl);
  await page.waitForSelector('.chat-message-body', { timeout: 10000 });
  await screenshot(page, "r7-hybrid-toolbar-more");

  const more = page.locator('[data-testid^="message-more-"]').last();
  if (await more.count() > 0) {
    await more.click();
    await sleep(300);
    await screenshot(page, "r7-hybrid-action-sheet");
    await page.keyboard.press("Escape");
    await sleep(300);
  }

  await browser.close();
}

async function runMobileWebKit(conversationUrl) {
  const browser = await webkit.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();

  await login(page);
  await page.goto(conversationUrl);
  await page.waitForSelector('.chat-message-body', { timeout: 10000 });

  await screenshot(page, "r7-mobile-webkit-default");

  const body = page.locator('.chat-message-body').last();
  await body.tap();
  await sleep(300);
  await screenshot(page, "r7-mobile-tap");

  const more = page.locator('[data-testid^="message-more-"]').last();
  if (await more.count() > 0) {
    await more.click();
    await sleep(300);
    await screenshot(page, "r7-mobile-action-sheet");
    await page.keyboard.press("Escape");
  }

  await browser.close();
}

(async () => {
  console.log("IM_URL:", IM_URL);
  try {
    const conversationUrl = await runDesktopChromium();
    console.log("conversationUrl:", conversationUrl);
    await runHybridChromium(conversationUrl);
    await runMobileWebKit(conversationUrl);
    console.log("R7 browser QA completed");
  } catch (err) {
    console.error("R7 browser QA failed:", err);
    process.exit(1);
  }
})();
