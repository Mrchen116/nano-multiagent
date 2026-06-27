# feat-430 — 验收报告

> 对齐: docs/changes/feat-430-im-slash-skill-picker/spec.md 验收标准

---

# Round 1 — 2026-06-27

**unit_id**: feat-430
**Branch reviewed**: unit/feat-430
**Reviewer**: change-reviewer (Round 1)
**Date**: 2026-06-27

## Verdict

**fail**
**Highest Required Action**: fix-implementation
**Issues**: blocking: 1, major: 0, minor: 0

## 环境信息

| 服务 | 地址 | 备注 |
|---|---|---|
| IM | http://127.0.0.1:62855 | ephemeral port |
| Vite dev server | http://127.0.0.1:63065 | 前端开发服务 |
| Gateway | auto-bind 到 http://127.0.0.1:62855 | --foreground --auto-bind |

**构建产物指纹**: `index-BynY8evf.js`，包含 unit 关键 marker：`slashDismissed`、`buildSlashSkills`、`fromAgents`。指纹核验通过，前端代码为本 unit 构建。

**测试账号**: nano / nano1234（plato whitelist: 3 skills，hume whitelist: 6 skills）

## 用户旅程体验

**旅程 1 — 单聊 slash picker 主路径**

在 plato-direct 单聊输入框输入 `/`，picker 立即弹出，包含 `/stop` 和一批 skills。**但 skills 数量为 52 个而非 plato 实际已启用的 3 个**（change-spec-author、change-design-author、change-orchestrator）。ArrowDown 导航、Enter 确认、鼠标点击均工作正常；选中 skill 后输入框补入 `/skill:name `（末尾有空格）。Escape 关闭、点击面板外关闭均正常，已输入的 `/` 文本保留。前缀过滤（输入 `/change` 只显示 3 个 change- 开头的 skills）、无匹配空态提示（"No matching commands or skills"）均正常。整体交互体验流畅，唯一严重问题是 skills 来源范围错误。

**旅程 2 — 群聊 slash picker**

在 Test Group（plato + hume 两个 agent）输入 `/`，picker 弹出，显示 /stop + 52 个 skills；每个 skill 均标注 "from plato, hume"（正确，因为 plato 与 hume 使用同一路径的 capabilities skills）。同路径 skill 合并逻辑和来源标注正确。但由于 whitelist 交集未生效，实际应展示 plato (3 个) ∪ hume (6 个) ≈ 9 个，实际展示 52 个。

**旅程 3 — 群聊 /stop 及幂等测试**

在群聊中多次发送裸 `/stop`（无 @mention），均无 agent 报错回复，消息正常显示在聊天流（幂等行为正确）。通过 @plato 触发 plato 计数任务（1-200），但任务在约 8 秒内自然完成，未能在 plato 活跃 run 中发出 `/stop`，故群聊 /stop 停止活跃 run 和 MENTION bypass 两个场景未能可靠验证。

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 | **blocking** | 单聊/群聊 slash picker 展示全量 52 个 skills，而非 agent 已启用 whitelist 中的 skills（plato 应为 3 个，群聊应为约 9 个） | fix-implementation |

## 验收标准覆盖

### Requirement: 输入 `/` 弹出 slash 候选面板 — 组内结论: **fail**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 单聊里敲 `/` | spec.md R1-S1；澄清记录 Q1 | 旅程 1：plato-direct 单聊输入 `/`，观察面板内容 | `J1-01-slash-picker-appeared.png`；网络请求返回 `GET /agents/plato/config?source=mirror` 中 `"skills":[]` | **fail** | 面板弹出机制正常，但内容错误：显示全量 52 个 skills 而非已启用的 3 个。见 Issue #1。 |
| 群聊里敲 `/` | spec.md R1-S2；澄清记录 Q5/Q6 | 旅程 2：群聊（plato+hume）输入 `/` | `J4-01-group-slash-opened.png` | **fail** | 同一 whitelist bug，群聊应显示 plato ∪ hume whitelist（约 9 个），实际显示全量 52 个。 |
| 输入框中间出现 `/` 不触发 | spec.md R1-S3 | 未显式测试 | — | **inconclusive** | 因 Issue #1 优先处理未覆盖此场景。Fix-implementation 后补验。 |

### Requirement: slash 面板支持键盘与鼠标导航选中 — 组内结论: **pass**（inconclusive 1项）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用方向键选择并回车确认 | spec.md R2-S1 | 旅程 1：开 picker 后 ArrowDown→ Enter | `J1-03-arrow-down-highlight.png`，`J1-04-enter-selected.png` | **pass** | 高亮移动正常，Enter 后输入框变为 `/skill:change-spec-author `，面板关闭，焦点保留。 |
| 候选超出可视区时高亮项滚动可见 | spec.md R2-S2 | 旅程 2：有 52 个候选时持续 ArrowDown | 滚动行为在交互中观察到；未能截到清晰边界截图 | **inconclusive** | 视觉上高亮随导航滚动，但未能取到"滚到视区外→自动追入"的精确证据。Fix-implementation 后建议专门截图验证。 |
| 用鼠标点击候选项选中 | spec.md R2-S3 | 旅程 1：hover 并点击 skill 候选项 | `J1-05-mouse-click-selected.png` | **pass** | 点击后输入框填入对应 `/skill:name `，面板关闭，无需点两次。 |
| 按 Esc 或点击面板外关闭面板 | spec.md R2-S4 | 旅程 1：Escape 关闭；另次点击外部 | `J1-06-escape-closed.png`，`J1-07-click-outside.png` | **pass** | 两种关闭方式均正常，`/` 文本保留，焦点不丢失。 |

### Requirement: skill 选中后补成正确的 slash 格式 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 选中 skill 后补 `/skill:name ` | spec.md R3-S1；澄清记录 Q9 | 旅程 1：picker 选中 skill → 检查输入框内容 | `J1-04-enter-selected.png`（内容为 `/skill:change-spec-author `） | **pass** | 格式正确（`/skill:name ` 末尾有空格）。所选 skill 超出 plato 正确 whitelist 范围是 Issue #1 的表现，但格式机制本身正确。 |

### Requirement: 群聊 skills 按 skill 实际路径区分同一性并标注来源 — 组内结论: **pass**（inconclusive 1项）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同路径 skill 合并显示 | spec.md R4-S1；澄清记录 Q7 | 旅程 2：群聊 picker 检查 skill 行数和来源标注 | `J4-02-group-skills-from-agents.png`（每个 skill 显示 "from plato, hume"） | **pass** | 同路径 skill 合并为一行且来源标注正确。显示范围错误（52 个）是 Issue #1，合并逻辑本身正常。 |
| 不同路径的同名 skill 分开显示 | spec.md R4-S2；澄清记录 Q7 | 未测试 | — | **inconclusive** | 测试环境中 plato 和 hume 使用相同 SKILL.md 路径，无法构造不同路径同名 skill 场景。fix-implementation 后建议准备专用测试配置。 |

### Requirement: slash 面板支持前缀过滤 — 组内结论: **pass**（inconclusive 1项）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 输入 `/pr` 过滤出匹配的 skill | spec.md R5-S1；澄清记录 Q10 | 旅程 1：输入 `/change` 后观察过滤结果 | `J1-08-filter-change.png`（只显示含 "change" 前缀的 3 个 skills，`/stop` 不显示） | **pass** | 前缀过滤正常，commands 和 skills 一视同仁参与过滤。 |
| 输入 `/xyz` 无匹配 | spec.md R5-S2 | 旅程 1：输入 `/xyz` | `J1-09-no-match.png`（显示 "No matching commands or skills"） | **pass** | 空态提示文案清晰，不阻塞用户继续输入。 |
| 编辑已补入的 `/skill:` 文本时重新过滤纠错 | spec.md R5-S3 | 未显式测试 | 间接观察：补入后删字时 picker 有重新出现迹象 | **inconclusive** | 防止 `/skill:` 前缀影响过滤是关键边界，fix-implementation 后建议专门验证删减已补入文本时的 picker 重开行为。 |

### Requirement: 发送后行为与普通消息一致 — 组内结论: **fail**（inconclusive 3项）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 选中 skill 后继续输入并发送 | spec.md R6-S1 | 旅程 1：picker 选中 skill → 追加文本 → Enter 发送 | `J3-01-message-sent.png`（消息出现在聊天流） | **pass** | 消息作为普通用户消息发出，出现在聊天流，行为与普通消息一致。 |
| 群聊里发送 `/stop`（agent 正在运行） | spec.md R6-S2 | 旅程 3：@plato 触发 run → picker 选 /stop → 观察 | `J7-04-during-run.png`（plato 运行中），`J7-05-after-stop.png`（/stop 后无 "已停止" 提示） | **inconclusive** | plato 计数任务（1-200）在约 8s 内自然完成，/stop 命中已结束状态；未能在 plato 活跃 run 期间精确发出 /stop。需更长耗时的运行任务才能可靠验证。 |
| 群聊里裸 `/stop` 不受 MENTION 设置影响 | spec.md R6-S3；澄清记录 Q12 | 旅程 3：plato 在运行（MENTION 策略）→ 裸 /stop | `J7c-current-group-state.png`（plato 状态未确认停止；无 "已停止" 提示） | **inconclusive** | 因 timing 问题，/stop 均在 plato run 已完成后发出；无法确认 MENTION bypass 是否已在后端实现（spec.md 澄清 Q11/Q12 明确 in-scope）。 |
| 群聊里 `/stop` 对未在运行的 agent 幂等 | spec.md R6-S4 | 旅程 3：无活跃 run 时发送多次 /stop | `J7c-current-group-state.png`（聊天流有 4 个 /stop 消息，无 agent 回复或报错） | **pass** | 幂等行为正确，不在运行的 agent 不产生报错或副作用。 |

---

## Issues

### Issue 1 — 白名单交集失效：picker 展示全量 52 个 skills 而非已启用 skills

- **Severity**: blocking
- **Regression Relation**: direct（直接违反 R1 核心验收标准）
- **Recommended Action**: fix-implementation
- **Action Rationale**: whitelist 交集是 picker 的核心语义，前端调用的 endpoint 未能返回正确的 skills 白名单，导致"空白名单 = 全部可用"回退触发，picker 内容与用户期望严重不符。

**Symptom**: 在 plato 单聊输入 `/`，picker 显示 52 个 skills；期望为 plato 已启用的 3 个（change-spec-author、change-design-author、change-orchestrator）。

**Reproduction**:
1. 进入 plato-direct 单聊
2. 输入框输入 `/`
3. picker 出现 52 个 skills（而非 3 个）

**Evidence**:
- 网络请求确认：前端使用 `GET /im/v1/agents/plato/config?source=mirror`，返回 `{"skills": []}` （空数组）
- 正确端点 `GET /im/v1/agents/plato/config`（无 `?source=mirror`）返回 `{"skills": ["change-spec-author", "change-design-author", "change-orchestrator"]}`
- `?source=mirror` 参数返回 IM 本地镜像（gateway 推送同步过来的副本），该镜像当前不包含 skills 字段
- design.md Decision 2 规定"前端同时拉 `getAgentConfig`（已启用白名单 `skills: string[]`）+ `getAgentCapabilities`，按 name 取交集"——但 mirror 返回空 skills 时，交集逻辑 fallback 为"空白名单=全部可用"，导致全量展示

---

## Side Findings

- **群聊 @ mention picker 未出现**: 群聊输入框输入 `@` 时，mention picker 未弹出（底部 hint 显示 "@ to mention"，暗示应有 picker 支持）。不确定是 pre-existing 问题还是本 unit 副作用。未立 issue（无法确认归属），建议单独核查。

- **群聊 MENTION bypass 未验证**: spec.md R6-S3 要求 MENTION 策略下裸 /stop 也能停止 agent（澄清记录 Q12 明确 in-scope 需修后端）。本轮因 timing 问题标 inconclusive，不排除后端改动已实现但未能测到。fix-implementation 阶段请 worker 提供专项验证证据（可在 progress.md 中记录 backend 测试路径）。

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**（feat-430 不改跨包架构）
- [ ] `docs/specs/im/spec.md`（长青行为契约层）：**建议 fix 完成后由 orchestrator §7.0 收尾时追加** — slash picker 触发行为、capabilities API 中的 location 字段透传、config?source=mirror 的 skills 字段要求
- [ ] `docs/specs/gateway/spec.md`：**建议 fix 完成后追加** — 群聊 /stop MENTION bypass 行为（若后端已实现）
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**
- [x] `docs/SPEC_GUIDE.md`：**无需更新**
