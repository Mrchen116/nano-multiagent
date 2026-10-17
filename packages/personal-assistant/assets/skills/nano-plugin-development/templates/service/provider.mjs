export function apply(ctx) {
  // This state belongs to one preset instance; it intentionally resets on reload.
  ctx.provide('workspaceCallCounter', { count: 0 });
}
