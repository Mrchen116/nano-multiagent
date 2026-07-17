# bugfix-468 — 回归验证

> 对齐: incident.md v1 / design.md v1
> Review round: 1
> Date: 2026-07-17

## Verdict

`pass`

## 验收标准覆盖

### Requirement: 设置页工具/技能勾选态反映存储真值

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 存储非空的 agent 显示实际存储值 | incident.md §验收标准 | 浏览器：进入 default-agent 设置页，勾选 read/write，保存后刷新 | `ACCEPTANCE/bugfix-468/02-default-nonempty-desktop.png` | pass | 保存后仅 read、write 高亮 |
| 存储为空的 agent 全不亮 | incident.md §验收标准 | 浏览器：进入 plato 设置页（tool_allowlist=[]） | `ACCEPTANCE/bugfix-468/01-plato-empty-desktop.png` | pass | 全部 13 个工具 pill 均未选中 |
| 显式清空可以表达并保持，且新会话无工具 | incident.md §验收标准 | 浏览器：default-agent 取消全部勾选→保存→刷新；随后与该 agent 直聊请求读文件 | `ACCEPTANCE/bugfix-468/03-default-cleared-refreshed-desktop.png`、`05-chat-default-empty.png`、`m2-empty-messages.json` | pass | 刷新后全不亮；会话中 bash/glob/read 均 failed |
| create 页预选默认行为不变 | incident.md §验收标准 | 浏览器：进入新建 agent 页 | `ACCEPTANCE/bugfix-468/04-create-preselect-desktop.png` | pass | read/write/edit/bash/agent/task_stop/web_fetch/web_search/skill_manage/skill_view/memory 预选（与变更前一致） |

### Requirement: 零工具/受限会话的非名单工具被明确拒绝

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 显式零工具会话中工具调用被拒 | incident.md §验收标准 | 浏览器+API：default-agent（tool_allowlist=[]）直聊请求读取 README | `ACCEPTANCE/bugfix-468/05-chat-default-empty.png`、`m2-empty-messages.json` | pass | bash/file_read/glob/read 均 failed，错误含 "tool 'X' is not enabled in this session" |
| 正常 agent 工具通路不回归 | incident.md §验收标准 | 浏览器+API：plato（tool_allowlist=["read","write"]）直聊请求读取 README | `ACCEPTANCE/bugfix-468/06-chat-plato-normal.png`、`m2-normal-messages.json` | pass | read 工具 completed，返回文件内容 |

### Requirement: 参数校验报错列出具体字段名

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 错参数名调用可自我纠正 | incident.md §验收标准 | SDK 直接驱动 edit 工具传入 old_string/new_string | `ACCEPTANCE/bugfix-468/m3_validator_qa.py` 输出 | pass | 报错含 "The required parameter `oldText` is missing"、"The required parameter `newText` is missing" |
| 多余参数与类型错误同样列名 | incident.md §验收标准 | SDK 直接驱动 edit 工具传入 extra_field / 整数 oldText | `ACCEPTANCE/bugfix-468/m3_validator_qa.py` 输出 | pass | unexpected: "An unexpected parameter `extra_field` was provided"；type: "The parameter `oldText` type is expected as `string` but provided as `integer`" |

## User Journeys Exercised

1. **设置页真值渲染（Req-1）**：登录 → 打开 plato detail 页 → 确认空名单全不亮 → 打开 default-agent detail 页 → 勾选 read/write → 保存并刷新 → 取消全部勾选 → 保存并刷新 → 打开新建 agent 页确认预选。覆盖 4 条 Scenario。
2. **零工具会话兜底（Req-2）**：与 tool_allowlist=[] 的 default-agent 直聊 → 请求读取 README → 观察到所有工具调用被拒绝。覆盖 1 条 Scenario。
3. **正常工具通路（Req-2）**：与 tool_allowlist=["read","write"] 的 plato 直聊 → 请求读取 README → 观察到 read 成功完成。覆盖 1 条 Scenario。
4. **校验报错列字段名（Req-3）**：通过 SDK 直接驱动 edit 工具，分别传入错误参数名、多余参数、错误类型，捕获 ToolError 文本。覆盖 2 条 Scenario。

## 复现验证

原始 issue #203 描述的三个缺口在修复前表现为：设置页空 allowlist 显示默认全开、零工具会话中模型自由调用仍可执行、参数校验报错不列字段名。本轮在隔离真栈（IM_URL=http://127.0.0.1:57425，NODE_ID=wt-unit-bugfix-468-59391）复现同一场景后，三个缺口均已关闭：

- 设置页空名单显示全不亮（证据 01）。
- 零工具会话中工具调用被拒绝且无副作用（证据 05、m2-empty-messages.json：bash/file_read/glob/read 全部 failed）。
- 错误参数调用 edit 时返回文本明确列出 `oldText`/`newText`（m3_validator_qa.py 输出）。

## 回归测试

- 正常 agent（plato 启用 read/write）的文件读取通路仍可正常工作（证据 06、m2-normal-messages.json：read completed）。
- 新建 agent 页默认工具预选行为与变更前一致（证据 04）。
- 浏览器控制台与网络请求无报错（`browser-console.json`、`chat-console.json` 均为空）。

## Issues

无。

## Side Findings

无 blocking/major 发现。以下属次要观察，不立 issue：

- 多次点击 agent 设置页 "Open chat" 会创建多个同名直聊会话；属既有行为，不在 #203 范围内。
- M3 的自然聊天诱导（要求模型使用 old_string/new_string）未能触发 edit 调用——模型改用 read+write 完成目标。因此本轮对 Req-3 的验证采用 SDK 直接驱动 edit 工具的 fallback，该路径经过真实 ToolRegistry/EditTool，非 mock。

## 自动化测试增量

由 milestone worker 负责，reviewer 未直接运行全量测试树，仅确认：

- M1: `npm run test` / `npm run build` 已通过（见 `M1-settings-truth-rendering/progress.md`）。
- M2: `pytest tests/unit/agent tests/unit/personal_assistant -q` 已通过（见 `M2-executor-allowlist-enforcement/progress.md`）。
- M3: `pytest tests/unit/test_tool_validation_errors.py` 与全测试树已通过（见 `M3-validator-error-field-names/progress.md`）。

## 上层文档同步

- [ ] `SPEC.md`（跨包顶点架构）：无需更新 —— 本 unit 未改变包边界或顶层架构。
- [ ] `docs/specs/<包>/`（长青行为契约层）：需要更新 —— design.md §契约层增量已列出：
  - `docs/specs/kernel/tools-hooks.md`（执行层名单拦截 + 校验报错文案）
  - `docs/specs/im/agents-nodes.md`（设置 detail 页按存储真值渲染）
  - `docs/specs/gateway/agent-capabilities.md`（显式工具名单在会话执行层强制，含空=全拒）
  - `docs/specs/cli/spec.md` 无需更新（CLI 会话 tool_allowlist=None，行为不变）
  由 orchestrator 在 PR 阶段按 delta-spec 收尾归并。
- [ ] `AGENTS.md` / `CLAUDE.md`：无需更新 —— 启动/配置范式未变。
- [ ] `docs/SPEC_GUIDE.md`（文档规范）：无需更新 —— 未改动文档体系本身。
