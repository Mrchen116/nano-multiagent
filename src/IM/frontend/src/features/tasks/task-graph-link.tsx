import type { ComponentProps } from "react";
import { Link } from "react-router-dom";

/** Keep task visits in the app so per-chat composer snapshots survive. */
export function TaskGraphLink({ href, node: _node, ...props }: ComponentProps<"a"> & { node?: unknown }) {
  if (href) {
    try {
      const target = new URL(href, window.location.href);
      if (target.origin === window.location.origin && (target.pathname === "/tasks" || target.pathname.startsWith("/tasks/"))) {
        return <Link {...props} to={`${target.pathname}${target.search}${target.hash}`} />;
      }
    } catch {
      // A malformed Markdown link retains the existing ordinary-anchor behavior.
    }
  }
  return <a {...props} href={href} />;
}
