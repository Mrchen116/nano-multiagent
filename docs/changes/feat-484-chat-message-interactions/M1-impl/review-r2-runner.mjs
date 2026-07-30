// feat-484 reviewer runner — Round 2 targeted revalidation.
import { chromium, webkit } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const REPO_ROOT = "/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-484";
const UNIT_DIR = path.join(REPO_ROOT, "docs/changes/feat-484-chat-message-interactions");
const EVIDENCE_DIR = path.join(UNIT_DIR, "M1-impl/review-r2-evidence");
const IM_URL = process.env.IM_URL || "http://127.0.0.1:8011";

const USERNAME = "nano";
const PASSWORD = "nano1234";

const PROMPT_RICH = [
  "请用中文回复一段演示消息，必须包含：",
  "1) 两段以上正文；2) 一个无序列表（至少两项，其中一项含嵌套）；",
  "3) 一个具名外链 [文档](https://example.com/docs)；",
  "4) 一个裸 URL https://example.com；",
  "5) 一个相对链接 /chat；",
  "6) 两个 fenced 代码块，第一个代码块内部包含空行和缩进。",
  "只输出这些结构化内容，不要额外寒暄。"
].join("\n");

await fs.mkdir(EVIDENCE_DIR, { recursive: true });

function log(...args) {
  console.log(new Date().toISOString(), ...args);
}

async function httpJson(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`${opts.method || "GET"} ${url} -> ${res.status}`);
  return res.json();
}

async function loginAndCreateConversation() {
  log("Logging in...");
  const login = await httpJson(`${IM_URL}/im/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD })
  });
  const token = login.access_token;
  const userId = login.user.id;

  log("Listing agents...");
  const agents = await httpJson(`${IM_URL}/im/v1/agents`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const agent = agents.find((a) => a.node_status === "online" && a.agent_id) || agents[0];
  if (!agent) throw new Error("No agent available");

  log("Creating direct conversation...");
  const conv = await httpJson(`${IM_URL}/im/v1/conversations`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      title: agent.display_name,
      participants: [{ type: "user", id: userId }, { type: "agent", id: agent.agent_id }]
    })
  });

  log("Sending rich-content prompt...");
  const message = await httpJson(`${IM_URL}/im/v1/conversations/${encodeURIComponent(conv.id)}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ sender_user_id: userId, content: PROMPT_RICH })
  });

  return { token, userId, conversation: conv, message };
}

async function waitForAgentReply(token, conversationId, userMessageId, timeoutMs = 120000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const data = await httpJson(
      `${IM_URL}/im/v1/conversations/${encodeURIComponent(conversationId)}/messages?limit=200`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const items = Array.isArray(data) ? data : (data.items || []);
    const messages = items.map((it) => it.message || it);
    const agentMsg = messages.find((m) =>
      m.sender_type === "agent" && m.delivery_status === "completed" && m.id !== userMessageId
    );
    if (agentMsg) return agentMsg;
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error("Timeout waiting for agent reply");
}

async function authenticatePage(page) {
  await page.goto(`${IM_URL}/login`);
  await page.waitForSelector("input", { timeout: 10000 });
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/chat/, { timeout: 15000 });
}

async function screenshot(page, name) {
  const p = path.join(EVIDENCE_DIR, name);
  await page.screenshot({ path: p, fullPage: false });
  log("screenshot", p);
  return p;
}

async function writeText(name, text) {
  const p = path.join(EVIDENCE_DIR, name);
  await fs.writeFile(p, text, "utf-8");
  log("wrote", p);
  return p;
}

async function openProductChat(page, conversationUrl) {
  await page.goto(conversationUrl);
  await page.waitForSelector(".chat-message-body", { timeout: 20000 });
  await page.waitForTimeout(600);
}

async function runDesktop(browser, conversationUrl) {
  log("=== Desktop 1440x900 ===");
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"]
  });
  const page = await context.newPage();
  await authenticatePage(page);
  await openProductChat(page, conversationUrl);

  const bubble = page.locator(".chat-bubble--agent").last();
  await bubble.scrollIntoViewIfNeeded();

  // Reading state.
  await screenshot(page, "r2-desktop-reading.png");

  // Toolbar default keyboard reachability: Tab from composer should reach toolbar without hover.
  await page.keyboard.press("Tab");
  await page.waitForTimeout(300);
  const toolbarFocused = await page.evaluate(() =>
    document.activeElement?.closest(".chat-message-toolbar") !== null
  );
  log("toolbar default keyboard reachable:", toolbarFocused);
  await screenshot(page, "r2-desktop-toolbar-tab-focus.png");

  // Whole-message copy and verify clipboard.
  await bubble.hover();
  const copyBtn = bubble.locator(`[data-testid^='message-copy-']`).first();
  await copyBtn.click();
  await page.waitForTimeout(600);
  await screenshot(page, "r2-desktop-copy-success.png");

  const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
  await writeText("r2-desktop-clipboard-message.txt", clipboardText);
  log("clipboard length:", clipboardText.length);

  // Consecutive code copy: first block, then second block.
  const codeBlocks = page.locator(".im-code-block");
  const codeClipboards = [];
  const count = await codeBlocks.count();
  log("code blocks:", count);
  for (let i = 0; i < Math.min(count, 2); i++) {
    const block = codeBlocks.nth(i);
    await block.hover();
    await page.waitForTimeout(200);
    const copy = block.locator(".im-code-copy").first();
    await copy.click();
    await page.waitForTimeout(500);
    const txt = await page.evaluate(() => navigator.clipboard.readText());
    codeClipboards.push(txt);
    log(`code block ${i} length:`, txt.length);
  }
  await screenshot(page, "r2-desktop-code-copy-second.png");
  for (let i = 0; i < codeClipboards.length; i++) {
    await writeText(`r2-desktop-clipboard-code-${i}.txt`, codeClipboards[i]);
  }

  // Context menu open, Escape close, focus back to trigger.
  await bubble.hover();
  const bodyBox = await bubble.locator(".chat-message-body").boundingBox();
  if (bodyBox) {
    await page.mouse.click(bodyBox.x + 20, bodyBox.y + 20, { button: "right" });
    await page.waitForTimeout(400);
    await screenshot(page, "r2-desktop-contextmenu.png");
    let menuOpen = await page.locator("[role='menu']").isVisible().catch(() => false);
    log("context menu open:", menuOpen);

    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    menuOpen = await page.locator("[role='menu']").isVisible().catch(() => false);
    log("context menu after Escape:", menuOpen);
    const activeAfterEscape = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? `${el.tagName} ${el.getAttribute("data-testid") || el.className || el.textContent?.slice(0, 30)}` : "null";
    });
    log("activeElement after menu Escape:", activeAfterEscape);
    await screenshot(page, "r2-desktop-menu-escape.png");
  }

  // Context menu outside click close.
  await page.mouse.click(bodyBox.x + 20, bodyBox.y + 20, { button: "right" });
  await page.waitForTimeout(400);
  await page.mouse.click(10, 10, { button: "left" });
  await page.waitForTimeout(300);
  const menuOpenOutside = await page.locator("[role='menu']").isVisible().catch(() => false);
  log("context menu after outside click:", menuOpenOutside);
  await screenshot(page, "r2-desktop-menu-outside-click.png");

  // Link classification regression: external has target blank, raw URL no indicator duplication, same-origin no target.
  const extNamed = page.locator("a.im-md-link--external").first();
  const extRaw = page.locator("a[href='https://example.com']").first();
  const sameOrigin = page.locator("a[href='/chat']").first();
  log("named external target:", await extNamed.getAttribute("target"));
  log("raw URL target:", await extRaw.getAttribute("target"));
  log("same-origin target:", await sameOrigin.getAttribute("target"));

  await context.close();
}

async function runHybrid(browser, conversationUrl) {
  log("=== Hybrid 1024x768 ===");
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 }, hasTouch: true });
  const page = await context.newPage();
  await authenticatePage(page);
  await openProductChat(page, conversationUrl);

  const bubble = page.locator(".chat-bubble--agent").last();
  await bubble.scrollIntoViewIfNeeded();
  await bubble.hover();
  await page.waitForTimeout(400);
  await screenshot(page, "r2-hybrid-hover-toolbar.png");

  const more = bubble.locator(`[data-testid^='message-more-']`).first();
  const moreVisible = await more.isVisible().catch(() => false);
  log("hybrid More visible:", moreVisible);
  if (moreVisible) {
    await more.click();
    await page.waitForTimeout(400);
    await screenshot(page, "r2-hybrid-sheet.png");
    await page.keyboard.press("Escape");
    await page.waitForTimeout(200);
  }

  await context.close();
}

async function runMobileWebKit(browser, conversationUrl) {
  log("=== Mobile WebKit 390x844 ===");
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
  });
  const page = await context.newPage();
  await authenticatePage(page);
  await openProductChat(page, conversationUrl);

  const bubble = page.locator(".chat-bubble--agent").last();
  await bubble.scrollIntoViewIfNeeded();
  await screenshot(page, "r2-mobile-reading.png");

  const more = bubble.locator(`[data-testid^='message-more-']`).first();
  await more.tap();
  await page.waitForTimeout(500);
  await screenshot(page, "r2-mobile-sheet.png");
  await page.keyboard.press("Tab");
  await page.waitForTimeout(200);
  const activeAfterTab = await page.evaluate(() => {
    const el = document.activeElement;
    return el ? `${el.tagName} ${el.getAttribute("data-testid") || el.className || el.textContent?.slice(0, 30)}` : "null";
  });
  log("mobile sheet activeElement after Tab:", activeAfterTab);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  await screenshot(page, "r2-mobile-sheet-closed.png");

  await context.close();
}

async function main() {
  const { token, conversation, message } = await loginAndCreateConversation();
  const conversationUrl = `${IM_URL}/chat/${conversation.id}`;
  log("Conversation URL:", conversationUrl);

  log("Waiting for agent reply...");
  const reply = await waitForAgentReply(token, conversation.id, message.id);
  log("Got reply, id:", reply.id, "length:", reply.content?.length || 0);

  const browser = await chromium.launch({ headless: true });
  const webkitBrowser = await webkit.launch({ headless: true });

  await runDesktop(browser, conversationUrl);
  await runHybrid(browser, conversationUrl);
  await runMobileWebKit(webkitBrowser, conversationUrl);

  await browser.close();
  await webkitBrowser.close();

  log("Evidence saved to", EVIDENCE_DIR);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
