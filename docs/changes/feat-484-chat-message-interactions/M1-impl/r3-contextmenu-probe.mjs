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
await page.waitForTimeout(600);

const bubble = page.locator(".chat-bubble--agent").last();
await bubble.scrollIntoViewIfNeeded();
const box = await bubble.boundingBox();

// 1. Right-click on plain bubble area -> IM menu appears
await page.mouse.click(box.x + box.width / 2, box.y + 30, { button: "right" });
await page.waitForTimeout(400);
const menu = page.locator("[role='menu']");
const menuVisible = await menu.isVisible().catch(() => false);
log("menu visible after right-click:", menuVisible);
const items = await menu.locator("[role='menuitem']").allTextContents().catch(() => []);
log("menu items:", JSON.stringify(items));
const disabledStates = await menu.locator("[role='menuitem']").evaluateAll(
  (els) => els.map((e) => ({ text: e.textContent, ariaDisabled: e.getAttribute("aria-disabled") }))
);
log("menu item aria-disabled:", JSON.stringify(disabledStates));
await page.screenshot({ path: `${EVD}/r3-contextmenu-open.png` });

// 2. Roving: ArrowDown / Home / End across items incl. aria-disabled
await page.keyboard.press("ArrowDown");
await page.waitForTimeout(150);
let focus = await page.evaluate(() => ({ tag: document.activeElement?.tagName, text: document.activeElement?.textContent, ariaDisabled: document.activeElement?.getAttribute?.("aria-disabled") }));
log("focus after ArrowDown:", JSON.stringify(focus));
await page.keyboard.press("End");
await page.waitForTimeout(150);
focus = await page.evaluate(() => document.activeElement?.textContent);
log("focus after End:", JSON.stringify(focus));
await page.keyboard.press("Home");
await page.waitForTimeout(150);
focus = await page.evaluate(() => document.activeElement?.textContent);
log("focus after Home:", JSON.stringify(focus));

// 3. Escape closes menu, focus returns
await page.keyboard.press("Escape");
await page.waitForTimeout(300);
log("menu visible after Escape:", await menu.isVisible().catch(() => false));
focus = await page.evaluate(() => ({ tag: document.activeElement?.tagName, cls: document.activeElement?.className?.toString?.().slice(0, 60) }));
log("focus after Escape:", JSON.stringify(focus));

// 4. Reopen, outside click closes
await page.mouse.click(box.x + box.width / 2, box.y + 30, { button: "right" });
await page.waitForTimeout(400);
log("menu reopened:", await menu.isVisible().catch(() => false));
await page.mouse.click(60, 800, { button: "left" });
await page.waitForTimeout(300);
log("menu visible after outside click:", await menu.isVisible().catch(() => false));

// 5. Reopen, activate Copy message via keyboard Enter
await page.mouse.click(box.x + box.width / 2, box.y + 30, { button: "right" });
await page.waitForTimeout(400);
await page.keyboard.press("Home");
await page.waitForTimeout(120);
await page.keyboard.press("Enter");
await page.waitForTimeout(400);
log("menu visible after Enter on first item:", await menu.isVisible().catch(() => false));
const notice = await page.locator("text=Copied").first().isVisible().catch(() => false);
log("Copied feedback visible:", notice);
await page.screenshot({ path: `${EVD}/r3-contextmenu-copy.png` });

await context.close();
await browser.close();
log("done");
