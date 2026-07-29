// feat-484 reviewer runner — Round 1 product acceptance evidence capture.
// This is a review artifact, not production source. It drives real browsers
// against the isolated worktree IM stack and the unit prototype.
import { chromium, webkit } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const REPO_ROOT = "/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-484";
const UNIT_DIR = path.join(REPO_ROOT, "docs/changes/feat-484-chat-message-interactions");
const EVIDENCE_DIR = path.join(UNIT_DIR, "M1-impl/review-r1-evidence");
const IM_URL = process.env.IM_URL || "http://127.0.0.1:8011";
const PROTOTYPE_URL = "file://" + path.join(UNIT_DIR, "prototype.html");

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
  log("Using agent", agent.agent_id, agent.display_name);

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

  return { token, userId, agent, conversation: conv, message };
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

async function writeText(name, text) {
  const p = path.join(EVIDENCE_DIR, name);
  await fs.writeFile(p, text, "utf-8");
  log("wrote", p);
  return p;
}

async function screenshot(page, name) {
  const p = path.join(EVIDENCE_DIR, name);
  await page.screenshot({ path: p, fullPage: false });
  log("screenshot", p);
  return p;
}

async function openProductChat(page, conversationUrl) {
  await page.goto(conversationUrl);
  await page.waitForSelector(".chat-message-body", { timeout: 20000 });
  // Let CSS transitions settle.
  await page.waitForTimeout(600);
}

async function capturePrototype(browser, viewportName, width, height, branchState, stateName, fileName) {
  const context = await browser.newContext({ viewport: { width, height } });
  const page = await context.newPage();
  await page.goto(PROTOTYPE_URL);
  await page.waitForSelector("[data-viewport='desktop']", { timeout: 10000 });
  await page.click(`[data-viewport='${viewportName}']`);
  await page.click(`[data-branch-state='${branchState}']`);
  if (stateName !== "default") {
    await page.click(`[data-state='${stateName}']`);
  }
  await page.waitForTimeout(400);
  const p = await screenshot(page, `proto-${fileName}`);
  await context.close();
  return p;
}

async function runDesktop(browser, conversationUrl, agentReply) {
  log("=== Desktop 1440x900 ===");
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"]
  });
  const page = await context.newPage();

  await authenticatePage(page);
  // Wait for agent list / sidebar to render, then open conversation.
  await page.waitForSelector(".chat-sidebar", { timeout: 10000 });
  await openProductChat(page, conversationUrl);

  const agentBubbles = page.locator(".chat-bubble--agent");
  const count = await agentBubbles.count();
  if (count === 0) throw new Error("No agent bubble found");
  const bubble = agentBubbles.last();
  await bubble.scrollIntoViewIfNeeded();

  // Reading state.
  await screenshot(page, "desktop-reading.png");

  // Hover toolbar.
  await bubble.hover();
  await page.waitForTimeout(400);
  await screenshot(page, "desktop-hover-toolbar.png");

  // Focus toolbar via Tab (keyboard).
  await page.keyboard.press("Tab");
  await page.waitForTimeout(300);
  await screenshot(page, "desktop-focus-toolbar.png");

  // Right-click on plain body area -> IM menu.
  const bodyBox = await bubble.locator(".chat-message-body").boundingBox();
  if (bodyBox) {
    await page.mouse.click(bodyBox.x + bodyBox.width * 0.3, bodyBox.y + bodyBox.height * 0.3, { button: "right" });
    await page.waitForTimeout(400);
    await screenshot(page, "desktop-contextmenu.png");
    await page.keyboard.press("Escape");
    await page.waitForTimeout(200);
  }

  // Local selection inside bubble then right-click -> native menu ownership check.
  const body = bubble.locator(".chat-message-body").first();
  await body.click();
  await page.evaluate(() => {
    const bubbleBody = document.querySelector(".chat-bubble--agent:last-of-type .chat-message-body");
    if (!bubbleBody) return;
    const selection = window.getSelection();
    selection.selectAllChildren(bubbleBody);
  });
  await page.waitForTimeout(200);
  await screenshot(page, "desktop-selection.png");

  // Right-click inside selection and record whether IM prevented native menu.
  const selBox = await body.boundingBox();
  if (selBox) {
    await page.evaluate(() => {
      window.__contextMenuPrevented = null;
      document.addEventListener("contextmenu", (e) => {
        window.__contextMenuPrevented = e.defaultPrevented;
      }, { once: true });
    });
    await page.mouse.click(selBox.x + 12, selBox.y + 12, { button: "right" });
    await page.waitForTimeout(250);
    const prevented = await page.evaluate(() => window.__contextMenuPrevented);
    log("contextmenu defaultPrevented (selection):", prevented);
  }

  // Click "Copy message" from toolbar and capture snackbar.
  await bubble.hover();
  const copyBtn = bubble.locator(`[data-testid^='message-copy-']`).first();
  await copyBtn.click();
  await page.waitForTimeout(600);
  await screenshot(page, "desktop-copy-result.png");
  const notice = page.locator(".chat-copy-notice");
  const noticeText = await notice.isVisible().then(async (v) => v ? notice.textContent() : "");
  log("copy notice text:", noticeText);
  let clipboardText = null;
  try {
    clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    log("clipboard length:", clipboardText?.length);
    if (clipboardText != null) await writeText("desktop-clipboard-message.txt", clipboardText);
  } catch (e) {
    log("clipboard read failed:", e.message);
  }

  // Code copy button.
  const codeBlocks = page.locator(".im-code-block");
  let codeClipboard = null;
  if (await codeBlocks.count() > 0) {
    const firstCode = codeBlocks.first();
    await firstCode.hover();
    await page.waitForTimeout(200);
    await screenshot(page, "desktop-code-hover.png");
    const codeCopy = firstCode.locator(".im-code-copy").first();
    await codeCopy.click();
    await page.waitForTimeout(600);
    await screenshot(page, "desktop-code-copy-result.png");
    try {
      codeClipboard = await page.evaluate(() => navigator.clipboard.readText());
      log("code clipboard length:", codeClipboard?.length);
      if (codeClipboard != null) await writeText("desktop-clipboard-code.txt", codeClipboard);
    } catch (e) {
      log("code clipboard read failed:", e.message);
    }
  }

  // External link hover.
  const extLink = page.locator("a[rel='noopener noreferrer']").first();
  if (await extLink.isVisible().catch(() => false)) {
    await extLink.hover();
    await page.waitForTimeout(300);
    await screenshot(page, "desktop-external-link-hover.png");
    const ariaLabel = await extLink.getAttribute("aria-label");
    log("external link aria-label:", ariaLabel);
  }

  await context.close();
}

async function runHybrid(browser, conversationUrl) {
  log("=== Hybrid 1024x768 ===");
  const context = await browser.newContext({
    viewport: { width: 1024, height: 768 },
    hasTouch: true
  });
  const page = await context.newPage();
  await authenticatePage(page);
  await openProductChat(page, conversationUrl);

  const bubble = page.locator(".chat-bubble--agent").last();
  await bubble.scrollIntoViewIfNeeded();
  await bubble.hover();
  await page.waitForTimeout(400);
  await screenshot(page, "hybrid-hover-toolbar.png");

  // More button should be visible in hybrid.
  const more = bubble.locator(`[data-testid^='message-more-']`).first();
  const moreVisible = await more.isVisible().catch(() => false);
  log("hybrid More visible:", moreVisible);
  if (moreVisible) {
    await more.click();
    await page.waitForTimeout(400);
    await screenshot(page, "hybrid-sheet.png");
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
  await screenshot(page, "mobile-reading.png");

  // More button visibility / style probe.
  const more = bubble.locator(`[data-testid^='message-more-']`).first();
  const moreBox = await more.boundingBox().catch(() => null);
  const moreDisplay = await more.evaluate((el) => window.getComputedStyle(el).display).catch(() => "error");
  log("mobile More display:", moreDisplay, "box:", moreBox ? `${Math.round(moreBox.width)}x${Math.round(moreBox.height)}` : "none");
  if (moreBox) {
    await more.hover();
    await screenshot(page, "mobile-more-hover.png");
  }

  // Long-press on body should yield native selection, not custom menu.
  const body = bubble.locator(".chat-message-body").first();
  const bodyBox = await body.boundingBox();
  if (bodyBox) {
    await page.touchscreen.tap(bodyBox.x + 20, bodyBox.y + 20);
    await page.waitForTimeout(800);
    await page.touchscreen.tap(bodyBox.x + 20, bodyBox.y + 20);
    await page.waitForTimeout(800);
    await screenshot(page, "mobile-body-touch.png");
  }

  // Open More sheet.
  await more.tap();
  await page.waitForTimeout(500);
  await screenshot(page, "mobile-sheet.png");

  // Focus trap: Tab should cycle inside sheet; record activeElement.
  await page.keyboard.press("Tab");
  await page.waitForTimeout(200);
  const activeAfterTab = await page.evaluate(() => {
    const el = document.activeElement;
    return el ? `${el.tagName} ${el.getAttribute("data-testid") || el.className || el.textContent?.slice(0, 30)}` : "null";
  });
  log("mobile sheet activeElement after Tab:", activeAfterTab);
  await screenshot(page, "mobile-sheet-focus.png");

  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const activeAfterClose = await page.evaluate(() => {
    const el = document.activeElement;
    return el ? `${el.tagName} ${el.getAttribute("data-testid") || el.className || el.textContent?.slice(0, 30)}` : "null";
  });
  log("mobile activeElement after close:", activeAfterClose);
  await screenshot(page, "mobile-sheet-closed.png");

  await context.close();
}

async function main() {
  let token, conversationUrl, reply;
  const reuseUrl = process.env.FEAT484_CONVERSATION_URL;
  if (reuseUrl) {
    conversationUrl = reuseUrl;
    log("Reusing conversation:", conversationUrl);
    const loginRes = await httpJson(`${IM_URL}/im/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: USERNAME, password: PASSWORD })
    });
    token = loginRes.access_token;
    const convId = conversationUrl.split("/").pop();
    const msgs = await httpJson(`${IM_URL}/im/v1/conversations/${encodeURIComponent(convId)}/messages?limit=10`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const items = Array.isArray(msgs) ? msgs : (msgs.items || []);
    reply = items.map((it) => it.message || it).find((m) => m.sender_type === "agent" && m.delivery_status === "completed");
    if (!reply) throw new Error("No completed agent reply found in reused conversation");
  } else {
    const setup = await loginAndCreateConversation();
    token = setup.token;
    conversationUrl = `${IM_URL}/chat/${setup.conversation.id}`;
    log("Conversation URL:", conversationUrl);
    log("Waiting for agent reply...");
    reply = await waitForAgentReply(token, setup.conversation.id, setup.message.id);
  }
  log("Got reply, id:", reply.id, "length:", reply.content?.length || 0);

  const browser = await chromium.launch({ headless: true });
  const webkitBrowser = await webkit.launch({ headless: true });

  // Capture prototype references.
  await capturePrototype(browser, "desktop", 1440, 900, "available", "default", "desktop-reading-ref.png");
  await capturePrototype(browser, "desktop", 1440, 900, "available", "actions", "desktop-actions-ref.png");
  await capturePrototype(browser, "desktop", 1440, 900, "available", "menu", "desktop-menu-ref.png");
  await capturePrototype(browser, "mobile", 390, 844, "available", "default", "mobile-reading-ref.png");
  await capturePrototype(browser, "mobile", 390, 844, "available", "menu", "mobile-sheet-ref.png");
  await capturePrototype(browser, "hybrid", 1024, 768, "available", "actions", "hybrid-actions-ref.png");

  // Product journeys.
  await runDesktop(browser, conversationUrl, reply);
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
