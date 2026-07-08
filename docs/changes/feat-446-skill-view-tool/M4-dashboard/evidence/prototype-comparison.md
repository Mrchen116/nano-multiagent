# feat-446-M4 Prototype Comparison

Date: 2026-07-08

Purpose: retrospective durable comparison after PR #178 tightened the prototype handoff contract for change-design-author / orchestrator / worker / reviewer. This file does not add feat-446 scope; it records how the already implemented M4 dashboard should be judged against `prototype.html` and the existing Agent detail UX.

## Contract Summary

| Reference | Alignment level | Actual implementation / evidence | Match or accepted adaptation |
|---|---|---|---|
| Agent detail shell contains a Skills area | must-match | `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx` adds `Config` / `Skills` section buttons and renders `AgentSkillsUsagePanel` inside the existing Agent detail page. Round 4 acceptance confirms Agent Skills dashboard list/agent/health views render from real data. | Match. |
| Existing Agent Config page is preserved | must-match | `agent-detail-page.tsx` keeps Identity, Behavior, Heartbeat, Cron, Access, Workspace form content under the `Config` section. Round 4 acceptance confirms default-agent config remains visible and isolated to the right workspace. | Match. |
| Prototype top-level `Overview` / `Channels` / `Sessions` tabs | out-of-scope | Current product only needs `Config` / `Skills` for this unit. `design.md` now explicitly says those prototype tabs are placeholders / future pages. | Accepted adaptation; do not implement empty pages for this unit. |
| Skill list view shows name/source/state/use_count/recent trend and archived filtering | must-match for data and interaction; may-adapt for layout | `SkillsListView` renders skill name, state, source, last-used text, use count, trend bars, and `Show archived`. Round 4 acceptance records `change-spec-author`, `active`, `F1`, and real `use_count`. | Match. The prototype table is adapted to the product's current card/list style. |
| Agent heatmap view | must-match | `AgentHeatmapView` renders a 30-day heatmap from `heatmap_data`; Round 4 acceptance records the Agent view screenshot and real usage API payload. | Match. |
| Health funnel view | must-match | `HealthFunnelView` renders Created / Still active / Used at least once; Round 4 acceptance records the Health view screenshot. | Match. |
| Empty and offline states | must-match | `AgentSkillsUsagePanel` separates empty `.usage.json` from query/error/offline state. M4 progress records empty and offline browser states; Round 4 acceptance keeps the non-empty real path focused. | Match. |
| `skill_view` tool call row | must-match | `tool-presentation.ts` and `tool-detail-renderers.tsx` render `查看 skill：<name>`, name, location, content, and failed state. Round 4 acceptance confirms both slash-triggered and direct `skill_view` rows complete and expand. | Match. |

## Notes For Review

- The implementation is not expected to match the prototype's exact visual table chrome. It must preserve user-perceived information hierarchy and interactions while using the existing Agent detail card/list design system.
- The implementation is not expected to create Overview, Channels, or Sessions pages. Those prototype labels only expressed that Skills belongs in the Agent detail context rather than a separate settings surface.
- Earlier browser screenshots were recorded in `acceptance.md` / `progress.md` as `/tmp/...` artifacts from the original runs. This retrospective file makes the comparison durable, but it does not recreate those screenshot files.
