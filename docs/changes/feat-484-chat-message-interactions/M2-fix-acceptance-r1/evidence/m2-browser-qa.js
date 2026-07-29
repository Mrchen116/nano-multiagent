/**
 * feat-484-M2 真浏览器验收脚本（一次性证据，不进测试套件）.
 *
 * 覆盖 M2 修复项：
 * - 链接/代码内右键保留原生菜单
 * - context menu Escape / 外部点击关闭
 * - 连续两个 code block copy 按钮工作
 * - resize 时 context menu 关闭
 * - toolbar opacity/pointer-events 默认态仍可达
 *
 * 运行前须先 source <worktree>/.e2e-ports.env.
 */

const { chromium } = require("playwright");

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

async function getLastAgentBubble(page) {
  const bubbles = await page.locator('[data-testid^="message-bubble-"]').all();
  let lastAgentBubble = bubbles[bubbles.length - 1];
  for (const b of bubbles) {
    const cls = await b.getAttribute("class");
    if (cls?.includes("chat-bubble--agent")) {
      lastAgentBubble = b;
    }
  }
  return lastAgentBubble;
}

async function runDesktopChromium() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      console.error("PAGE ERROR:", msg.text());
    }
  });
  page.on("pageerror", (err) => {
    console.error("PAGE EXCEPTION:", err.message);
  });

  await login(page);
  await openAgentChat(page);
  const conversationUrl = page.url();

  await sendMessage(
    page,
    "Please reply with a short markdown message that includes:\n" +
      "- A named external link to https://example.com as [Example](https://example.com)\n" +
      "- A bare URL https://example.org\n" +
      "- Two fenced code blocks\n" +
      "Keep it concise."
  );
  await waitForAgentReply(page, 180000);

  // Wait for the agent message body to actually render before taking evidence.
  await page.waitForSelector('.chat-bubble--agent .chat-message-body', { timeout: 10000 });
  await sleep(500);

  const lastAgentBubble = await getLastAgentBubble(page);

  // 1. Default reading state.
  await screenshot(page, "m2-desktop-default");

  // 2. Hover toolbar visible.
  await lastAgentBubble.hover();
  await sleep(300);
  await screenshot(page, "m2-desktop-hover-toolbar");

  // Helper to fire a synthetic right-click contextmenu event.
  async function fireContextMenu(locator) {
    const box = await locator.boundingBox();
    if (!box) throw new Error("locator bounding box not found");
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    await locator.evaluate((el, { cx, cy }) => {
      const event = new MouseEvent("contextmenu", {
        bubbles: true,
        cancelable: true,
        button: 2,
        buttons: 2,
        clientX: cx,
        clientY: cy,
      });
      // @ts-ignore
      event.pointerType = "mouse";
      el.dispatchEvent(event);
    }, { cx: x, cy: y });
  }

  // 3. Right-click on plain body opens IM menu.
  const body = lastAgentBubble.locator(".chat-message-body").first();
  await fireContextMenu(body);
  await page.waitForSelector(".chat-message-menu", { timeout: 5000 });
  await sleep(300);
  await screenshot(page, "m2-desktop-context-menu");

  // 4. Press Escape closes the menu.
  await page.keyboard.press("Escape");
  await sleep(300);
  await screenshot(page, "m2-desktop-menu-escape-closed");

  // 5. Right-click inside link keeps native menu (no IM menu).
  const link = lastAgentBubble.locator('a.im-md-link').first();
  await fireContextMenu(link);
  await sleep(300);
  await screenshot(page, "m2-desktop-link-rightclick-native");
  await page.keyboard.press("Escape");
  await sleep(200);

  // 6. Right-click inside code block keeps native menu.
  const codeBlock = lastAgentBubble.locator('.im-code-block').first();
  await fireContextMenu(codeBlock);
  await sleep(300);
  await screenshot(page, "m2-desktop-code-rightclick-native");
  await page.keyboard.press("Escape");
  await sleep(200);

  // 7. Context menu closes on window resize.
  await fireContextMenu(body);
  await page.waitForSelector(".chat-message-menu", { timeout: 5000 });
  await sleep(300);
  await page.setViewportSize({ width: 1280, height: 800 });
  await sleep(300);
  await screenshot(page, "m2-desktop-menu-resize-closed");
  await page.setViewportSize({ width: 1440, height: 900 });

  // 8. Consecutive code block copy.
  const copyButtons = await lastAgentBubble.locator('button[aria-label="Copy code"]').all();
  if (copyButtons.length >= 2) {
    await copyButtons[0].click();
    await sleep(600);
    await screenshot(page, "m2-desktop-code-copy-first");
    await copyButtons[1].click();
    await sleep(600);
    await screenshot(page, "m2-desktop-code-copy-second");
  }

  await browser.close();
  return conversationUrl;
}

runDesktopChromium()
  .then((url) => {
    console.log("conversation:", url);
    process.exit(0);
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
