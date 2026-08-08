# IM web-chat-ux Specification (delta for bugfix-518)

## MODIFIED Requirements

### Requirement: 历史会话蒸馏 conversation 选择入口

用户可从 IM 左侧 conversation 列表选择已完成、且属于同一 Gateway 的会话，生成一条普通聊天消息来
调用历史会话蒸馏 skill。IM 负责 source identity、同节点约束、execution Agent 和写入范围的选择与
路由；它不读取 workspace、扫描 JSONL、返回 JSONL path 或把 path 预填到聊天消息。

#### Scenario: 用户在 IM 左侧面板选择同 Gateway conversation 发起蒸馏
- **WHEN** 用户在 conversation 列表中进入“生成 skill”多选模式
- **THEN** 提供 checkbox 选择入口；`run_state=idle` 且有 source Agent 的 conversation 可选，
  `run_state=running` 的 conversation 禁选并显示“运行中”
- **AND** 已选来源属于一个 Gateway 后，其他 Gateway 的 conversation 禁选并说明一次蒸馏只能使用
  同一 Gateway

#### Scenario: execution Agent 与来源在同一 Gateway
- **GIVEN** 用户已选择一个或多个同 Gateway 的 idle conversations
- **WHEN** 用户点击“生成 skill”
- **THEN** 若来源属于同一 Agent，IM 自动选中该 Agent；否则只提供同一 Gateway 的 Agent 供选择
- **AND** 用户可选择 agent 或 global 范围，确认后进入 execution Agent 的新对话

#### Scenario: execution Agent 缺少蒸馏能力时不创建空对话
- **GIVEN** 用户已选择同 Gateway 来源
- **WHEN** 候选 execution Agent 缺少 `conversation-skill-distiller`、`skill_view` 或 `skill_manage`
- **THEN** IM 显示不可执行的原因并阻止开始蒸馏
- **AND** 不创建或导航到新的 execution conversation，也不遗留 distillation draft

#### Scenario: 提交蒸馏时不暴露本机路径
- **GIVEN** 用户在新对话补充意图并提交蒸馏
- **WHEN** IM 持久化并中继该普通用户消息
- **THEN** relay 只携带来源 conversation/Agent identity、execution Agent 与 target scope
- **AND** browser composer、conversation API、IM relay payload 与普通消息正文均不含
  `source_jsonl_paths`、workspace root 或 JSONL 绝对路径

#### Scenario: 蒸馏写入结果复用现有对话展示
- **GIVEN** 目标 Gateway 已从本机来源准备好蒸馏输入
- **WHEN** agent 成功调用 `skill_manage(create)` 写入 skill
- **THEN** IM 通过现有工具调用展示或普通 assistant 消息展示写入结果
- **AND** 不新增专门的 SKILL.md 草稿预览卡片、确认写入按钮或取消按钮

#### Scenario: 普通 sidebar 浏览不显示蒸馏选择状态
- **WHEN** 用户未进入“生成 skill”选择模式
- **THEN** conversation 列表保持既有普通浏览外观
- **AND** 不显示 running、different Gateway 或 checkbox 等只服务于蒸馏选择的标签
