# feat-438 — 验收报告

> 对齐: `docs/changes/feat-438-im-group-settings/spec.md` 验收标准

## Verdict

**pass**

- Highest Required Action: `pass`
- Issues: blocking 0 / major 0 / minor 1（见 Side Findings）
- Review Round: 1
- Date: 2026-06-26

---

## 用户旅程体验

### 环境

- IM 后端: uvicorn 127.0.0.1:50345
- Vite dev server: 127.0.0.1:50346 (proxy → IM)
- 测试账号: nano / nano1234
- 种子数据: 4 个 agent（策划师/撰写者/评审员/架构师）直接 SQLite 写入（无 Gateway 可用）

### 旅程 A — PC 端主路径（Config 入口 + 群设置完整操作）

覆盖 Scenarios 1、3、4、5、6、7、8、9、10、11

1. 打开"研发小组"群聊 → 点 Config（⚙）→ GroupSettings 右侧 drawer 展开，URL 不变，不跳 agent 页 ✓
2. 改群名 "测试群组" → "技术研讨组 V2"，保存后标题栏 + 侧边栏同步更新 ✓
3. 清空群名 → 红框 + "Group name can't be empty" + Save 灰态 ✓
4. 成员列表：Test User（Creator/You）+ 策划师 + 评审员 全部呈现 ✓
5. 点击"策划师"行 → 跳转 /settings/agents/planner ✓
6. 移除"评审员" → 弹内联确认 → 确认后成员列表 Members · 2，用户停留群内 ✓
7. 继续移除到 0 agent → Members · 1（只剩 Test User），无任何"没人回"提示，Config 按钮仍在 ✓
8. 点"Add members" → 候选列表显示策划师 + 评审员（已移除的重新可选）→ 选策划师 → Add(1) → Members 增加 ✓
9. 再次"Add members" → 策划师已在群，候选排除策划师 ✓
10. 全部 agent 加入群后"Add members" → "No agents available to add" 空态 ✓

### 旅程 B — PC 端 direct chat Config 回归

覆盖 Scenario 2

1. 在 Agents 页找到架构师 → 点"Open chat ↗"创建 direct-agent 会话 → 进入聊天
2. 点 Config（⚙）→ 导航到 /settings/agents/architect，与变更前一致 ✓

### 旅程 C — 解散群（主 + 取消）

覆盖 Scenarios 12、13

1. 打开某群设置 → "Dissolve group" → 弹"permanently deleted" 确认 → 点 Cancel → 群、成员、聊天记录不变 ✓
2. 再进群设置 → "Dissolve group" → 确认 → URL 跳回 /chat，侧边栏该群消失 ✓

### 旅程 D — 移动端（375px）完整群管理

覆盖 Scenario 14

1. 浏览器调整为 375 × 812；页面正常自适应成移动布局（底部导航栏、紧凑聊天头）
2. UI 创建"移动端测试群"（策划师 + 撰写者，3 成员）→ 移动端聊天界面显示 ‹ Back + 群名 + ⚙
3. 点 Config（⚙）→ 全屏面板打开，"Group settings" 标题 + "Manage" 右上按钮，"‹ Back" 左上返回 ✓
4. 点 Rename → 内联文本框，填入"移动端测试群 v2" → Save → 标题栏同步更新 ✓
5. 点 Manage → "Manage members" 标题 + "Done" 右上 → 点撰写者行的 Remove → 内联确认 → 确认后 Members · 2 ✓
6. 点"Add members" → 全屏候选页，显示撰写者/评审员/架构师（策划师已在群排除）→ 勾选撰写者 → Add 1 → Members · 3 ✓
7. 点"Dissolve group" → 确认 → URL 跳 /chat，群从侧边栏消失 ✓
8. 布局全程未破版，375px 下各元素正确自适应 ✓

---

## 问题清单

无 blocking / major 问题。Minor 问题见 Side Findings。

---

## 验收标准覆盖

### Requirement: 群聊配置入口指向群设置，不再错跳 agent 配置页 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 群聊点配置打开群设置 | spec.md Scenario 1 | 旅程 A：点群内 Config，观察 URL + 面板 | URL 不变，GroupSettings drawer 展开，dialog "Group settings" 出现 | **pass** | |
| direct chat 点配置仍进 agent 配置页 | spec.md Scenario 2 | 旅程 B：用"Open chat ↗"创建 direct-agent 会话，点 Config | 导航到 /settings/agents/architect | **pass** | API 直接建的会话 type=group，排除作为测试数据；须用 UI 建的 direct-agent 会话才还原正确类型 |

### Requirement: 在群设置里修改群名 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 改群名成功 | spec.md Scenario 3 | 旅程 A：改名 Save 后观察标题栏 + 侧边栏 | "技术研讨组 V2" 在 header + sidebar + panel 同步显示 | **pass** | |
| 群名不能为空 | spec.md Scenario 4 | 旅程 A：清空名字观察 Save 状态 + 提示 | 红框 + "Group name can't be empty" + Save button 无响应 | **pass** | |

### Requirement: 查看群成员并可进入某成员 agent 的配置页 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 成员列表展示全部成员 | spec.md Scenario 5 | 旅程 A：打开群设置面板，扫描成员列表 | Test User（Creator/You）+ 策划师 + 评审员 全部呈现 | **pass** | |
| 点 agent 成员进其配置页 | spec.md Scenario 6 | 旅程 A：点策划师行 | 导航到 /settings/agents/planner | **pass** | |

### Requirement: 移除群里的 agent 成员 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 移除一个 agent 成员 | spec.md Scenario 7 | 旅程 A：移除评审员，观察列表 + 停留位置 | Members · 2，群界面保持，无页面跳转 | **pass** | |
| 移除到一个 agent 不剩（边界） | spec.md Scenario 8 | 旅程 A：连续移除至 Members · 1 | 群存在，成员列表仅 Test User，无任何"没人回"提示，Config 按钮仍可用 | **pass** | |

### Requirement: 向群里添加 agent 成员 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 添加一个 agent 进群 | spec.md Scenario 9 | 旅程 A：Add members → 选策划师 → Add(1) | Members 计数递增，策划师出现在列表 | **pass** | |
| 已在群里的 agent 不重复出现在候选 | spec.md Scenario 10 | 旅程 A：Add members 候选列表检查 | 当前群成员（策划师）不出现在候选 | **pass** | |
| 没有可添加的 agent（空态） | spec.md Scenario 11 | 旅程 A：所有 agent 入群后打开 Add members | "No agents available to add" 空态提示 + 图标 | **pass** | |

### Requirement: 解散群 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 解散群成功 | spec.md Scenario 12 | 旅程 C：确认解散 | URL 跳 /chat，群从侧边栏消失 | **pass** | |
| 取消解散 | spec.md Scenario 13 | 旅程 C：取消解散 | 群、Members · 5、聊天记录均无变化 | **pass** | |

### Requirement: 移动端可用 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 移动端完成群管理 | spec.md Scenario 14 | 旅程 D：375px 改名 + 移除成员 + 解散 | 全屏 GroupSettings 在 375px 正常展示；改名/移除/添加/解散均可完成；布局不破版 | **pass** | 移动端 manage 模式 ✕ 按钮视觉见 Side Findings |

---

## Side Findings

**SF-1（minor）** 移动端 manage 模式 ✕ 按钮视觉透明

- 在 375px 进入"Manage members"模式后，各 agent 行的移除按钮（✕）存在于 DOM 与无障碍树（playwright 抓到 `button "Remove 策划师"`），但截图中视觉不可见（无红色圆圈或移除图标）。点击正确区域确能触发内联确认，功能正常。仅为视觉 polish 问题，不影响本 unit 任何 Scenario 的可完成性。
- 建议：后续 polish unit 检查 mobile manage mode ✕ 按钮的 CSS visibility。
- 不立 issue（severity minor，不影响验收）

**SF-2（minor / out-of-unit）** `/im/v1/agents/{id}/capabilities` 503

- 进入 agent 配置页时，前端调用 capabilities 接口返回 503。原因：无 Gateway 进程运行。与本 unit 无关，属现有已知限制（agent 能力探测依赖 Gateway），不立 issue。

---

## 上层文档同步

- [ ] `SPEC.md`（跨包顶点架构）：**无需更新**（本 unit 只改 IM frontend + IM 后端一个新端点，不影响跨包架构描述）
- [ ] `docs/specs/im/spec.md`（IM 长青契约层）：**需要更新**（新增 `POST /conversations/{id}/participants` 端点；群设置配置入口路由行为；由 orchestrator §7.0 收尾归并）
- [ ] `AGENTS.md` / `CLAUDE.md`：**无需更新**
- [ ] `docs/SPEC_GUIDE.md`：**无需更新**

> 长青契约层写回由 orchestrator 收尾归并处理，reviewer 仅标记此处需同步。

---

## 用户旅程脚本索引（User Journeys Exercised）

| 旅程 | 覆盖 Scenarios | 入口 |
|---|---|---|
| A — PC 主路径（Config + 群设置完整操作） | 1, 3, 4, 5, 6, 7, 8, 9, 10, 11 | 浏览器 1280px |
| B — direct chat Config 回归 | 2 | 浏览器 1280px（用"Open chat ↗"建 direct-agent 会话） |
| C — 解散群（主 + 取消） | 12, 13 | 浏览器 1280px |
| D — 移动端完整群管理 | 14 | 浏览器 375px |
