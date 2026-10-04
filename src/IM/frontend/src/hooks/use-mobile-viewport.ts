import { useEffect } from "react";

/** Keep mobile editing controls inside the visual viewport without restricting zoom. */
export function useMobileViewport() {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const root = document.documentElement;
    const update = () => {
      const editing = document.activeElement?.matches("input, textarea, select, [contenteditable='true']");
      // iOS keyboards shrink the visual viewport, while dvh still tracks browser chrome.
      if (window.innerWidth < 768 && editing && Math.abs(viewport.scale - 1) < 0.01) {
        root.style.setProperty("--im-viewport-height", `${viewport.height}px`);
        // Standalone Safari can also pan the page when focusing a bottom input.
        root.style.setProperty("--im-viewport-offset", `${viewport.offsetTop}px`);
      } else {
        root.style.removeProperty("--im-viewport-height");
        root.style.removeProperty("--im-viewport-offset");
      }
    };
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
    viewport.addEventListener("resize", update);
    viewport.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    window.addEventListener("pageshow", update);
    update();
    return () => {
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", update);
      viewport.removeEventListener("resize", update);
      viewport.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      window.removeEventListener("pageshow", update);
      root.style.removeProperty("--im-viewport-height");
      root.style.removeProperty("--im-viewport-offset");
    };
  }, []);
}
