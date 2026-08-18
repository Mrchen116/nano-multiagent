# Verification Report: feat-540

> Validation snapshot: `f6c4c22d5 → a14c8b750`
> Mode: full
> Delta range: `remotes/origin/main...HEAD`
> Focus issues: N/A

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 |
| Correctness | covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- **Milestone 完成度**: feat-540-M1 全部 9 条退出标准均有实现或证据：
  - 1-2 多设备逐条标注 / 别名：由 `AgentRow` + `nodeLabelOf` 实现，真栈截图 `desktop-index.png`、`desktop-account.png` 可复查。
  - 3 无归属留空：产品内不可达，降级为 `agent-row.test.tsx` 单测锁定不渲染路径。
  - 4 移动端标注：由 `AgentRow` 移动分支实现，真栈截图 `mobile-index.png` 可复查。
  - 5 名字两行 / 行高 / 状态角标：`AgentRow` 保留 `min-h-[52px]`、名字 `truncate`、设备名 `shrink-0 max-w-[92px]`、以 `Avatar` status 取代右缘圆点。
  - 6 原型 must-match：真栈截图覆盖超长 ID、别名、离线节点。
  - 7 首页深底深字修复：`AgentRow` 桌面普通态显示名 `0.86` / ID `0.64`，选中态对应浅色，三处复用同一组件。
  - 8 测试全绿：`cd src/IM/frontend && npm test -- src/features/settings/agents --run` → 125 passed。
  - 9 浏览器截图证据：已存 `M1-impl/screenshots/`。
- **Spec 覆盖**: 全部 2 条 Requirement + 8 条 Scenario 在代码中均有实现（含用户裁决删除的「无归属留空」Scenario 的降级单测）。
- **Prototype / Reference 覆盖**: design.md 前端原型的 4 条 `must-match` 契约均投影到实现与 M1 证据。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| **Req: Agents 列表每个条目右缘标注归属设备** | | | |
| 多设备下逐条标注 | `agent-row.tsx:24-28` (`nodeLabelOf`) + `agent-row.tsx:111-128` (渲染) | `agent-row.test.tsx`、`agents-list-page.test.tsx:79-86`、`agents-rail-desktop.test.tsx:65-74` | covered |
| 设备设置别名时显示别名 | `agent-row.tsx:27` (`node.alias \|\| node.node_name`) | `agent-row.test.tsx:31-34` | covered |
| 设备离线仍显示归属 | `agent-row.tsx:111-128`（设备名渲染与 `status` 无关） | `M1-impl/screenshots/desktop-offline-node.png`（reviewer 证据） | covered |
| 移动端同样标注 | `agent-row.tsx:111-119` | `agent-row.test.tsx:118-134`、`mobile-index.png` | covered |
| **Req: 标注不牺牲条目既有信息与状态表达** | | | |
| 名字两行与行高不被挤压 | `agent-row.tsx:54` (`min-h-[52px]`)、`agent-row.tsx:85-109`（名字 `truncate`）+ `agent-row.tsx:122` (`shrink-0 max-w-[92px]`) | `agent-row.test.tsx:91-96` | covered |
| 在线状态由头像角标表达 | `agent-row.tsx:79-84` (`Avatar status`)，右缘无圆点 | `agent-row.test.tsx:68-74` | covered |
| **Req: 三处列表条目文字在深色侧栏上清晰可读** | | | |
| 桌面端首页列表未选中条目可读 | `agent-row.tsx:86-95`（普通态 `0.86`/`0.64`） | `agent-row.test.tsx:76-90`、`agents-rail-desktop.test.tsx:48-63` | covered |
| 选中与 hover 条目可读性一致 | `agent-row.tsx:58-75`（active/hover 背景与文字色），三处复用 `AgentRow` | 截图证据 + 组件渲染测试 | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1：抽出共享 `AgentRow`，两处行实现合一 | 是 | `agents-list-page.tsx:118-125`、`agents-rail-desktop.tsx:62-71` 均渲染 `<AgentRow>`；原内联行实现已删除 |
| 决策 2：设备名 = 前端 join `/im/v1/nodes`，零后端改动，优先级 `alias \|\| node_name` | 是 | `agent-row.tsx:24-28`、`agents-rail-desktop.tsx:18-19` 新增 `listNodes` query；后端接口未改动 |
| 决策 3：三者视觉规范（明度阶梯、设备名右对齐同基线、截断只截自己） | 是 | `agent-row.tsx:86-128` 的 Tailwind token 与 design.md 表一致；桌面设备名 `self-end pb-[1px]`，移动设备名占原圆点位 |
| 决策 4：颜色修复 = 首页侧栏统一到 rail 正确值，移动端不动 | 是 | 桌面普通态显示名 `0.86`、ID `0.64`（修复前 `0.18`/`0.50`）；移动端显示名保持 `0.18` |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 桌面行：右缘设备名（右对齐、与第二行同基线、明度阶梯） | M1 退出标准 1、5、6 | `agent-row.tsx:120-128` | `M1-impl/screenshots/desktop-index.png`、`desktop-detail.png`、`desktop-create.png` | covered |
| 移动行：设备名占原圆点位 + 「›」在其下 | M1 退出标准 4 | `agent-row.tsx:111-119` | `M1-impl/screenshots/mobile-index.png` | covered |
| 首页行文字色修复（0.86/0.64 + 选中态） | M1 退出标准 7 | `agent-row.tsx:86-106` | `M1-impl/screenshots/desktop-index-hover.png` | covered |
| 头像状态角标两组件一致；右缘无独立圆点 | M1 退出标准 5 | `agent-row.tsx:79-84`；无 `rounded-full` 状态 dot | `M1-impl/screenshots/desktop-index.png` | covered |

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

- `docs/changes/feat-540-agent-list-node-label/prototype.html:239` 视觉规范表中「移动端 · 显示名」仍写 `oklch(0.14 0.01 240)`，与 design.md 决策 3 及实现采用的 `0.18` 不一致，建议改为 `oklch(0.18 0.01 240)` 以免 reviewer 对照时困惑。
- `src/IM/frontend/src/features/settings/agents/agents-rail-desktop.test.tsx:65-74` 设备名单测只断言了 active 行（Planner），可补充对 offline 行（Researcher）的设备名断言，与 M1 退出标准 2 形成更直接的回归绑定。
- `src/IM/frontend/src/features/settings/agents/agent-row.test.tsx` 未覆盖 active 态移动端、hover 态以及 `Avatar` status 的视觉落点，可作为后续加固补充；当前由 reviewer 截图与 `statusOf` 单测兜底。
