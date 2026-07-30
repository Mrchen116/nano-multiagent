import { chromium } from "playwright";
const IM_URL = "http://127.0.0.1:54488";
const CONV_URL = `${IM_URL}/chat/8ea103f32c3f4b6cb66ea50dcac37d82`;
const EVD = "/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-484/docs/changes/feat-484-chat-message-interactions/M1-impl/review-r3-evidence";
const log = (...a) => console.log(new Date().toISOString(), ...a);

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  permissions: ["clipboard-read", "clipboard-write"]
});
const page = await context.newPage();
await page.goto(`${IM_URL}/login`);
await page.getByLabel("Username").fill("nano");
await page.getByLabel("Password").fill("nano1234");
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(/\/chat/, { timeout: 15000 });
await page.goto(CONV_URL);
await page.waitForSelector(".chat-message-body", { timeout: 20000 });
await page.waitForTimeout(600);

const bubble = page.locator(".chat-bubble--agent").last();
await bubble.scrollIntoViewIfNeeded();
const box = await bubble.boundingBox();
const menu = page.locator("[role='menu']");

// Keyboard: open menu, Home -> Copy message, Enter
await page.mouse.click(box.x + box.width / 2, box.y + 30, { button: "right" });
await page.waitForTimeout(400);
await page.keyboard.press("Home");
await page.waitForTimeout(150);
log("focus before Enter:", await page.evaluate(() => document.activeElement?.textContent));
await page.keyboard.press("Enter");
await page.waitForTimeout(600);
log("menu visible after Enter(Copy):", await menu.isVisible().catch(() => false));
log("Copied visible:", await page.locator("text=Copied").first().isVisible().catch(() => false));
log("focus after action:", JSON.stringify(await page.evaluate(() => ({ tag: document.activeElement?.tagName, cls: document.activeElement?.className?.toString?.().slice(0,60) }))));
const clip = await page.evaluate(() => navigator.clipboard.readText());
log("clipboard starts with:", JSON.stringify(clip.slice(0, 30)));
await page.screenshot({ path: `${EVD}/r3-keyboard-copy-result.png` });

// Pointer: click Copy message item directly
await page.mouse.click(box.x + box.width / 2, box.y + 30, { button: "right" });
await page.waitForTimeout(400);
await menu.locator("[role='menuitem']", { hasText: "Copy message" }).click();
await page.waitForTimeout(600);
log("[pointer] menu visible after click Copy:", await menu.isVisible().catch(() => false));
log("[pointer] Copied visible:", await page.locator("text=Copied").first().isVisible().catch(() => false));
await page.screenshot({ path: `${EVD}/r3-pointer-copy-result.png` });

await context.close();
await browser.close();
log("done");
