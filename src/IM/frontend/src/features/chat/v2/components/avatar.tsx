/**
 * Single source of truth for agent avatar colors.
 *
 * The same agent must render the same avatar color everywhere it appears:
 * settings list, settings detail, chat sidebar row, chat header, and message
 * bubbles. Two things have to stay aligned for that to hold:
 *   1. the seed — `display_name` is the only identifier available in *all*
 *      those places. Message bubbles only carry the sender's IM user UUID
 *      (`sender_user_id`), never the `agent_id` the settings pages key off, so
 *      keying on `agent_id` would leave bubbles a different color from the
 *      sidebar/header. Seeding on `display_name` keeps every surface in sync
 *      (and the avatar initials already track `display_name` anyway).
 *   2. the oklch lightness/chroma — fixed here so every call site renders the
 *      same shade for a given hue.
 */
const AVATAR_LIGHTNESS = 0.52;
const AVATAR_CHROMA = 0.14;

/** Deterministic avatar color from an arbitrary seed string. */
export function colorForAgentSeed(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash << 5) - hash + seed.charCodeAt(i);
  const hue = Math.abs(hash) % 360;
  return `oklch(${AVATAR_LIGHTNESS} ${AVATAR_CHROMA} ${hue})`;
}

/** Avatar color for an agent, seeded by display_name (id fallback). */
export function colorForAgent(agent: { display_name?: string | null; agent_id?: string | null }): string {
  return colorForAgentSeed(agent.display_name || agent.agent_id || "");
}

interface AvatarProps {
  initials: string;
  color?: string;
  size?: number;
  status?: "online" | "offline" | "running" | null;
}

/**
 * Single circular initials avatar with an optional status dot. We compute the
 * color from the seed string when none is provided so two avatars with the
 * same initials stay visually identifiable across the list.
 *
 * Status dot matches prototype (im-components.jsx): border uses the sidebar
 * background colour so the dot sits cleanly on dark sidebar rows.
 */
export function Avatar({ initials, color, size = 32, status }: AvatarProps) {
  const bg = color ?? colorForAgentSeed(initials);
  const dotSize = size * 0.28;
  return (
    <span className="chat-avatar" style={{ width: size, height: size }}>
      <span
        className="chat-avatar-face"
        style={{
          width: size,
          height: size,
          background: bg,
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

