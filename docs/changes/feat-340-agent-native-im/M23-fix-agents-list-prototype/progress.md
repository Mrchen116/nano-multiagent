# M23: Fix Agents List Prototype Alignment

## What Was Done

### 1. Rewrote `agents-list-page.tsx` to match prototype `AgentListView`

The original `AgentsListPage` used light gray background (`oklch(0.93 0.007 240)`) and `Link` elements for rows, which deviated significantly from the prototype `im-settings-page.jsx:12-75`.

**Key changes:**
- **Desktop sidebar**: Dark background `oklch(0.24 0.012 240)`, fixed width 240px, border `oklch(0.29 0.010 240)`
- **Mobile**: Light background `oklch(0.93 0.007 240)`, full width
- **Agent rows**: Changed from `<Link>` to `<button>` (matching prototype), with:
  - Border radius 12px (`rounded-xl`)
  - Active state: background `oklch(0.31 0.015 240)`, outline `oklch(0.40 0.08 180)`
  - Hover state: background `oklch(0.28 0.012 240)` (desktop) / `oklch(0.90 0.006 240)` (mobile)
  - Active text color: white (`#fff`)
  - Min height 52px
- **Status dot**: Online `oklch(0.55 0.18 145)`, Offline `oklch(0.45 0.01 240)`
- **New button**: Desktop dark bg `oklch(0.30 0.012 240)`, Mobile green bg `oklch(0.52 0.14 180)`
- **Header**: Desktop uppercase "Agents" with tracking, Mobile centered h1 with absolute-positioned + New
- **Font sizes**: Name 13px/15px (desktop/mobile), Sub 11px mono/12.5px (desktop/mobile)
- **Avatar**: 32px/38px (desktop/mobile), green bg `oklch(0.52 0.14 180)`
- **Chevron**: Mobile only `›` indicator

### 2. Updated tests

- `agents-list-page.test.tsx`: Updated selectors (`Link` -> `button`), href expectations, label text queries
- `agents-i18n-switch.test.tsx`: Updated heading role query to text query
- `router.test.tsx`: Updated to handle multiple "Agents" text occurrences

---

## Prototype Comparison Checklist

| Aspect | Prototype (`im-settings-page.jsx`) | Implementation | Match |
|--------|-----------------------------------|----------------|-------|
| **Sidebar width** | 240px | 240px | ✅ |
| **Sidebar bg (desktop)** | `oklch(0.24 0.012 240)` | `oklch(0.24 0.012 240)` | ✅ |
| **Sidebar bg (mobile)** | `oklch(0.93 0.007 240)` | `oklch(0.93 0.007 240)` | ✅ |
| **Border color** | `oklch(0.29 0.010 240)` | `oklch(0.29 0.010 240)` | ✅ |
| **Row border radius** | 12px | 12px (`rounded-xl`) | ✅ |
| **Row active bg** | `oklch(0.31 0.015 240)` | `oklch(0.31 0.015 240)` | ✅ |
| **Row active outline** | `oklch(0.40 0.08 180)` | `oklch(0.40 0.08 180)` | ✅ |
| **Row hover bg** | `oklch(0.28 0.012 240)` (desktop) | `oklch(0.28 0.012 240)` | ✅ |
| **Row hover bg (mobile)** | `oklch(0.90 0.006 240)` | `oklch(0.90 0.006 240)` | ✅ |
| **Active text color** | `#fff` white | `#fff` white | ✅ |
| **Status dot online** | `oklch(0.55 0.18 145)` | `oklch(0.55 0.18 145)` | ✅ |
| **Status dot offline** | `oklch(0.45 0.01 240)` | `oklch(0.45 0.01 240)` | ✅ |
| **New button (desktop)** | `oklch(0.30 0.012 240)` bg | `oklch(0.30 0.012 240)` | ✅ |
| **New button (mobile)** | `oklch(0.52 0.14 180)` bg | `oklch(0.52 0.14 180)` | ✅ |
| **Header title (desktop)** | 11px, uppercase, tracking 0.08em | 11px, uppercase, tracking-[0.08em] | ✅ |
| **Header title (mobile)** | 17px, bold, centered | 17px, bold, centered | ✅ |
| **Avatar size (desktop)** | 32px | 32px (h-8 w-8) | ✅ |
| **Avatar size (mobile)** | 38px | 38px (h-[38px] w-[38px]) | ✅ |
| **Avatar bg** | `oklch(0.52 0.14 180)` | `oklch(0.52 0.14 180)` | ✅ |
| **Name font (desktop)** | 13px, weight 600 | 13px, font-semibold | ✅ |
| **Name font (mobile)** | 15px, weight 600 | 15px, font-semibold | ✅ |
| **Sub font (desktop)** | 11px, mono | 11px, font-mono | ✅ |
| **Sub font (mobile)** | 12.5px | 12.5px | ✅ |
| **Chevron (mobile)** | `›` | `›` | ✅ |
| **Row element type** | `<button>` | `<button>` | ✅ |
| **Padding (desktop)** | 14px 12px 10px header, 6px 8px body, 9px 10px row | Same | ✅ |
| **Padding (mobile)** | 10px 16px 12px header, 8px 10px body, 12px 10px row | Same | ✅ |

---

## Evidence

### Screenshots

- `evidence/m23-agents-desktop.png` — Desktop 1440x900, dark sidebar 240px with agent rows
- `evidence/m23-agents-mobile.png` — Mobile 375x812, light background with centered title

### Build Verification

```bash
cd src/IM/frontend && npm run build
# dist/assets/index-*.js contains: oklch(0.24, oklch(0.31, oklch(0.28
# dist/assets/index-*.css no longer contains old .im-agents-list rules
```

### Test Results

```
Test Files  52 passed (52)
     Tests  292 passed (292)
```

---

## Exit Criteria Verification

| Criterion | Status | Notes |
|-----------|--------|-------|
| (a) sidebar 宽 240px 背景 dark | ✅ Verified | Desktop screenshot shows 240px dark sidebar `oklch(0.24 0.012 240)` |
| (b) 每行圆角 12px 卡片式，hover/active 状态正确 | ✅ Verified | Rows use `rounded-xl` (12px), active has outline + dark bg, hover changes bg color |
| (c) status dot 正确 | ✅ Verified | Online: `oklch(0.55 0.18 145)` green, Offline: `oklch(0.45 0.01 240)` gray |
| (d) 字体/间距/按钮风格与原型一致 | ✅ Verified | All font sizes, weights, padding, button colors match prototype exactly |

---

## Files Modified

1. `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx` — Complete rewrite to match prototype
2. `src/IM/frontend/src/features/settings/agents/agents-list-page.test.tsx` — Updated selectors
3. `src/IM/frontend/src/features/settings/agents/agents-i18n-switch.test.tsx` — Updated heading query
4. `src/IM/frontend/src/app/router.test.tsx` — Updated Agents text query

## Notes

- The `AgentsRailDesktop` component in `agent-detail-page.tsx` already matched the prototype closely. This M23 ensures the standalone `AgentsListPage` (shown at `/settings/agents` with no agent selected) uses the same visual treatment.
- No CSS file changes were needed because all styles are inline (matching the prototype's inline style approach).
