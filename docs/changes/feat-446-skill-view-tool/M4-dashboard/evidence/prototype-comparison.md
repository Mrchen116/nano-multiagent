# feat-446-M4 Prototype Comparison

Date: 2026-07-08

Purpose: durable comparison after PR #178 tightened the prototype handoff contract for change-design-author / orchestrator / worker / reviewer. `prototype.html` is the implementation handoff for M4 Agent Skills UX; this file records the corrected code-level alignment.

## Contract Summary

| Reference | Alignment level | Actual implementation / evidence | Match or accepted adaptation |
|---|---|---|---|
| Agent detail shell contains a Skills area | must-match | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx` renders `概览 / 配置 / 通道 / Skills / 会话` in the existing Agent detail page and mounts `AgentSkillsUsagePanel` under `Skills`. | Match. |
| Existing Agent Config page is preserved | must-match | `agent-detail-page.tsx` keeps Identity, Behavior, Heartbeat, Cron, Access, Workspace form content under the `Config` section. Round 4 acceptance confirms default-agent config remains visible and isolated to the right workspace. | Match. |
| Prototype top-level `Overview` / `Channels` / `Sessions` tabs | must-match shell; functional content out of scope | `agent-detail-page.tsx` implements the prototype tab shell. `概览`, `通道`, and `会话` render explicit empty-state placeholders without adding business behavior. | Match. |
| Skill list view shows name/source/state/use_count/recent trend and archived filtering | must-match | `SkillsListView` renders a table with `名字 / 来源 / 状态 / 使用次数 / 最近使用 / 趋势`, localized source badges, and `显示 archived` / `隐藏 archived`. | Match. |
| Agent heatmap view | must-match | `AgentHeatmapView` renders `使用热力图`, the 30-day heatmap from `heatmap_data`, and the prototype helper `最近 30 天 · 每格 = 1 天`. | Match. |
| Health funnel view | must-match | `HealthFunnelView` renders `自进化存活率`, `自动创建总数 / still active / use_count > 0`, `存活率`, and the lifecycle timeline table. | Match. |
| Empty and offline states | must-match | `AgentSkillsUsagePanel` separates empty `.usage.json` from query/error/offline state. M4 progress records empty and offline browser states; Round 4 acceptance keeps the non-empty real path focused. | Match. |
| `skill_view` tool call row | must-match | `tool-presentation.ts` and `tool-detail-renderers.tsx` render `查看 skill：<name>`, name, location, content, and failed state. Round 4 acceptance confirms both slash-triggered and direct `skill_view` rows complete and expand. | Match. |

## Notes For Review

- Product chrome may reuse existing Agent detail cards, spacing, and button styles, but the prototype's tab shell, Skills table structure, localized sub-tabs, health funnel, and lifecycle timeline are implementation requirements.
- Overview, Channels, and Sessions remain functional out-of-scope pages; the prototype shell is still implemented with explicit empty states so downstream implementation does not invent a different information architecture.
- Code-level verification on 2026-07-08: `npm run test -- --run src/features/settings/agents/agent-detail-page.test.tsx`; `npm run build`.
