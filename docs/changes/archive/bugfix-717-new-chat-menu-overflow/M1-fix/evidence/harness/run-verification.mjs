#!/usr/bin/env node
// Re-runnable evidence harness for bugfix-717 (the chat sidebar "+" creation menu).
//
// It rebuilds both CSS variants through the repository's own pipeline (vite + @tailwindcss/vite, the
// same plugins as `src/IM/frontend/vite.config.ts`), bundles the fixture that mounts the real
// `NewConversationMenu` component, serves it on an isolated loopback port and drives real Chrome.
//
// usage:
//   node docs/changes/bugfix-717-new-chat-menu-overflow/M1-fix/evidence/harness/run-verification.mjs
//   ... --prefix-ref origin/main --out /tmp/bugfix717-evidence
//
// Exit code is 1 when any check fails. Checks are labelled `behavior` (user-observable) or
// `property` (an implementation detail such as the computed `overflow` value).
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// harness/ -> evidence/ -> M1-fix/ -> <unit>/ -> changes/ -> docs/ -> repository root
const REPO = path.resolve(HERE, "..", "..", "..", "..", "..", "..");
const FRONTEND = path.join(REPO, "src/IM/frontend");
const GLOBAL_CSS = "src/IM/frontend/src/styles/global.css";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(`--${name}`);
  return index === -1 ? fallback : args[index + 1];
};
const PREFIX_REF = option("prefix-ref", "origin/main");
const OUT = path.resolve(option("out", path.join(os.tmpdir(), "bugfix717-evidence")));
const SHOTS = path.join(OUT, "shots");
const PORT = Number(option("port", "4319"));
const VIEWPORTS = [
  { name: "375x600", width: 375, height: 600 },
  { name: "1072x444", width: 1072, height: 444 },
  { name: "1440x900", width: 1440, height: 900 }
];
const EXTRA = [
  { name: "1440x300", width: 1440, height: 300 },
  { name: "1072x200", width: 1072, height: 200 },
  { name: "768x400", width: 768, height: 400 },
  { name: "767x444", width: 767, height: 444 },
  { name: "320x480", width: 320, height: 480 }
];

const requireFromFrontend = createRequire(path.join(FRONTEND, "package.json"));
const requireFromRepo = createRequire(path.join(REPO, "package.json"));
const { chromium } = requireFromFrontend("playwright");

fs.mkdirSync(SHOTS, { recursive: true });
// The CSS variants are materialised outside the repository; Tailwind resolves `@import "tailwindcss"`
// relative to the stylesheet, so the output directory needs the frontend's modules on its path.
const relativeToRepo = path.relative(REPO, OUT);
if (!relativeToRepo.startsWith("..") && !path.isAbsolute(relativeToRepo)) {
  throw new Error("--out must point outside the repository so no build artifacts land in the worktree");
}
const nodeModulesLink = path.join(OUT, "node_modules");
if (!fs.existsSync(nodeModulesLink)) fs.symlinkSync(path.join(FRONTEND, "node_modules"), nodeModulesLink);

// ---------------------------------------------------------------------------------------------
// CSS variants
// ---------------------------------------------------------------------------------------------
const vite = await import(pathToFileURL(path.join(FRONTEND, "node_modules/vite/dist/node/index.js")).href);
const tailwindcss = (await import(
  pathToFileURL(path.join(FRONTEND, "node_modules/@tailwindcss/vite/dist/index.mjs")).href
)).default;

async function buildCss({ label, cssSource }) {
  const dir = path.join(OUT, label);
  fs.mkdirSync(dir, { recursive: true });
  const sourceFile = path.join(dir, "global.css");
  fs.writeFileSync(sourceFile, cssSource);
  const entry = path.join(dir, "css-entry.css");
  fs.writeFileSync(entry, `@import "${sourceFile}";\n`);
  const outDir = path.join(dir, "dist");
  await vite.build({
    configFile: false,
    root: FRONTEND,
    plugins: [tailwindcss()],
    logLevel: "warn",
    build: { outDir, emptyOutDir: true, rollupOptions: { input: entry } }
  });
  const assets = path.join(outDir, "assets");
  const css = fs.readdirSync(assets).find((file) => file.endsWith(".css"));
  if (!css) throw new Error(`no css emitted for ${label}`);
  return path.join(assets, css);
}

let prefixSource;
try {
  prefixSource = execFileSync("git", ["show", `${PREFIX_REF}:${GLOBAL_CSS}`], { cwd: REPO, encoding: "utf8" });
} catch {
  throw new Error(`cannot read ${GLOBAL_CSS} at ${PREFIX_REF}; pass --prefix-ref <ref> after fetching it`);
}
const prefixCss = await buildCss({ label: "css-prefix", cssSource: prefixSource });
const fixedCss = await buildCss({
  label: "css-fixed",
  cssSource: fs.readFileSync(path.join(REPO, GLOBAL_CSS), "utf8")
});

// ---------------------------------------------------------------------------------------------
// Fixture bundle + static server
// ---------------------------------------------------------------------------------------------
const serverRoot = path.join(OUT, "site");
fs.mkdirSync(serverRoot, { recursive: true });
fs.copyFileSync(path.join(HERE, "harness.html"), path.join(serverRoot, "harness.html"));
await requireFromRepo("esbuild").build({
  entryPoints: [path.join(HERE, "sidebar-harness.tsx")],
  bundle: true,
  format: "esm",
  jsx: "automatic",
  outfile: path.join(serverRoot, "sidebar-harness.js"),
  nodePaths: [path.join(FRONTEND, "node_modules")],
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "warning"
});

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" };
const server = http.createServer((request, response) => {
  const file = path.join(serverRoot, decodeURIComponent((request.url ?? "/").split("?")[0]));
  if (!file.startsWith(serverRoot) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    response.writeHead(404).end("not found");
    return;
  }
  response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "application/octet-stream" });
  fs.createReadStream(file).pipe(response);
});
await new Promise((resolve) => server.listen(PORT, "127.0.0.1", resolve));

// ---------------------------------------------------------------------------------------------
// Probes executed inside the page
// ---------------------------------------------------------------------------------------------
const readState = () => {
  const q = (selector) => document.querySelector(selector);
  const row = q(".chat-sidebar-header-row");
  const sidebar = q(".chat-sidebar");
  const menu = q(".chat-conversation-menu-items");
  const title = q(".chat-sidebar-title");
  const trigger = q(".chat-sidebar-create-trigger");
  const rect = (element) => {
    if (!element) return null;
    const box = element.getBoundingClientRect();
    return {
      x: +box.x.toFixed(1), y: +box.y.toFixed(1),
      width: +box.width.toFixed(1), height: +box.height.toFixed(1),
      right: +box.right.toFixed(1), bottom: +box.bottom.toFixed(1)
    };
  };
  const inViewport = (element) => {
    if (!element) return null;
    const box = element.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && box.top >= 0 && box.left >= 0
      && box.bottom <= innerHeight && box.right <= innerWidth;
  };
  const hitTest = (element) => {
    if (!element) return null;
    const box = element.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) return false;
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false;
    const hit = document.elementFromPoint(x, y);
    return Boolean(hit && (hit === element || element.contains(hit)));
  };
  const items = [...document.querySelectorAll('.chat-conversation-menu-items [role="menuitem"]')];
  const root = document.documentElement;
  return {
    viewport: { width: innerWidth, height: innerHeight },
    activeElement: document.activeElement ? (document.activeElement.textContent || "").trim().slice(0, 16) : null,
    row: {
      overflow: row ? getComputedStyle(row).overflow : null,
      opacity: row ? getComputedStyle(row).opacity : null,
      scrollTop: row ? row.scrollTop : null,
      scrollHeight: row ? row.scrollHeight : null,
      clientHeight: row ? row.clientHeight : null,
      rect: rect(row)
    },
    sidebar: {
      overflow: sidebar ? getComputedStyle(sidebar).overflow : null,
      scrollTop: sidebar ? sidebar.scrollTop : null,
      scrollHeight: sidebar ? sidebar.scrollHeight : null,
      clientHeight: sidebar ? sidebar.clientHeight : null,
      rect: rect(sidebar),
      scrollWidth: sidebar ? sidebar.scrollWidth : null,
      clientWidth: sidebar ? sidebar.clientWidth : null
    },
    documentScroll: {
      top: document.scrollingElement ? document.scrollingElement.scrollTop : null,
      scrollWidth: root.scrollWidth,
      clientWidth: root.clientWidth
    },
    menuHeight: menu ? +menu.getBoundingClientRect().height.toFixed(1) : null,
    menuRect: rect(menu),
    items: items.map((element) => ({
      text: element.textContent.trim().slice(0, 12),
      rect: rect(element),
      inViewport: inViewport(element),
      hittable: hitTest(element)
    })),
    title: { rect: rect(title), inViewport: inViewport(title) },
    trigger: { rect: rect(trigger), inViewport: inViewport(trigger), hittable: hitTest(trigger) }
  };
};

// Freezes the collapse/expand transition at a fixed time instead of sampling wall-clock time:
// a `waitForTimeout` sample can land before the transition starts (it did, at 90ms).
const freezeTransition = async ({ searching, atMs, hold }) => {
  const row = document.querySelector(".chat-sidebar-header-row");
  globalThis.__setSearching(searching);
  await new Promise((resolve) => {
    const tick = () => (document.querySelector(".chat-sidebar")?.classList.contains("chat-sidebar--searching") === searching)
      ? resolve() : requestAnimationFrame(tick);
    tick();
  });
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const animations = row.getAnimations();
  for (const animation of animations) {
    animation.pause();
    animation.currentTime = atMs;
  }
  const frozen = {
    animations: animations.length,
    height: +row.getBoundingClientRect().height.toFixed(1),
    opacity: getComputedStyle(row).opacity
  };
  if (!hold) for (const animation of animations) animation.finish();
  return frozen;
};

const finishTransitions = () => document.getAnimations().forEach((animation) => animation.finish());

const readRow = () => {
  const row = document.querySelector(".chat-sidebar-header-row");
  return { height: +row.getBoundingClientRect().height.toFixed(1), opacity: getComputedStyle(row).opacity };
};

// Explains why the un-clipped row content is not visible during the expand animation: measure what
// actually paints on top of the overlap band, then repeat with `.chat-search-input-row` unpositioned.
const probeOverlapCover = () => {
  const row = document.querySelector(".chat-sidebar-header-row");
  const trigger = document.querySelector(".chat-sidebar-create-trigger");
  const searchRow = document.querySelector(".chat-search-input-row");
  const describe = (element) => element ? `${element.tagName.toLowerCase()}.${element.className}` : null;
  const band = () => {
    const triggerBox = trigger.getBoundingClientRect();
    const searchBox = searchRow.getBoundingClientRect();
    const top = Math.max(triggerBox.top, searchBox.top);
    const bottom = Math.min(triggerBox.bottom, searchBox.bottom);
    return { top, bottom, height: +(bottom - top).toFixed(1), x: triggerBox.x + triggerBox.width / 2 };
  };
  const observed = band();
  const covered = observed.height > 0
    ? describe(document.elementFromPoint(observed.x, (observed.top + observed.bottom) / 2))
    : null;
  const saved = searchRow.style.position;
  searchRow.style.position = "static";
  const uncovered = observed.height > 0
    ? describe(document.elementFromPoint(observed.x, (observed.top + observed.bottom) / 2))
    : null;
  searchRow.style.position = saved;
  return {
    rowHeight: +row.getBoundingClientRect().height.toFixed(1),
    searchRowPosition: getComputedStyle(searchRow).position,
    overlapBand: observed,
    topElementWithPositionedSearchRow: covered,
    topElementWithStaticSearchRow: uncovered
  };
};

// ---------------------------------------------------------------------------------------------
// Checks
// ---------------------------------------------------------------------------------------------
const checks = [];
const record = (kind, label, passed, detail) => {
  checks.push({ kind, label, passed, detail });
  console.log(`${passed ? "PASS" : "FAIL"}  [${kind}] ${label}${detail === undefined ? "" : `  ${JSON.stringify(detail)}`}`);
};
const info = (label, detail) => {
  checks.push({ kind: "info", label, passed: true, detail });
  console.log(`INFO  ${label}  ${JSON.stringify(detail)}`);
};

const browser = await chromium.launch({ channel: "chrome" });

async function openHarness(size, cssPath) {
  const page = await browser.newPage({ viewport: { width: size.width, height: size.height } });
  await page.goto(`http://127.0.0.1:${PORT}/harness.html`);
  await page.addStyleTag({ path: cssPath });
  await page.waitForSelector(".chat-sidebar-create-trigger");
  return page;
}

// Variant-level checks. The four layout invariants must hold in both variants; the four defect
// conditions are asserted in the direction that matches the variant, so a green run means
// "reproduced on the pre-fix CSS" and "gone after the fix" respectively.
for (const variant of [
  { label: "prefix", css: prefixCss, expectBroken: true },
  { label: "fixed", css: fixedCss, expectBroken: false }
]) {
  for (const size of VIEWPORTS) {
    const page = await openHarness(size, variant.css);
    await page.click(".chat-sidebar-create-trigger");
    await page.waitForSelector(".chat-conversation-menu-items");
    await page.waitForTimeout(150);
    const state = await page.evaluate(readState);
    await page.screenshot({ path: path.join(SHOTS, `${variant.label}-${size.name}-open.png`) });

    const tag = `${variant.label} ${size.name}`;
    const direction = variant.expectBroken ? "defect present" : "defect gone";
    const itemsReachable = state.items.length === 3 && state.items.every((item) => item.inViewport && item.hittable);
    const triggerUsable = Boolean(state.trigger.inViewport && state.trigger.hittable);

    record("behavior", `${tag} sidebar did not scroll`, state.sidebar.scrollTop === 0, state.sidebar.scrollTop);
    record("behavior", `${tag} document did not scroll`, state.documentScroll.top === 0, state.documentScroll.top);
    record("behavior", `${tag} popover taller than 120px`, state.menuHeight > 120, state.menuHeight);
    record("behavior", `${tag} popover stays inside the sidebar`,
      state.menuRect.right <= state.sidebar.rect.right && state.menuRect.x >= state.sidebar.rect.x,
      { menuRight: state.menuRect.right, sidebarRight: state.sidebar.rect.right });
    record("property", `${tag} header row computed overflow is ${variant.expectBroken ? "hidden" : "visible"}`,
      variant.expectBroken ? state.row.overflow === "hidden" : state.row.overflow === "visible", state.row.overflow);
    record("behavior", `${tag} ${direction}: header row scrolls its own content away`,
      variant.expectBroken ? state.row.scrollTop > 0 : state.row.scrollTop === 0, state.row.scrollTop);
    record("behavior", `${tag} ${direction}: all three menu items reachable`,
      variant.expectBroken ? !itemsReachable : itemsReachable,
      state.items.map((item) => `${item.text}:${item.hittable}/${item.inViewport}`));
    record("behavior", `${tag} ${direction}: title in the viewport`,
      variant.expectBroken ? !state.title.inViewport : state.title.inViewport, state.title.rect);
    record("behavior", `${tag} ${direction}: "+" in the viewport and clickable`,
      variant.expectBroken ? !triggerUsable : triggerUsable, state.trigger);
    info(`${tag} open state`, state);
    await page.close();
  }
}

// Post-fix behaviour: keyboard/pointer contract, settled search collapse and frozen mid frames.
for (const size of VIEWPORTS) {
  const page = await openHarness(size, fixedCss);
  const tag = `fixed ${size.name}`;
  await page.click(".chat-sidebar-create-trigger");
  await page.waitForSelector(".chat-conversation-menu-items");
  const focused = await page.evaluate(readState);
  record("behavior", `${tag} focus landed on the first item`,
    focused.activeElement === focused.items[0]?.text, focused.activeElement);
  await page.locator('.chat-conversation-menu-items [role="menuitem"]').nth(1).click();
  const picked = await page.evaluate(() => globalThis.__picked ?? null);
  record("behavior", `${tag} second item starts a group chat`, picked === "new-group", picked);
  record("behavior", `${tag} focus returned to "+" after selecting`,
    await page.evaluate(() => document.activeElement?.classList?.contains("chat-sidebar-create-trigger") === true));

  await page.click(".chat-sidebar-create-trigger");
  await page.waitForSelector(".chat-conversation-menu-items");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(80);
  record("behavior", `${tag} Escape closes the menu`,
    await page.evaluate(() => document.querySelector(".chat-conversation-menu-items") === null));
  record("behavior", `${tag} Escape returns focus to "+"`,
    await page.evaluate(() => document.activeElement?.classList?.contains("chat-sidebar-create-trigger") === true));

  const entering = await page.evaluate(freezeTransition, { searching: true, atMs: 40, hold: false });
  info(`${tag} enter frozen at 40ms`, entering);
  record("behavior", `${tag} entering search still animates the row shut`,
    entering.animations > 0 && entering.height < 44 && entering.height > 0, entering);
  const collapsed = await page.evaluate(freezeTransition, { searching: true, atMs: 400, hold: false });
  record("behavior", `${tag} search view hides the header row`,
    collapsed.height < 1 && collapsed.opacity === "0", collapsed);

  // Hold the expand transition at 20ms so the overlap probe measures the frozen frame, not the end state.
  const exiting = await page.evaluate(freezeTransition, { searching: false, atMs: 20, hold: true });
  info(`${tag} exit frozen at 20ms`, exiting);
  record("behavior", `${tag} exiting search grows the row back`, exiting.height > 0 && exiting.height < 40, exiting);
  info(`${tag} overlap cover probe`, await page.evaluate(probeOverlapCover));
  await page.evaluate(finishTransitions);
  const restored = await page.evaluate(readRow);
  record("behavior", `${tag} header row restored after leaving search`,
    restored.height >= 40 && restored.opacity === "1", restored);
  await page.close();
}

// Layout edge cases: no scrolling anywhere, popover contained, no horizontal scrollbar.
for (const size of EXTRA) {
  const page = await openHarness(size, fixedCss);
  const tag = `fixed ${size.name}`;
  await page.click(".chat-sidebar-create-trigger");
  await page.waitForSelector(".chat-conversation-menu-items");
  await page.waitForTimeout(150);
  const state = await page.evaluate(readState);
  record("behavior", `${tag} nothing scrolls`, state.row.scrollTop === 0 && state.sidebar.scrollTop === 0 && state.documentScroll.top === 0,
    { row: state.row.scrollTop, sidebar: state.sidebar.scrollTop, document: state.documentScroll.top });
  record("behavior", `${tag} all three items hit-testable`, state.items.every((item) => item.hittable),
    state.items.map((item) => item.hittable));
  record("behavior", `${tag} no horizontal overflow`,
    state.documentScroll.scrollWidth === state.documentScroll.clientWidth
    && state.menuRect.right <= state.sidebar.rect.right,
    { scrollWidth: state.documentScroll.scrollWidth, clientWidth: state.documentScroll.clientWidth, menuRight: state.menuRect.right, sidebarRight: state.sidebar.rect.right });
  await page.close();
}

await browser.close();
await new Promise((resolve) => server.close(resolve));

const behavior = checks.filter((check) => check.kind === "behavior");
const property = checks.filter((check) => check.kind === "property");
const failed = checks.filter((check) => !check.passed);
fs.writeFileSync(path.join(OUT, "summary.json"), JSON.stringify({ prefixRef: PREFIX_REF, prefixCss, fixedCss, checks }, null, 2));
console.log(`\n${failed.length === 0 ? "ALL CHECKS PASSED" : `${failed.length} CHECK(S) FAILED`} — `
  + `${behavior.filter((c) => c.passed).length}/${behavior.length} behavior, `
  + `${property.filter((c) => c.passed).length}/${property.length} property`);
console.log(`artifacts: ${OUT}`);
process.exit(failed.length === 0 ? 0 : 1);
