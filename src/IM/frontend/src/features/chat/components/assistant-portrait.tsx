import PALETTE from "../../../../../shared/portrait-palette.json";
import './assistant-portrait.css';

// The silhouette carries the personality so the face stays legible at chat size.
const PERSONAL_SHAPES = [
  'M15 38C15 19 25 10 42 11c18 1 27 13 25 30-2 18-16 28-33 25C20 64 13 53 15 38Z',
  'M12 45c-2-16 7-23 19-27C45 8 61 13 66 28c7 19-3 38-21 40C27 71 14 62 12 45Z',
  'M24 17c6-12 23-12 29 0 15-3 24 13 16 24 8 13-4 28-18 24-8 10-25 7-28-5C7 58 5 40 16 32c-4-6-1-12 8-15Z',
  'M43 9C37 22 16 25 13 42c-4 18 11 29 29 27 19-1 30-14 24-31C61 24 48 21 43 9Z',
];
const AGENT_SHAPES = [
  'M14 43C14 22 25 12 40 12s26 10 26 31v17c0 5-4 8-9 8H23c-5 0-9-3-9-8Z',
  'M36 12c4-4 10-4 14 1l18 22c4 5 3 11-1 15L46 68c-5 4-11 3-15-1L12 45c-4-5-3-11 1-15Z',
  'M18 16h35c8 0 13 5 13 13v33c0 5-4 8-9 7l-35-6c-7-1-11-6-10-13l2-25c0-5 1-9 4-9Z',
  'M34 13c3-7 11-7 14 0l6 13 13 6c7 3 7 11 0 14l-13 6-6 14c-3 7-11 7-14 0l-6-14-14-6c-7-3-7-11 0-14l14-6Z',
];
const FACE_TILTS = [-7, 8, -4, 5];

/** Stable default appearance for existing agents, independent of their mutable name. */
export function avatarVariantFor(id: string): number {
  let hash = 2166136261;
  for (const char of id) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return (hash >>> 0) % 24;
}

/** Organic companions and geometric colleagues share a minimal, expressive face. */
export function AssistantPortrait({ size = 64, personal = true, seed = '', variant }: {
  size?: number; personal?: boolean; seed?: string; variant?: number | null;
}) {
  const selected = variant ?? (seed ? avatarVariantFor(seed) : 0);
  const color = selected % 6, style = Math.floor(selected / 6);
  const { body, ink } = PALETTE[color];
  return <svg className="assistant-portrait" data-avatar={`${personal ? 'personal' : 'agent'}-${selected}`} width={size} height={size} viewBox="0 0 80 80" fill="none" aria-hidden="true">
    <path d={(personal ? PERSONAL_SHAPES : AGENT_SHAPES)[style]} fill={body} />
    <g transform={`rotate(${FACE_TILTS[style]} 40 40)`}>
      <g className="assistant-portrait-eyes">
        <ellipse cx="31" cy="37" rx={personal ? 7 : 6.5} ry={personal ? 9 : 8} fill="#fffdf8" />
        <ellipse cx="49" cy="37" rx={personal ? 7 : 6.5} ry={personal ? 9 : 8} fill="#fffdf8" />
        <ellipse cx={style % 2 ? 33 : 30} cy="38" rx="2.8" ry="4.2" fill={ink} />
        <ellipse cx={style % 2 ? 51 : 48} cy="38" rx="2.8" ry="4.2" fill={ink} />
      </g>
      {personal && <path d="M36 52q5 4 10-1" stroke={ink} strokeWidth="2.5" strokeLinecap="round" />}
    </g>
  </svg>;
}
