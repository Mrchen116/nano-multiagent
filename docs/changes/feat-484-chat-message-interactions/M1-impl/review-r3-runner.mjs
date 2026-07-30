// feat-484 reviewer runner — Round 3 targeted revalidation.
import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const REPO_ROOT = "/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-484";
const UNIT_DIR = path.join(REPO_ROOT, "docs/changes/feat-484-chat-message-interactions");
const EVIDENCE_DIR = path.join(UNIT_DIR, "M1-impl/review-r3-evidence");
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

  const agents = await httpJson(`${IM_URL}/im/v1/agents`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const agent = agents.find((a) => a.node_status === "online" && a.agent_id) || agents[0];
  if (!agent) throw new Error("No agent available");

  const conv = await httpJson(`${IM_URL}/im/v1/conversations`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      title: agent.display_name,
      participants: [{ type: "user", id: userId }, { type: "agent", id: agent.agent_id }]
    })
  });

  const message = await httpJson(`${IM_URL}/im/v1/conversations/${encodeURIComponent(conv.id)}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ sender_user_id: userId, content: PROMPT_RICH })
  });

  return { token, conversation: conv, message };
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

async function main() {
  const { token, conversation, message } = await loginAndCreateConversation();
  const conversationUrl = `${IM_URL}/chat/${conversation.id}`;
  log("Conversation URL:", conversationUrl);

  log("Waiting for agent reply...");
  const reply = await waitForAgentReply(token, conversation.id, message.id);
  log("Got reply, id:", reply.id, "length:", reply.content?.length || 0);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"]
  });
  const page = await context.newPage();
  await authenticatePage(page);

  await page.goto(conversationUrl);
  await page.waitForSelector(".chat-message-body", { timeout: 20000 });
  await page.waitForTimeout(600);

  const bubble = page.locator(".chat-bubble--agent").last();
  await bubble.scrollIntoViewIfNeeded();
  await screenshot(page, "r3-desktop-reading.png");

  // Whole-message copy.
  await bubble.hover();
  const copyBtn = bubble.locator(`[data-testid^='message-copy-']`).first();
  await copyBtn.click();
  await page.waitForTimeout(600);
  await screenshot(page, "r3-desktop-copy-success.png");

  const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
  await writeText("r3-desktop-clipboard-message.txt", clipboardText);
  log("clipboard length:", clipboardText.length);

  // Verify clipboard content.
  const checks = {
    hasFirstCodeBlock: clipboardText.includes('def main()') || clipboardText.includes('print("'),
    hasSecondCodeBlock: clipboardText.includes('echo "'),
    noCopyButtonGlyph: !clipboardText.includes("⎘"),
    listContinuousNoBlankBetweenItems: !clipboardText.match(/- .*\n\n- /),
    namedLinkInline: clipboardText.includes("文档 (https://example.com/docs)"),
    bareUrlSingle: clipboardText.includes("https://example.com") && !clipboardText.match(/https:\/\/example\.com\s*\n\s*https:\/\/example\.com/),
    sameOriginNoAppend: clipboardText.includes("/chat") && !clipboardText.includes("/chat (http")
  };
  log("checks:", checks);

  // Independent code copy still works.
  const codeBlocks = page.locator(".im-code-block");
  const firstCode = codeBlocks.first();
  await firstCode.hover();
  await page.waitForTimeout(200);
  const codeCopy = firstCode.locator(".im-code-copy").first();
  await codeCopy.click();
  await page.waitForTimeout(500);
  const codeClipboard = await page.evaluate(() => navigator.clipboard.readText());
  await writeText("r3-desktop-clipboard-code.txt", codeClipboard);
  log("code clipboard length:", codeClipboard.length);

  await context.close();
  await browser.close();

  log("Evidence saved to", EVIDENCE_DIR);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
