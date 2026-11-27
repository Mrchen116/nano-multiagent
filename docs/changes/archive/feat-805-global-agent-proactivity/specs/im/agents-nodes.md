# IM - Agents and Nodes Delta Specification

> Target: `docs/specs/im/agents-nodes.md`

## MODIFIED Requirements

### Requirement: Web 与 iOS SHALL 使用一致的 Feature 依赖联动与轻提示

#### Scenario: 开启、关闭和独立重开
- **WHEN** 用户创建或编辑 Agent 的 Feature、工具或 Skill
- **THEN** 开启 Feature（含默认开启的「插件开发与管理」`plugin_management` 与全局模式的「主动筹划」`proactive_planning`）完整展开依赖；合法关闭默认撤销直接工具和 Skill 但保留共享及固定能力；随后单开工具（如单独启用 `cordis_inspect_list`）或 Skill 尊重最后选择，不反开 Feature
- **AND** 默认 Task 带出 Cron；关闭 Task 不级联关闭 Cron；Goal 与 Workflow 等独立工具保持各自工具选择，不设额外 Feature 开关，工具旁不增加依赖归属标注

#### Scenario: 全局模式默认开启与独立启停主动筹划，单会话模式不暴露
- **WHEN** 管理者在 Web IM、Desktop 客户端或原生 iOS 新建或编辑全局工作模式（`work_mode === "global"`，含个人助手与普通全局数字员工）或单会话工作模式（`work_mode === "single_thread"`）Agent
- **THEN** 满足「任务图」（`task_graph`）能力前提的全局模式 Agent 默认开启「主动筹划」（`proactive_planning`），并以符合其角色定位的说明展示开启与关闭后果（普通全局数字员工说明对话安静后原位记账、夜间围绕角色职责生成原会话待拍板候选卡及低噪跟进，关闭后停止自动记账与夜间提议立卡但保留已有任务图、正式记忆、角色约定与显式定时任务）；开启期间与「任务图」保持同一页面的依赖联动与轻提示
- **AND** 单会话模式 Agent 不显示且不持久化 `proactive_planning` 开关（新建页从全局模式切换为单会话模式时隐藏并剥离该项，提交前再切回全局模式且此前未手动关过该项、`task_graph` 仍开启时自动恢复默认开启态；编辑单会话模式 Agent 时关闭 `task_graph` 或 `cron_scheduling` 不受 `proactive_planning` 阻断）；所属节点不可达时沿用整页离线只读保护

#### Scenario: 阻止关闭或点击插件工具时保留状态并轻提示
- **WHEN** 用户点击被开启 Feature、模式固定基础能力或真实业务责任需要的开关，或在全量工具列表中点击由已启用插件提供的工具
- **THEN** 开关保持原态且不闪动；操作附近轻提示说明先关闭哪个 Feature、前往「插件」页关闭哪个插件、或说明其为基础固定能力/需开启 `plugin_manager` 方可激活，约 2 秒后自动淡出，无关闭按钮、不遮挡目标或抢焦点；提示作为独立浮层，不挤开控件、不改变列表换行或留下空位
- **AND** 重复点击延长同一提示，不堆叠；批量取消保留需要项，页面仍可编辑其他配置

#### Scenario: 保存重新校验且保留草稿
- **GIVEN** 页面预检后新增了有效责任或出现相关在途工作
- **WHEN** 用户保存关闭候选
- **THEN** 服务端重新检查并拒绝冲突关闭，页面恢复被阻止能力及其依赖，保留其他编辑并轻提示，不自动再次提交
- **AND** API 返回明确依赖、占用、资源缺失或状态无法确认原因；未确认成功不显示已生效

#### Scenario: 查询状态不泄露业务内容
- **WHEN** 有权限用户请求 Agent 能力使用状态
- **THEN** 仅返回本 Agent 的责任计数、相关忙碌能力与检查时间，不返回任务内容或他人数据；配置保存仍以最新权威状态复核
