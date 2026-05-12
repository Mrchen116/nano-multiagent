import { appRoutes } from "../../app/router";
import { renderRouter } from "../../test/render-router";

describe("settings shell mobile (M19 R1 — no sub-nav on mobile)", () => {
  // M19/R11-2: 移动端进入 /settings/agents 等子页不再渲染 Settings 二级 tab pill。
  // 移动端导航由底部 tab + UserMenu/Me 入口完成,settings 子页本身只渲染自己。
  it("does not render the Settings section navigation on mobile", async () => {
    window.innerWidth = 375;
    window.dispatchEvent(new Event("resize"));

    const { container } = renderRouter({ routes: appRoutes, initialEntries: ["/settings/agents"] });

    expect(container.querySelector('nav[aria-label="Settings Sections"]')).toBeNull();
  });
});
