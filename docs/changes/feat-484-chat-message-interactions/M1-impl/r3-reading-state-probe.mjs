import { chromium } from "playwright";
const IM_URL = "http://127.0.0.1:54488";
const CONV_URL = `${IM_URL}/chat/8ea103f32c3f4b6cb66ea50dcac37d82`;
const EVD = "/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-484/docs/changes/feat-484-chat-message-interactions/M1-impl/review-r3-evidence";
const log = (...a) => console.log(new Date().toISOString(), ...a);

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
await page.goto(`${IM_URL}/login`);
await page.getByLabel("Username").fill("nano");
await page.getByLabel("Password").fill("nano1234");
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(/\/chat/, { timeout: 15000 });
await page.goto(CONV_URL);
await page.waitForSelector(".chat-message-body", { timeout: 20000 });
// Park mouse far from bubbles before anything else
await page.mouse.move(20, 850);
await page.waitForTimeout(800);

const bubble = page.locator(".chat-bubble--agent").last();
const toolbar = bubble.locator("[data-testid^='message-copy-']").first();
const state = await toolbar.evaluate((el) => {
  const wrap = el.closest("div");
  const cs = getComputedStyle(wrap);
  return { opacity: cs.opacity, pointerEvents: cs.pointerEvents, visibility: cs.visibility };
});
log("toolbar wrapper computed (mouse parked):", JSON.stringify(state));
await page.screenshot({ path: `${EVD}/r3-desktop-reading-clean.png` });

await context.close();
await browser.close();
log("done");
