// M2 worker 真栈自证: reviewer round 3 issue 3(整条复制折叠 code 内部空行)修复验证。
import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const REPO = "/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-484";
const EVD = path.join(REPO, "docs/changes/feat-484-chat-message-interactions/M2-fix-acceptance-r1/evidence");
const IM_URL = process.env.IM_URL;
const log = (...a) => console.log(new Date().toISOString(), ...a);

const PROMPT = [
  "请用中文回复一段演示消息，必须包含：",
  "1) 两段正文；2) 一个无序列表（至少两项）；",
  "3) 一个具名外链 [文档](https://example.com/docs)；",
  "4) 两个 fenced 代码块，第一个代码块内部必须包含两个连续空行和缩进。",
  "只输出这些结构化内容，不要额外寒暄。"
].join("\n");

async function httpJson(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`${opts.method || "GET"} ${url} -> ${res.status}`);
  return res.json();
}

await fs.mkdir(EVD, { recursive: true });

const login = await httpJson(`${IM_URL}/im/v1/auth/login`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username: "nano", password: "nano1234" })
});
const token = login.access_token;
const userId = login.user.id;
const agents = await httpJson(`${IM_URL}/im/v1/agents`, { headers: { Authorization: `Bearer ${token}` } });
const agent = agents.find((a) => a.node_status === "online") || agents[0];
const conv = await httpJson(`${IM_URL}/im/v1/conversations`, {
  method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  body: JSON.stringify({ title: agent.display_name, participants: [{ type: "user", id: userId }, { type: "agent", id: agent.agent_id }] })
});
const sent = await httpJson(`${IM_URL}/im/v1/conversations/${conv.id}/messages`, {
  method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  body: JSON.stringify({ sender_user_id: userId, content: PROMPT })
});
log("sent, waiting for reply...");
let reply = null;
for (let i = 0; i < 80; i++) {
  const data = await httpJson(`${IM_URL}/im/v1/conversations/${conv.id}/messages?limit=200`, { headers: { Authorization: `Bearer ${token}` } });
  const items = Array.isArray(data) ? data : (data.items || []);
  reply = items.map((it) => it.message || it).find((m) => m.sender_type === "agent" && m.delivery_status === "completed" && m.id !== sent.id);
  if (reply) break;
  await new Promise((r) => setTimeout(r, 1500));
}
if (!reply) throw new Error("timeout waiting for reply");
await fs.writeFile(path.join(EVD, "m2-fix-r3-agent-reply.md"), reply.content, "utf-8");
log("reply saved, length:", reply.content.length);

// Extract fenced code blocks from source markdown
const fenced = [...reply.content.matchAll(/```[^\n]*\n([\s\S]*?)```/g)].map((m) => m[1]);
log("fenced blocks found:", fenced.length, "first block:", JSON.stringify(fenced[0]));

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ["clipboard-read", "clipboard-write"] });
const page = await context.newPage();
await page.goto(`${IM_URL}/login`);
await page.getByLabel("Username").fill("nano");
await page.getByLabel("Password").fill("nano1234");
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(/\/chat/, { timeout: 15000 });
await page.goto(`${IM_URL}/chat/${conv.id}`);
await page.waitForSelector(".chat-message-body", { timeout: 20000 });
await page.waitForTimeout(600);

const bubble = page.locator(".chat-bubble--agent").last();
await bubble.hover();
await bubble.locator("[data-testid^='message-copy-']").first().click();
await page.waitForTimeout(600);
const clip = await page.evaluate(() => navigator.clipboard.readText());
await fs.writeFile(path.join(EVD, "m2-fix-r3-clipboard-whole.txt"), clip, "utf-8");
await page.screenshot({ path: path.join(EVD, "m2-fix-r3-copy-result.png") });

// Strict comparison: every fenced block must appear in clipboard with internal newlines intact
const checks = [];
for (const [i, block] of fenced.entries()) {
  const trimmed = block.replace(/\n+$/, "");
  checks.push([`fenced[${i}] verbatim in clipboard`, clip.includes(trimmed)]);
  const triple = (trimmed.match(/\n\n\n/) || []).length;
  if (triple > 0) checks.push([`fenced[${i}] has ${triple} double-blank segment(s) preserved`, clip.includes(trimmed)]);
}
checks.push(["named link inline", clip.includes("文档 (https://example.com/docs)")]);
checks.push(["no blank between list items", !/- .*\n\n- /.test(clip)]);
checks.push(["no copy glyph", !clip.includes("⎘")]);
let ok = true;
for (const [name, pass] of checks) { log(pass ? "PASS" : "FAIL", "-", name); if (!pass) ok = false; }
await context.close(); await browser.close();
log(ok ? "SELFCHECK OK" : "SELFCHECK FAILED");
process.exit(ok ? 0 : 1);
