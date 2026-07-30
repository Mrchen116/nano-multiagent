/**
 * feat-484-M2 P0-22 真栈验证(一次性证据,不进测试套件)。
 *
 * 验证 reviewer round 1 issue 1 已关闭:
 * - loose list(项间空行)复制后列表项连续,无多余空行
 * - 具名外链(display:inline-flex)复制后内联且带 absolute URL 追加
 * - 裸 URL 不重复追加,同源链接无追加
 *
 * 运行前: source <worktree>/.e2e-ports.env,且前端已 build(IM 托管 dist)。
 */

const { chromium } = require("playwright");
const fs = require("node:fs");

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
  const fields = page.locator(".im-auth-field input");
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
  await page.waitForSelector(".chat-pane", { timeout: 10000 });
}

async function sendMessage(page, text) {
  const composer = page.locator(".chat-pane-composer-input").first();
  await composer.fill(text);
  await composer.press("Enter");
}

async function waitForAgentReply(page, timeoutMs = 180000) {
  await page.waitForFunction(
    () => !document.querySelector('[data-testid^="message-elapsed-"]'),
    null,
    { timeout: timeoutMs }
  );
  await sleep(500);
}

async function getLastAgentBubble(page) {
  const bubbles = await page.locator('[data-testid^="message-bubble-"]').all();
  let lastAgentBubble = bubbles[bubbles.length - 1];
  for (const b of bubbles) {
    const cls = await b.getAttribute("class");
    if (cls?.includes("chat-bubble--agent")) lastAgentBubble = b;
  }
  return lastAgentBubble;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await context.newPage();
  page.on("pageerror", (err) => console.error("PAGE EXCEPTION:", err.message));

  await login(page);
  await openAgentChat(page);

  await sendMessage(
    page,
    [
      "请用中文回复一段演示消息,必须包含:",
      "1) 两段正文;2) 一个无序列表至少三项,列表项之间用空行分隔,其中一项含嵌套子列表;",
      "3) 具名外链 [文档](https://example.com/docs);4) 裸 URL https://example.com;5) 相对链接 /chat;",
      "6) 一个 fenced 代码块。只输出结构化内容,不要寒暄。",
    ].join("\n")
  );
  await waitForAgentReply(page);
  await page.waitForSelector(".chat-bubble--agent .chat-message-body", { timeout: 10000 });
  await sleep(500);

  const bubble = await getLastAgentBubble(page);
  await bubble.hover();
  await page.screenshot({ path: `${EVIDENCE_DIR}/m2-p022-hover-toolbar.png` });

  const copyBtn = bubble.locator("[data-testid^='message-copy-']").first();
  await copyBtn.click();
  await sleep(600);
  await page.screenshot({ path: `${EVIDENCE_DIR}/m2-p022-copy-result.png` });

  const clipboard = await page.evaluate(() => navigator.clipboard.readText());
  fs.writeFileSync(`${EVIDENCE_DIR}/m2-p022-clipboard-message.txt`, clipboard);
  console.log("=== clipboard ===");
  console.log(clipboard);
  console.log("=== checks ===");

  const failures = [];
  if (/^- [^\n]*\n\n- /m.test(clipboard)) {
    failures.push("顶级列表项之间存在多余空行");
  }
  if (/^ +- [^\n]*\n\n +- /m.test(clipboard)) {
    failures.push("嵌套列表项之间存在多余空行");
  }
  if (!/文档 \(https:\/\/example\.com\/docs\)/.test(clipboard)) {
    failures.push("具名外链未内联输出 '文档 (https://example.com/docs)'");
  }
  const bareUrlCount = (clipboard.match(/https:\/\/example\.com(?!\/docs)/g) || []).length;
  if (bareUrlCount !== 1) {
    failures.push(`裸 URL 出现 ${bareUrlCount} 次(期望恰好 1 次,不重复追加)`);
  }
  if (/\/chat \(http/.test(clipboard)) {
    failures.push("同源相对链接被错误追加 absolute URL");
  }

  if (failures.length) {
    console.error("P0-22 FAIL:");
    for (const f of failures) console.error(" -", f);
    process.exitCode = 1;
  } else {
    console.log("P0-22 PASS: 列表连续 / 具名外链内联 / 裸 URL 单次 / 同源无追加");
  }

  await browser.close();
})();
