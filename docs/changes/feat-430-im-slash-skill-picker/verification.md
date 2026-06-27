# Verification Report: feat-430

> round: 1 | verifier: feat-430-verifier | date: 2026-06-27

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 0/6 exit criteria formally ticked（但代码+测试实证全部完成，见 Issues） |
| Correctness | 16/16 spec requirements/scenarios covered |
| Coherence | Followed（6/6 design 关键决策均遵守） |

1 critical issue(s) found. Fix before PR.

---

## Completeness

### Tasks

Tasks: 0/6 formally complete（`M1-slash-picker/tasks.md` 退出标准全部仍为 `- [ ]`）

所有 6 条退出标准均未勾选，但经代码核查 + 测试全绿，工作实质上已完成（进展证据见 `progress.md` R1-R5）：

| 退出标准 | 实现状态 |
|---|---|
| location 四层透传 | 已实现：`sdk/dto.py:397` / `kernel list_skills` / `upstream_reporter.py:124` / `agents.py:539-549` / 前端 `im-agent-config-api.ts:64` |
| kernel `/skill` 正则+多 part 重写 | 已实现：`skill_commands.py:8-14` / `runtime.py:586` |
| gateway 群聊裸 `/stop` 放行 + 幂等 | 已实现：`inbound_pipeline.py:842` |
| 前端 slash-picker 全功能 | 已实现：`slash-picker.tsx` / `slash-candidates.ts` / `message-pane.tsx` |
| npm test + npm build + pytest 全绿 | 已验证：3049 pytest passed；vitest 533 passed |
| live 真栈验收 | 已完成（progress.md R5 有完整证据） |

**必须修**：将 `tasks.md` 6 条 `- [ ]` 更新为 `- [x]`。

### Spec 覆盖

所有 spec requirements 均有实现（见 Correctness 表）。

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| **输入 `/` 弹出 slash 候选面板** | | | |
| 单聊里敲 `/` 弹面板含 `/stop`+已启用 skills | `message-pane.tsx:162-163`（`matchSlashTrigger`）+ `slash-picker.tsx:45-54` | `message-pane.test.tsx:1159` | covered |
| 群聊里敲 `/` 弹面板含所有成员 skills 并集 | `chat-workspace-page.tsx:289-314`（并发拉 config+capabilities）+ `buildSlashSkills` 合并 | `slash-candidates.test.ts: buildSlashSkills`+ `message-pane.test.tsx:1233` | covered |
| 输入框中间出现 `/` 不触发 | `matchSlashTrigger` 正则 `^/(skill:)?([^\s/]*)$` 要求无前置文本 | `message-pane.test.tsx:1175` | covered |
| **键盘与鼠标导航选中** | | | |
| 方向键移动高亮 + Enter 确认 | `slash-picker.tsx:79-88` | `slash-picker.test.tsx:60-66` | covered |
| 候选超出可视区高亮项滚动可见 | `slash-picker.tsx:66-68`（scrollIntoView nearest） | 无单测（visual-only，tasks.md 已标注浏览器截图） | covered（visual-only 可接受） |
| 鼠标点击候选项选中 | `slash-picker.tsx:134-136`（mousedown+preventDefault） | `slash-picker.test.tsx:43-49` | covered |
| Esc 或点击面板外关闭，`/` 文本保留 | `slash-picker.tsx:88-91`（Esc）；`message-pane.tsx:260-273`（点外）| `message-pane.test.tsx:1207` | covered |
| **skill 选中后补正确 slash 格式** | | | |
| 选中 skill 后补 `/skill:name ` 尾随空格光标末尾 | `message-pane.tsx:212-221`（rAF setSelectionRange） | `message-pane.test.tsx:1197` | covered |
| **群聊 skills 按路径区分同一性并标注来源** | | | |
| 同路径 skill 合并显示 | `slash-candidates.ts:buildSlashSkills:67-78`（key = location） | `slash-candidates.test.ts: merges same-location` | covered |
| 不同路径同名 skill 分开显示+标注来源 | 同上（不同 key → 两行）；`slash-picker.tsx:117-120`（fromLabel） | `slash-candidates.test.ts: keeps same-named at different locations` + `slash-picker.test.tsx:79-85` | covered |
| **前缀过滤** | | | |
| `/pr` 过滤出匹配的 skill，不匹配的 `/stop` 消失 | `slash-picker.tsx:47-53`（前缀过滤） | `slash-picker.test.tsx: prefix-filters` | covered |
| `/xyz` 无匹配显示空态提示 | `slash-picker.tsx:97-102` | `slash-picker.test.tsx: empty state` | covered |
| 编辑已补入 `/skill:doc` → `/skill:d` 重新过滤纠错 | `slash-candidates.ts:matchSlashTrigger`（`/skill:` 形态）；`message-pane.tsx:166`（changeDraft 重置 dismissed） | `slash-candidates.test.ts: /skill: namespace supports prefix editing` | covered |
| **发送行为与普通消息一致** | | | |
| 选中 skill 后继续输入发送，agent 按既有规则处理 | slash 文本就是普通 textarea 内容，走普通发送链路 | 无专测（集成行为）；live 真栈验证 R5 | covered |
| 群聊里发送 `/stop`，正在运行的 agent 收到后停止 | `inbound_pipeline.py:842`（放行裸 `/stop`）+ 既有 `_is_stop_command`/`_handle_stop_command` | `test_gateway_stop_command.py: test_bare_stop_in_group_mention_policy_interrupts_running_agent` | covered |
| 群聊里裸 `/stop` 不受"仅 @ 才响应"设置影响 | `inbound_pipeline.py:842`（置于 is_group MENTION 门控之前） | `test_gateway_stop_command.py: test_bare_stop_in_group_mention_policy_interrupts_running_agent` | covered |
| 群聊里 `/stop` 对未在运行的 agent 幂等，无报错无副作用 | `inbound_pipeline.py:917-919`（群聊无 active run 时抑制 ack） | `test_gateway_stop_command.py: test_bare_stop_in_group_no_active_run_has_no_side_effect` + `test_bare_stop_in_group_multi_agent_stops_only_running_no_noise` | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：新建独立 `slash-picker.tsx`，不复用 mention-picker | 是 | `slash-picker.tsx`（独立文件，mention-picker 未被修改） |
| 决策 2：启用 skills = config 白名单 ∩ capabilities；空白名单显示全部 | 是 | `slash-candidates.ts:resolveEnabledSkills:45-52`；`slash-candidates.test.ts: empty whitelist` |
| 决策 3：location 五层只读透传 | 是 | `dto.py:397` → `list_skills` → `upstream_reporter.py:124` → `agents.py:549` → `im-agent-config-api.ts:64` |
| 决策 4：裸 `/stop` 绕过 MENTION 策略（纯文本检查，非 wire-mention）| 是 | `inbound_pipeline.py:842`（`message.text.strip() == "/stop"` 置 MENTION 门控之前） |
| 决策 5：`_SKILL_COMMAND_PATTERN` 认可选 `[..]` 前缀 + runtime 对末 part 重写 | 是 | `skill_commands.py:9`（`(?P<prefix>\[[^\]]*\]\s*)?`）；`runtime.py:586`（对 `last_part` 重写）|
| 决策 6：命令补 `/name `，skill 补 `/skill:name `，命令+skill 一视同仁前缀过滤 | 是 | `message-pane.tsx:213`；`slash-picker.tsx:47-53` |

---

## Issues

### CRITICAL（提 PR 前必须修）

**C1 — tasks.md 退出标准 6 条均未勾选（`- [ ]`）**

`docs/changes/feat-430-im-slash-skill-picker/M1-slash-picker/tasks.md:11-16` 所有退出标准仍为 `- [ ]`，尽管 progress.md R1-R5 均有实现证据且测试全绿。  
**修法**：将 6 条 `- [ ]` 改为 `- [x]`（实现已完成，仅需更新文档记账）。

---

### WARNING（应该修）

**W1 — delta-spec 未并入长青契约层**

`docs/changes/feat-430-im-slash-skill-picker/specs/` 下的三份 delta-spec（gateway、im、kernel）已写就，但对应的 canonical `docs/specs/{gateway,im,kernel}/spec.md` 尚无 feat-430 相关更新。历史惯例（参见 git log）是收尾前做一次 `docs(feat-430): 收尾归并契约层` commit。  
**修法**：按 delta-spec 内容将三份 scenario/requirement 增量并入各包的 canonical spec.md，提交 `docs(feat-430): 收尾归并契约层 docs/specs/{gateway,im,kernel}`。

**W2 — 群聊裸 /stop 新行为未在 e2e-critical-paths.md 登记**

`docs/e2e-critical-paths.md` 要求"新增关键特性须登记一行 + 配 e2e"。本 unit 新增了群聊裸 `/stop` 绕过 MENTION 策略这一关键行为变更，但既有 `test_stop_run_critical_path.py` 只覆盖单聊 /stop，且 `e2e-critical-paths.md` 未新增登记。  
**修法**：在 `docs/e2e-critical-paths.md` 的「已知缺口 backlog」段补一行（群聊裸 /stop 经 MENTION 策略 agent 仍被中断），或在 `tests/e2e/critical_paths/test_stop_run_critical_path.py` 补一条群聊路径并登记到 v1 必保活表。

---

### SUGGESTION（可以修）

**S1 — slash-picker 缺 `aria-activedescendant`**

design.md 的 slash picker 交互 checklist 明确要求 "给面板/项加 `role=listbox`/`option` 与 `aria-activedescendant`"。`slash-picker.tsx` 已有 `role="listbox"`/`role="option"`/`aria-selected`，但 listbox 容器未设 `aria-activedescendant` 指向当前高亮项。  
**修法**：在 `slash-picker.tsx` 中给高亮项 button 添加固定 id（如 `slash-item-{idx}`），并在 listbox 容器上添加 `aria-activedescendant={highlighted item id}`，完善键盘可访问性。

**S2 — slash-picker 缺 Tab 键选中测试**

design.md checklist 说明 "Enter 与 Tab 都确认选中"，`slash-picker.tsx:85` 实现了 Tab，但 `slash-picker.test.tsx` 只测了 Enter（line 57-65），Tab 无对应用例。  
**修法**：在 `slash-picker.test.tsx` 中补一条 `user.keyboard("{Tab}")` 验证 Tab 确认选中的测试用例。
