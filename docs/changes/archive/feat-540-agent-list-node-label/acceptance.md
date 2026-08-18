# feat-540 — 验收报告

> 对齐: `docs/changes/feat-540-agent-list-node-label/spec.md` v2
>
> Validation snapshot: `f6c4c223d5f0a803cfdfeae806e2f48b5e7384a7 → fc0afe9f9` (unit/feat-540 HEAD)

## Verdict

**pass**

**Highest Required Action**: pass

## 用户旅程体验

本次验收在已部署的 worktree 真栈上进行(未按 reviewer skill 惯例重启常驻服务,因 orchestrator 已预搭现场并指示直接使用):

1. **桌面端主路径**:登录 nano/nano1234 → 打开 `/settings/agents` 首页 → 左侧列表 5 个 agent 条目全部右缘显示归属设备名,未选中文字浅色可读;点击 `e2e` 进入详情页,左栏同款列表同样标注且选中条目有清晰 outline;打开 `/settings/agents/new`,左栏依旧标注。
2. **别名一致性**:Account 页显示第二台节点别名为「工作室」,air-planner / air-researcher / migration-verification-20260816 三条目右缘均显示「工作室」,与 Account 页一致。
3. **离线边界**:kill `.gateway-air.pid` 中的 gateway 进程后刷新 `/settings/agents`,air 三个条目的头像角标由绿转灰,但右缘「工作室」依旧显示。
4. **移动端**:390×844 viewport 打开 `/settings/agents`,每条右上方显示设备名,chevron 位于设备名下方。

全部旅程均通过真实 Chromium 浏览器执行并截图;同屏未发现报错、布局错位或相邻功能损坏。

## Reference Artifacts Reviewed

对齐 design.md `## 前端原型` 中的 must-match 契约:

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype.html 桌面行 | 右缘设备名右对齐、与第二行同基线、明度阶梯(显示名 0.86 / ID 0.64 / 设备名 0.55) | review-desktop-index.png | desktop 普通/选中 | match |
| prototype.html 移动行 | 设备名占原圆点位,chevron 在其下 | review-mobile-index.png | mobile 390×844 | match |
| prototype.html 颜色修复 | 桌面首页未选中显示名 0.86、ID 0.64;选中态 ID 0.70 | review-desktop-index.png | desktop 未选中/选中 | match(经 computed style 复核) |
| prototype.html 状态表达 | 头像状态角标一致;右缘无独立圆点 | review-desktop-index.png / M1-impl/desktop-offline-node.png | desktop 在线/离线 | match |

## 问题清单

无。

## 验收标准覆盖

### Requirement: Agents 列表每个条目右缘标注归属设备 — 组内结论: pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 多设备下逐条标注 | spec.md / prototype.html | 桌面端打开首页、详情页、新建页,观察三处左栏条目 | review-desktop-index.png | pass | e2e/e2e-peer 标 `wt-unit-feat-540-38743`;air 三个 agent 标 `工作室`;设备名右对齐 |
| 设备设置别名时显示别名 | spec.md | Account 页确认别名后,核对列表显示 | review-desktop-index.png | pass | 与 Account 页一致显示「工作室」 |
| 设备离线仍显示归属 | spec.md | kill gateway-air 后刷新首页 | M1-impl/desktop-offline-node.png | pass | air agent 头像角标变灰,`工作室` 仍显示 |
| 移动端同样标注 | spec.md / prototype.html | 390×844 viewport 打开首页 | review-mobile-index.png | pass | 设备名在条目右上,chevron 在其下 |

### Requirement: 标注不牺牲条目既有信息与状态表达 — 组内结论: pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 名字两行与行高不被挤压 | spec.md / design 决策 3 | 观察列表条目;检查 DOM 行高与文本样式 | review-desktop-index.png, review-mobile-index.png | pass | 行高 52px;显示名 13px oklch(0.86), ID 11px mono oklch(0.64), 设备名 11px sans oklch(0.55);设备名仅自身超长时截断 |
| 在线状态由头像角标表达 | spec.md / prototype.html | 观察条目头像与右缘 | review-desktop-index.png / M1-impl/desktop-offline-node.png | pass | 头像右下绿/灰角标;右缘无独立状态圆点 |

### Requirement: 三处列表条目文字在深色侧栏上清晰可读 — 组内结论: pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 桌面端首页列表未选中条目可读 | spec.md / prototype.html | 桌面端查看首页列表 | review-desktop-index.png | pass | 显示名 oklch(0.86)、ID oklch(0.64), 在深底上可读 |
| 选中与 hover 条目可读性一致 | spec.md / prototype.html | 详情页选中条目;hover 条目;复核 computed style | review-desktop-index.png | pass | 选中: outline oklch(0.4 0.08 180) 1px + bg oklch(0.31 0.015 240);hover bg oklch(0.28 0.012 240);文字可读 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本 unit 仅涉及 IM 前端展示层,未改变跨包架构。
- [x] `docs/specs/im/agents-nodes.md`（长青行为契约层）：需要更新。本 unit 已产出 `docs/changes/feat-540-agent-list-node-label/specs/im/agents-nodes.md` delta-spec,需由 orchestrator §7.1 收尾归并至 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。未触及架构红线或项目级约定。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：无需更新。未改动文档体系本身。
