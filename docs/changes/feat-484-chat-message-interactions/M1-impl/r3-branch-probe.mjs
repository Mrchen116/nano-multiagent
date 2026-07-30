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
const menu = page.locator("[role='menu']");

await page.mouse.click(box.x + box.width / 2, box.y + 30, { button: "right" });
await page.waitForTimeout(400);
const urlBefore = page.url();
log("url before branch:", urlBefore);
await menu.locator("[role='menuitem']", { hasText: "Branch from here" }).click();
await page.waitForTimeout(1500);
const urlAfter = page.url();
log("url after branch:", urlAfter);
log("navigated to fork:", urlAfter !== urlBefore && /\/chat\//.test(urlAfter));
await page.screenshot({ path: `${EVD}/r3-branch-result.png` });

await context.close();
await browser.close();
log("done");
