/**
 * Shared Agent palette, seeded by display name: historical message senders carry
 * an IM user UUID rather than agent_id, so names keep colors aligned across views.
 */
const AVATAR_PALETTE = [
  { background: "#e4dbcf", foreground: "#6b5945" },
  { background: "#d9dfd1", foreground: "#506345" },
  { background: "#dfd8e8", foreground: "#69567b" },
  { background: "#e7d7dc", foreground: "#79525f" },
  { background: "#cbdedb", foreground: "#2f5954" },
  { background: "#d5ddea", foreground: "#485c7d" }
];

/** Deterministic color from a curated palette, seeded by the full display name. */
export function colorForAgentSeed(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash << 5) - hash + seed.charCodeAt(i);
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length].background;
}

/** Soft Agent backgrounds use dark lettering; explicit non-Agent colors retain white. */
export function foregroundForAvatar(background: string): string {
  return AVATAR_PALETTE.find((color) => color.background === background)?.foreground ?? "#fff";
}

/** Avatar color for an agent, seeded by display_name (id fallback). */
export function colorForAgent(agent: { display_name?: string | null; agent_id?: string | null }): string {
  return colorForAgentSeed(agent.display_name || agent.agent_id || "");
}

/** Initials for an agent display name. The same name must render the same
 *  initials on every surface (settings list, detail, chat), so the rule lives
 *  here once instead of being copied per call site. */
export function initialsOf(displayName: string): string {
  const trimmed = displayName.trim();
  if (!trimmed) return "AG";
  return trimmed.slice(0, 2).toUpperCase();
}

interface AvatarProps {
  initials: string;
  /** Must be provided by every call site via colorForAgent(). Required to prevent
   *  per-call-site seed divergence — omitting it is a type error. */
  color: string;
  size?: number;
  status?: "online" | "offline" | "running" | null;
}

/**
 * Single circular initials avatar with an optional status dot.
 *
 * `color` is required: callers must pass `colorForAgent({display_name, agent_id})`
 * (or an explicit fixed color for non-agent avatars such as group chats). Making
 * it required ensures the compiler catches any future call site that forgets to
 * wire up the single source of truth.
 *
 * Status dot matches prototype (im-components.jsx): border uses the sidebar
 * background colour so the dot sits cleanly on dark sidebar rows.
 */
export function Avatar({ initials, color, size = 32, status }: AvatarProps) {
  const bg = color;
  const dotSize = size * 0.28;
  return (
    <span className="chat-avatar" style={{ width: size, height: size }}>
      <span
        className="chat-avatar-face"
        style={{
          width: size,
          height: size,
          background: bg,
          color: foregroundForAvatar(bg),
          fontWeight: 600,
          fontSize: size * 0.35,
          letterSpacing: "-0.02em"
        }}
        aria-hidden="true"
      >
        {initials.slice(0, 2).toUpperCase()}
      </span>
      {status && (
        <span
          className={`chat-avatar-status chat-avatar-status--${status}`}
          aria-label={status}
          style={{
            width: dotSize,
            height: dotSize,
            bottom: 1,
            right: 1,
            borderWidth: 2,
          }}
        />
      )}
    </span>
  );
}

/** Group mark shared by the sidebar and chat header. */
export function GroupAvatar({ size = 36, label }: { size?: number; label: string }) {
  return (
    <span role="img" aria-label={label} style={{
      width: size, height: size, flexShrink: 0, display: "inline-flex",
      alignItems: "center", justifyContent: "center",
      borderRadius: size * 0.275, background: "var(--im-group-avatar)", color: "var(--im-group-avatar-text)"
    }}>
      <svg width={size * 0.525} height={size * 0.525} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M18 21a8 8 0 0 0-16 0" />
        <circle cx="10" cy="8" r="5" />
        <path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3" />
      </svg>
    </span>
  );
}

/* Lucide users-round, v0.468.0 — ISC License.
 * Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part
 * of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */
