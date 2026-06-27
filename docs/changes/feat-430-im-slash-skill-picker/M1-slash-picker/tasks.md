# feat-430-M1: slash-picker — Tasks

> 对齐: ../design.md v1（含 design-review #1/#2 修订）

## 目标

IM 前端 composer 在单聊/群聊敲 `/` 弹出候选面板（`/stop` + 该会话 agent(s) 已启用 skills），支持键盘/鼠标导航、前缀过滤、空态、选中补 `/skill:name `；后端补 skill `location` 四层只读透传供群聊按真实路径区分同名 skill 并标来源；并修群聊 `/stop`、`/skill:name` 在既有解析链上的识别缺口，使其在群聊真生效。

## 退出标准

- [ ] location 四层透传：sdk `SkillInfo` → kernel `list_skills` → upstream_reporter → IM capabilities API → 前端 type，字段端到端非空
- [ ] kernel `/skill` 正则认前导 `[..]` 段并保留；runtime 对命令所在 part（多 part 末 part）重写，覆盖「buffered 多 part + 末 part /skill」
- [ ] gateway 群聊裸 `/stop` 不受 MENTION 门控、对未运行 agent 无副作用（不发 no-op ack）
- [ ] 前端 slash-picker：单聊/群聊敲 `/` 弹面板（含 `/stop`+已启用 skills 交集）、键盘+鼠标导航、前缀过滤、空态、群聊按 location 合并/分行+来源标注、选中补 `/skill:name `
- [ ] 前端 `npm run test` + `npm run build` 全绿；后端 `pytest -m "not e2e"` 相关全绿
- [ ] live：真栈群聊发 `/stop`、`/skill:name` 真生效（reviewer 轨我先自证）

## 测试策略

- 被测行为：
  - location 透传非空（kernel `list_skills` 项带 location；reporter payload 带 location；IM `coerce_allowlist_options` 透传 location）
  - `rewrite_skill_command` 认 `[sender] /skill:doc` 前缀保留；runtime 多 part 末 part `/skill` 被重写
  - `_should_process` 放行群聊裸 `/stop`（MENTION 策略下）；群聊未运行 agent 无 ack 副作用
  - 前端 slash-picker 组件：过滤/键盘/鼠标/空态/补文本/群聊 location 分行；数据组装 config∩capabilities + 空白名单语义
- 已有测试：
  - `tests/contract/test_skill_commands_contract.py`（扩展 rewrite 前缀）
  - `tests/unit/test_agent_runtime.py`（扩展多 part /skill 重写）
  - `tests/unit/agent/test_kernel_list_capability_queries.py`（扩展 list_skills location）
  - `tests/unit/personal_assistant/test_gateway_stop_command.py`（扩展群聊裸 /stop）
  - IM API location：新建 `tests/unit/IM/test_capabilities_skill_location.py`（现有无合适落点），理由：capabilities `coerce_allowlist_options` location 透传无专测
  - reporter：扩展或新建 `tests/unit/personal_assistant/test_upstream_reporter_*`（按现状定位）
  - 前端：新建 `slash-picker.test.tsx`（照搬 mention-picker.test 结构）+ 数据组装单测
- 落层/marker：tests/unit + tests/contract，无 e2e marker（live 验收为临时证据）
- 可选依赖 importorskip：无
- 一次性验收证据（收尾删除）：浏览器截图、真栈 /stop + /skill log

### 前端 UI 部分

用户路径分类：
- slash-picker 弹出/选中/补文本 = `critical-path`（核心交互，落库组件测试 + 浏览器验收）
- 群聊 location 分行/来源标注 = `normal-ui`（组件测试 + 浏览器验收）
- 面板布局/截断/滚动 = `visual-only`（浏览器截图）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | 敲 `/` 弹面板，命令+skills，组件测试+截图 |
| loading | skills 数据在拉取中：面板可空/仅 `/stop`，组件容忍空 candidates |
| empty | `/xyz` 无匹配显示空态文案，组件测试 |
| error | capabilities 拉取失败：降级仅 `/stop`（不崩），数据层容错 |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | 长 description 单行截断 ellipsis，截图 |
| missing/nullable data | location 为 null：按 name 退化合并（中间态），数据层 |
| mobile viewport | composer 移动端面板仍锚定上方，截图 375 |
| desktop viewport | 1440 截图 |
| dark mode | 跟随既有主题，无专门处理 |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 弹出/前缀过滤/空态 | 组件测试 + 浏览器验收 | 是 |
| 键盘↑↓/Enter/Tab/Esc + 鼠标点击/hover/点外关 | 组件测试 + 浏览器验收 | 是 |
| 选中补 `/skill:name `/`/stop ` 光标末尾保焦 | 组件测试 + 浏览器验收 | 是 |
| 群聊 location 合并/分行+来源 | 组件测试（mock 数据）+ 浏览器验收 | 是 |
| config∩capabilities 交集 + 空白名单全量 | 数据组装单测 | 是 |
| 面板截断/滚动/布局不穿屏 | 浏览器截图 | 否 |
| 群聊 /stop、/skill 真生效 | 真栈 live | 否（临时证据） |

## Roadpoints

### R1 — 后端 location 四层只读透传 + 前端 type  [DONE]

- 步骤: `SkillInfo.location`（sdk dto）→ kernel `list_skills` 填 location → `_skills_from_kernel` 透传 → `AllowlistOptionResponse.location` + `coerce_allowlist_options` 透传 → 前端 `AgentAllowlistOption.location` + `normalizeAllowlistOptions` 透传
- 验证: 四层单测字段端到端非空 + 前端 normalize 单测

### R2 — kernel `/skill` 多 part 重写 + 正则认前缀  [DONE]

- 步骤: `skill_commands.py` 正则加可选 `^\s*(\[..\]\s*)?` 前缀并保留；`runtime.py` 多 part 分支对 `effective_user_text`（末 part）跑 rewrite
- 验证: contract 测 `[sender] /skill:doc` 保留前缀；runtime 多 part 末 part /skill 被重写（防 design-review #2 false-fix）

### R3 — gateway 群聊裸 /stop 放行 + 幂等无副作用  [DONE]

- 步骤: `_should_process` 放行裸 `/stop`；`_handle_stop_command` 群聊无 active run 时抑制 no-op ack
- 验证: 群聊 MENTION 策略下裸 /stop 触发 interrupt；未运行群成员无 ack

### R4 — 前端 slash-picker 组件 + message-pane 接入 + 数据获取  [DONE]

- 步骤: 新建 `slash-picker.tsx`（照搬 mention-picker 交互 + 原型 checklist）；`message-pane.tsx` 加 `/` 触发分支；`chat-workspace-page.tsx` 拉每会话 agent(s) 的 config∩capabilities skills 组装候选
- 验证: 组件测试（过滤/键盘/鼠标/空态/补文本/群聊分行）+ 数据组装单测 + `npm run test`/`build`

### R5 — live 真栈验收（浏览器 + 群聊 /stop + /skill）

- 步骤: e2e-up 起 IM+Gateway+Vite，浏览器敲 `/` 走全交互；真栈群聊发 /stop（裸、对运行/未运行）与 /skill:name 看后端真生效
- 验证: 截图 + proxy/gateway log 证据，记入 progress.md
