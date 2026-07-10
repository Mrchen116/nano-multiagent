# Verification Report: bugfix-390

## Round 2 Summary（2026-06-01）

| 维度 | 结果 |
|---|---|
| Completeness | 8/8（tasks.md 退出标准全部勾选；decode 回归单测新增） |
| Correctness | 全部 requirement 覆盖；Round 1 WARNING-1 已闭环（fixture 补 total + textContent 断言） |
| Coherence | 全部遵守；decode 层为 total 恒非 None 的单一收口点，WS/REST 兜底与之一致 |

All checks passed. Ready for PR.

---

## Round 2 核查重点

### WARNING-1 闭环：token-chip.test.tsx warn/critical fixture 补 total

已确认 `token-chip.test.tsx:22` warn 变体补 `total: 140_050` 并加 `textContent` 断言 `/140\.1k/`；`token-chip.test.tsx:30` critical 变体补 `total: 190_050` 并加 `textContent` 断言 `/190\.1k/`。`"undefined tok"` 渲染盲点已堵死。

全量 vitest：54 test files, **345 tests, 0 failed**（本地验证通过）。

### 根因修复 Coherence：decode 层为 total 恒非 None 的单一收口点

`src/IM/infra/repositories.py:2547-2576`（`_decode_token_usage`）：pre-M17 `total:null` 行在此处即被派生为 `context_used + output`，`TokenUsage.total` 从 decode 层出口起恒非 None。下游两条路径：
- **REST**（`messages.py:162-166`）：再次检查 `total is not None`，等同双重防御
- **WS**（`event_types.py:67`）：`int(usage.total) if usage.total else ctx+output`，同一公式

三层口径一致，无矛盾。decode 是收口，REST/WS 是防御层，逻辑清晰。

回归单测 `test_decode_token_usage_with_null_total_derives_from_context_plus_output`（`tests/im_service/unit/test_message_runtime_state.py:118-165`）直接复现 pre-M17 `total:null` 场景，断言 `usage.total == 5100`（5000+100）。**1 passed**。

### WARNING-2 闭环：tasks.md 退出标准 checkbox 全勾选

`tasks.md:11-18` 所有 8 个退出标准均已改为 `[x]`，与 Roadpoints DONE 状态对齐。

---

## Round 1 Summary（历史存档）

| 维度 | 结果 |
|---|---|
| Completeness | 7/8（退出标准 checklist 未勾选；Roadpoints 全 DONE，实际实现全到位） |
| Correctness | 5/5 requirement 有实现；2 个 WARNING：warn/critical 变体 fixture 缺 total、design.md 第 32 行遗留矛盾描述 |
| Coherence | 总体遵守；1 个 WARNING：design.md 现状分析 / 既有约束段与决策 1 存在明显矛盾文字 |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

### Task 完成检查

tasks.md Roadpoints 全部标注 `Status: DONE`：
- R1 token 牌主数字改 total + 后端 REST 兜底 — DONE
- R2 全局策略页接回路由 + 用户菜单加「策略」入口 — DONE
- R3 agent-edit 测试断言对齐 features:{} — DONE
- R4 全量门禁 + 浏览器验收 — DONE

已在 verify worktree 跑全量确认：
- `npx vitest run` → 54 test files, 345 tests, **0 failed**（baseline 3 failed → 0 failed）
- `pytest tests/im_service/ -m "not e2e" --ignore=tests/im_service/integration` → 158 passed
- 三个原失败测试（token-chip R8-3 / policies-page / agent-edit）全部转绿

形式上的问题：`tasks.md` 退出标准 8 个 checklist 全为 `[ ]`（未勾选），与 Roadpoints 均 DONE 的实际状态不一致——这是文档维护遗漏，不影响功能完整性。

**Tasks: 4/4 Roadpoints DONE（退出标准 checklist 表单未勾选，见 WARNING-1）**

### Spec 覆盖检查

| Requirement | 实现状态 |
|---|---|
| token 用量牌显示这一轮的总消耗 | 实现（token-chip.tsx:33） |
| 全局策略页可从用户菜单进入并使用 | 实现（router.tsx:73-75, user-menu.tsx:150-157） |
| agent-edit 保存测试对齐 features:{} | 实现（agent-edit.test.tsx:204） |

所有 3 条 requirement 均有实现。

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Req-token: 牌子主数字显示 total | token-chip.tsx:33 `const displayed = usage.total!` | token-chip.test.tsx:34-45 R8-3 转绿 | covered |
| Scenario: 回复带 total → 显示 "2.4k" | token-chip.tsx:33+43 `fmtK(displayed)` | token-chip.test.tsx:34-45 | covered |
| Scenario: 旧回复经 REST 历史加载仍显示 total | messages.py:159-166 total 兜底 `total or ctx+out` | im_service 单元测试通过 | covered |
| Req-policies: 从用户菜单进入全局策略页 | user-menu.tsx:150-157 `<Link to="/settings/policies">` | policies-page.test.tsx:17 转绿 | covered |
| Scenario: 用户菜单「节点」下方有「策略」入口 | user-menu.tsx:140-157（nodes Link 紧接 policies Link） | 浏览器验收（progress.md R2） | covered |
| Scenario: 点击进入策略页不再 404，可查看/保存 | router.tsx:73-75 路由接回；PoliciesPage 组件现成 | policies-page.test.tsx 完整 CRUD 断言 | covered |
| Req-agent-edit: 保存断言含 features:{} | agent-edit.test.tsx:204 | agent-edit.test.tsx 4 tests 全绿 | covered |

**问题：warn/critical 变体测试 fixture 缺 total，与后端契约不对齐**

token-chip.test.tsx:20 和 24 的用例：
```ts
render(<TokenChip usage={{ output: 50, context_used: 140_000, context_window: 200_000 }} />);
```
没有 `total` 字段。组件第 33 行 `const displayed = usage.total!` 会导致 `displayed = undefined`，`fmtK(undefined)` 返回 `"undefined"` 字符串渲染在按钮文字中（`"undefined tok·ctx 70%"`）。测试仅断言 CSS class，不检查文本，所以测试通过——但 fixture 本身违背了 design.md 决策 1"total 由后端契约保证恒有值"的约束，且遮蔽了一个运行时渲染缺陷。

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: 主数字 = `usage.total`，无视图层回退 | 是 | token-chip.tsx:33 `const displayed = usage.total!`；注释明确"Do NOT fall back to output" |
| 决策 1: REST total 兜底对齐 WS 口径 | 是 | messages.py:159-166，公式与 event_types.py:67 一致 |
| 决策 2: router.tsx 补 policies 路由在 nodes/account 之间 | 是 | router.tsx:73-75（在 nodes:60 与 account:78 之间） |
| 决策 2: user-menu.tsx nodes Link 之后加 policies Link | 是 | user-menu.tsx:150-157（紧接 nodes Link:140-149 之后） |
| 决策 2: EN/ZH i18n 各加 `shell.userMenu.policies` | 是 | en.json:41 "Policies", zh.json:41 "策略" |
| 决策 3: 更新 agent-edit 测试断言含 `features:{}`，不动产品代码 | 是 | agent-edit.test.tsx:204，无产品代码改动 |

**问题：design.md 第 32 行"既有约束"与决策 1 存在矛盾描述**

design.md:32 写 "主数字必须回退 `output`，不能报错/空白"，但决策 1（design.md:71）明确"❌ `usage.total ?? usage.output`" 并写 "坚决否决 output 退让"。
实现正确地遵守决策 1（不回退），但"既有约束"段的遗留描述没有更新，会误导后续读者。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**WARNING-1: token-chip.test.tsx warn/critical 变体 fixture 缺 total，遮蔽运行时渲染缺陷**

- 位置：`src/IM/frontend/src/features/chat/v2/components/token-chip.test.tsx:20, 24`
- 问题：warn 和 critical 变体测试 fixture 未包含 `total` 字段，导致组件渲染时 `displayed = undefined`，页面实际显示 `"undefined tok·ctx N%"`。测试只断言 CSS class，不验证文字，所以测试通过但遮蔽了渲染缺陷。这与 design.md 决策 1"total 由后端契约保证恒有值，fixture 也应体现此约束"相悖（progress.md R1 已明确这一要求）。
- 修复：在 token-chip.test.tsx:20 和 24 的 usage 对象中补入 `total` 字段（值可取 `context_used + output`，如 `total: 140_050` 和 `total: 190_050`），使 fixture 对齐后端契约，并补充文本断言或不做断言均可（class 断言已够），确保测试不再静默掩盖 undefined 渲染。

**WARNING-2: tasks.md 退出标准 checklist 全未勾选，形式不完整**

- 位置：`docs/changes/bugfix-390-im-token-policies-agent-edit/M1-fix-frontend-three-defects/tasks.md:11-18`
- 问题：8 个退出标准 `- [ ]` 均未勾选，但 Roadpoints 全部标 `Status: DONE`，进度文档和 checklist 不同步，存在歧义。
- 修复：将 8 个 `- [ ]` 改为 `- [x]`，与 Roadpoints 状态和实际测试结果对齐。

### SUGGESTION（可以修）

**SUGGESTION-1: design.md 第 32 行"既有约束"遗留矛盾描述**

- 位置：`docs/changes/bugfix-390-im-token-policies-agent-edit/design.md:32`
- 问题：该行写"主数字必须回退 `output`，不能报错/空白"——这是决策 1 之前的初始分析，被决策 1 明确推翻后未删除，导致 design.md 内部自相矛盾。
- 修复：删除第 32 行，或将其改为"（已被决策 1 覆盖：total 由后端契约保证，前端不做视图层回退）"，避免误导后续维护者。

---

## Round 3 Summary（2026-06-01）

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 Roadpoints DONE；tasks.md 退出标准 7 项均标 ✓（含 worker/reviewer 项） |
| Correctness | M2 全部 requirement / scenario 有实现；i18n 17 个 key EN/ZH 完全对齐；字段集与调用语义不变；vitest 345 passed |
| Coherence | 决策 4 全部遵守；house style 与 account-page 结构一致；M1 三处无回归 |

All checks passed. Ready for PR.

---

## Round 3 核查重点

### M2 Completeness：Tasks 全 DONE

`M2-restyle-policies-page/tasks.md` Roadpoints 全部 DONE：
- R1 i18n keys（EN/ZH 补 `settings.policies.*`） — DONE
- R2 policies-page.tsx 呈现层重写 — DONE
- R3 浏览器验收截图 + progress.md 补齐 — DONE

退出标准 checklist（7 项）均已标 ✓（含 3 项 worker 项、progress.md Evidence 项）。

### M2 Correctness：i18n 三维核对

**维度 1：policies-page.tsx 无硬编码英文**

`policies-page.tsx` 中所有用户可见文案均通过 `t("settings.policies.*")` 取值，无任何硬编码英文字符串（背景颜色、类名等非文案的字符串除外）。共使用 17 个 i18n key，全部通过 `useTranslation()` 取用。

**维度 2：EN/ZH key 完全对齐**

`en.json` 与 `zh.json` 的 `settings.policies` 段均包含相同的 22 个 key（17 个被页面使用，另有 5 个 Hint 类备用 key 两份均有）：

| 使用的 key | EN | ZH |
|---|---|---|
| `settings.policies.title` | "Policies" | "策略" |
| `settings.policies.subtitle` | "Global runtime limits…" | "全局运行时限制…" |
| `settings.policies.loading` | "Loading policies…" | "加载策略中…" |
| `settings.policies.fields.defaultModel` | "Default Model" | "默认模型" |
| `settings.policies.fields.auditLevel` | "Audit Level" | "审计级别" |
| `settings.policies.fields.auditLevelOff` | "off" | "关闭" |
| `settings.policies.fields.auditLevelBasic` | "basic" | "基础" |
| `settings.policies.fields.auditLevelStrict` | "strict" | "严格" |
| `settings.policies.fields.maxTurnPerRun` | "Max Turn Per Run" | "每轮最大轮次" |
| `settings.policies.fields.rateLimitPerMin` | "Rate Limit / Min" | "每分钟限流" |
| `settings.policies.fields.maxAttachmentSizeMb` | "Max Attachment Size (MB)" | "附件最大体积（MB）" |
| `settings.policies.fields.retentionDays` | "Retention Days" | "消息留存天数" |
| `settings.policies.actions.save` | "Save Policies" | "保存策略" |
| `settings.policies.actions.saving` | "Saving…" | "保存中…" |
| `settings.policies.actions.discard` | "Discard" | "放弃" |
| `settings.policies.actions.unsavedChanges` | "Unsaved changes" | "有未保存改动" |
| `settings.policies.actions.saveFailed` | "Save failed: {{detail}}" | "保存失败:{{detail}}" |

EN/ZH 均补全，无缺失 key，无多余/遗漏不对称。

**维度 3：测试 aria-label 与 i18n key 对齐**

`policies-page.test.tsx` 使用英文 aria-label（`getByLabelText("Default Model")`、`getByLabelText("Audit Level")` 等）。测试环境默认 en locale，`t("settings.policies.fields.defaultModel")` = "Default Model" ✓。label 元素直接包裹文本 + input（无嵌套 hint span），`getByLabelText` 精确匹配（`policies-page.tsx:116-122`）。`getByRole("button", { name: "Save Policies" })` 对应 `t("settings.policies.actions.save")` = "Save Policies" ✓。

### M2 Correctness：字段集与调用语义不变

`policies-page.tsx` 导入并调用 `getPolicies` / `updatePolicies`（`im-settings-api.ts:106-114`），字段绑定覆盖 `PolicyProfile` 全部 6 个字段（`default_model`, `audit_level`, `max_turn_per_run`, `rate_limit_per_min`, `max_attachment_size_mb`, `retention_days`）——与重写前完全一致。`isDirty` 函数（`policies-page.tsx:12-21`）对所有 6 个字段做脏检测，保存时传整个 `draft`（`policies-page.tsx:71`），语义不变。

### M2 Correctness：vitest 全绿

`npx vitest run` → **54 test files, 345 tests, 0 failed**（本轮在 unit 分支 worktree 验证通过）。`policies-page.test.tsx:17` 通过（含字段编辑+PATCH 断言）。

### M2 Coherence：决策 4 遵守情况

| 决策 4 要点 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 外层 `flex flex-1 flex-col overflow-y-auto bg-[oklch(0.95_0.005_240)]` | 是 | policies-page.tsx:75，与 account-page.tsx:107 结构相同 |
| 移动端 sticky 顶栏（样式、返回键、h1 标题） | 是 | policies-page.tsx:77-88，样式与 account-page.tsx:110-122 逐字对齐 |
| 桌面端 `<header>` 大标题 + subtitle | 是 | policies-page.tsx:96-101 |
| 居中窄卡 `mx-auto w-full max-w-[620px]` | 是 | policies-page.tsx:90 |
| 字段纳入白色圆角卡片（`rounded-[14px] border bg-white`） | 是 | policies-page.tsx:114, 142 |
| save error 样式化 alert（oklch 红色 alert，role="alert"） | 是 | policies-page.tsx:105-111 |
| loading 态样式化反馈 | 是 | policies-page.tsx:55-58（oklch 背景 + 样式化文本） |
| 所有文案走 `settings.policies.*` i18n，无硬编码英文 | 是 | 见上方 i18n 核对表 |
| 字段集、`getPolicies`/`updatePolicies` 调用、保存语义全部不动 | 是 | policies-page.tsx:7, 30, 43, 12-21 |

### M1 三处无回归

- `token-chip.tsx:33` `const displayed = usage.total!`（未变，M2 未触碰）
- `router.tsx:73-75` policies 路由已接回（未变）
- `user-menu.tsx:151-154` policies Link 已加入（未变）
- `agent-edit.test.tsx:204` features:{} 断言（未变）
