import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppProviders } from "./providers";

// AppProviders owns the viewport-to-CSS bridge for auth and protected routes.
function mountViewport(width = 430) {
  vi.stubGlobal("innerWidth", width);
  vi.spyOn(document.documentElement, "clientHeight", "get").mockReturnValue(780);
  const viewport = Object.assign(new EventTarget(), { height: 780, scale: 1, offsetTop: 0 });
  vi.stubGlobal("visualViewport", viewport);
  const view = render(<AppProviders><input aria-label="Message" /><button>Done</button></AppProviders>);
  return { ...view, viewport, input: screen.getByRole("textbox") };
}

const height = () => document.documentElement.style.getPropertyValue("--im-viewport-height");

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("mobile input viewport", () => {
  it("fits the visible height while editing, then restores CSS height on blur and unmount", () => {
    const { viewport, input, unmount } = mountViewport();
    act(() => input.focus());
    act(() => {
      viewport.height = 420;
      viewport.dispatchEvent(new Event("resize"));
    });
    expect(height()).toBe("420px");
    expect(document.documentElement.style.getPropertyValue("--im-composer-safe-bottom")).toBe("0px");
    act(() => {
      viewport.offsetTop = 68;
      viewport.dispatchEvent(new Event("scroll"));
    });
    expect(document.documentElement.style.getPropertyValue("--im-viewport-offset")).toBe("68px");
    act(() => {
      viewport.height = 780;
      viewport.dispatchEvent(new Event("resize"));
    });
    expect(document.documentElement.style.getPropertyValue("--im-composer-safe-bottom")).toBe("");
    act(() => screen.getByRole("button").focus());
    expect(height()).toBe("");
    expect(document.documentElement.style.getPropertyValue("--im-viewport-offset")).toBe("");
    act(() => input.focus());
    expect(height()).toBe("780px");
    unmount();
    viewport.dispatchEvent(new Event("resize"));
    expect(height()).toBe("");
  });

  it("leaves desktop and user zoom to the browser", () => {
    const { viewport, input } = mountViewport(1440);
    act(() => input.focus());
    expect(height()).toBe("");
    vi.stubGlobal("innerWidth", 430);
    act(() => window.dispatchEvent(new Event("resize")));
    expect(height()).toBe("780px");
    act(() => {
      viewport.scale = 1.5;
      viewport.dispatchEvent(new Event("resize"));
    });
    expect(height()).toBe("");
  });

  it("keeps the CSS fallback when VisualViewport is unavailable", () => {
    vi.stubGlobal("visualViewport", undefined);
    render(<AppProviders><input aria-label="Message" /></AppProviders>);
    act(() => screen.getByRole("textbox").focus());
    expect(height()).toBe("");
  });
});
