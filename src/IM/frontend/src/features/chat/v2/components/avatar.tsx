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
  const bg = color ?? colorForSeed(initials);
  const dotSize = Math.round(size * 0.28);
  return (
    <span className="chat-avatar" style={{ width: size, height: size, background: bg, fontSize: size * 0.35, letterSpacing: "-0.02em", borderRadius: "50%", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>
      <span aria-hidden="true">{initials.slice(0, 2).toUpperCase()}</span>
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

function colorForSeed(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash << 5) - hash + seed.charCodeAt(i);
  const hue = Math.abs(hash) % 360;
  return `oklch(0.55 0.15 ${hue})`;
}
