import type { ComponentProps } from "react";
import { Link, useLocation, useInRouterContext } from "react-router-dom";

/** Keep task visits in the app so per-chat composer snapshots survive. */
export function TaskGraphLink({ href, node: _node, ...props }: ComponentProps<"a"> & { node?: unknown }) {
  const inRouter = useInRouterContext();
  if (href) {
    try {
      const target = new URL(href, window.location.href);
      if (inRouter && target.origin === window.location.origin && /^\/chat\/[^/]+$/.test(target.pathname) && target.searchParams.has('message_id')) {
        return <SourceMessageLink {...props} href={`${target.pathname}${target.search}${target.hash}`} />;
      }
      if (target.origin === window.location.origin && (target.pathname === "/tasks" || target.pathname.startsWith("/tasks/"))) {
        return <Link {...props} to={`${target.pathname}${target.search}${target.hash}`} />;
      }
    } catch {
      // A malformed Markdown link retains the existing ordinary-anchor behavior.
    }
  }
  return <a {...props} href={href} />;
}

function SourceMessageLink({href,...props}:ComponentProps<'a'>) {
  const location=useLocation();
  return <Link {...props} to={href!} state={{sourceReturnUrl:location.pathname+location.search}}/>;
}
