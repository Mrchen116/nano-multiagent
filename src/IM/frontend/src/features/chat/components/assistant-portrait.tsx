const PALETTE = [
  ['#eae2fa', '#68508d', '#e9b45d'], ['#dcefe6', '#376e5e', '#dfae55'],
  ['#dfeafa', '#466487', '#de9d70'], ['#fbe4d9', '#925b48', '#a78cc7'],
  ['#f7e0ec', '#8c4e70', '#d5ab55'], ['#f6edcf', '#7c693a', '#769ca4'],
];
const PERSONAL_SHAPES = [
  'M13 20C17 8 60 5 67 20c6 12 5 37-6 44-10 7-30 5-41 8l2-11C10 55 8 34 13 20Z',
  'M11 30c0-16 13-22 29-22s29 6 29 22v15c0 16-13 23-29 23H19l3-9c-7-5-11-14-11-29Z',
  'M14 29C4 10 25 5 34 14c12-11 35-4 30 12 15 18 3 39-15 41H24C8 66 3 43 14 29Z',
  'M13 22C25 5 55 5 67 22l-3 31c-3 12-16 16-30 15L19 74l2-14C11 52 10 38 13 22Z',
];
const AGENT_SHAPES = [
  'M22 10h36l12 13v34L58 69H22L10 57V23Z',
  'M40 6 68 21v38L40 74 12 59V21Z',
  'M12 27C12 14 24 8 40 8s28 6 28 19v28c0 10-7 16-17 16H29c-10 0-17-6-17-16Z',
  'M23 10h34c7 0 13 6 13 13v27L55 69H23c-7 0-13-6-13-13V23c0-7 6-13 13-13Z',
];

/** Stable default appearance for existing agents, independent of their mutable name. */
export function avatarVariantFor(id: string): number {
  let hash = 2166136261;
  for (const char of id) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return (hash >>> 0) % 24;
}

/** Two related visual families with independently selectable color and silhouette. */
export function AssistantPortrait({ size = 64, personal = true, seed = '', variant }: {
  size?: number; personal?: boolean; seed?: string; variant?: number | null;
}) {
  const selected = variant ?? (seed ? avatarVariantFor(seed) : 0);
  const color = selected % 6, style = Math.floor(selected / 6);
  const [background, ink, accent] = PALETTE[color];
  return <svg className="assistant-portrait" data-avatar={`${personal ? 'personal' : 'agent'}-${selected}`} width={size} height={size} viewBox="0 0 80 80" fill="none" aria-hidden="true">
    <path d={(personal ? PERSONAL_SHAPES : AGENT_SHAPES)[style]} fill={background} />
    {personal ? <>
      <path d="M21 22c10-7 27-8 36-3" stroke="white" strokeWidth="3" strokeLinecap="round" />
      {style === 1 && <g stroke={ink} strokeWidth="2"><circle cx="29" cy="37" r="9" /><circle cx="50" cy="37" r="9" /><path d="M38 36h3" /></g>}
      <rect x="26" y="32" width="6" height="11" rx="3" fill={ink} />
      <rect x="47" y="32" width="6" height="11" rx="3" fill={ink} />
      <path d="M35 49q5 4 10-1" stroke={ink} strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="22" cy="46" r="4" fill={accent} opacity=".35" /><circle cx="57" cy="46" r="4" fill={accent} opacity=".35" />
      {style === 2 ? <path d="M37 14C22 2 49-1 43 14" fill={accent} /> : style === 3 ? <path d="m60 17 8-5 1 12-9-4Z" fill={accent} /> : <path d="m66 5 2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5Z" fill={accent} />}
    </> : <>
      <path d="M25 18h30" stroke={accent} strokeWidth="4" strokeLinecap="round" />
      <rect x="17" y="27" width="46" height="27" rx={style === 1 ? 6 : 12} fill={ink} />
      <path d={style === 2 ? 'M25 40h7m16 0h7' : 'M29 36v7m22-7v7'} stroke="white" strokeWidth="4" strokeLinecap="round" />
      <path d="M34 61h12" stroke={ink} strokeWidth="3" strokeLinecap="round" />
      {style === 0 || style === 2 ? <><rect x="6" y="33" width="5" height="14" rx="2" fill={accent} /><rect x="69" y="33" width="5" height="14" rx="2" fill={accent} /></> : <circle cx="61" cy="58" r="4" fill={accent} />}
    </>}
  </svg>;
}
