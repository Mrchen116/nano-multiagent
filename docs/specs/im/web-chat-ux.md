# IM - Web Chat UX Specification

> 对齐: feat-446 + feat-447
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

Web IM 聊天页滚动、输入、消息操作和桌面/移动一致性的用户可见契约。

## Requirements

### Requirement: Web IM 聊天页消息历史支持向上滚动分页加载

Web IM 的聊天页在会话历史超过一页时,用户向上滚动消息列表即可加载并查看更早内容;加载过程不破坏当前阅读位置。

#### Scenario: 用户向上滚动触发更早消息加载
- **GIVEN** 当前会话有更多历史消息
- **WHEN** 终端用户在消息列表中向上滚动到接近顶部
- **THEN** 更早的消息自动加载并插入到现有内容顶部
- **AND** 用户原来的阅读位置保持稳定,不自动跳到底部

#### Scenario: 已加载到最老的消息
- **GIVEN** 当前会话已经加载到第一条消息
- **WHEN** 终端用户继续滚动到顶部
- **THEN** 不再发起新的加载请求
- **AND** 列表顶部显示「没有更多消息」或等效空态提示

#### Scenario: 加载更早消息时显示加载状态
- **WHEN** 终端用户触发更早消息加载且请求尚未返回
- **THEN** 消息列表顶部出现加载状态提示

### Requirement: Web IM 新消息到达不打扰正在翻看历史的用户

当用户正在查看较早内容时,新到达的消息不会自动把视图拉到底部;只有当用户已经位于底部附近时,才自动跟随到最新内容。

#### Scenario: 用户正在看历史时收到新消息
- **GIVEN** 终端用户已经向上滚动离开底部,正在查看较早内容
- **WHEN** 有新消息或 agent 回复到达
- **THEN** 消息列表不自动滚动到底部
- **AND** 用户仍停留在当前阅读位置

#### Scenario: 用户位于底部时收到新消息
- **GIVEN** 终端用户位于消息列表底部附近
- **WHEN** 有新消息或 agent 回复到达
- **THEN** 消息列表自动滚动到底部,让用户看到最新内容

### Requirement: Web IM 移动端输入法回车发送消息

在移动设备上,终端用户在聊天输入框中按下输入法回车键即可发送消息,而不需要点击发送按钮。

#### Scenario: 移动端按回车发送
- **GIVEN** 终端用户在移动端的聊天输入框中输入了文字
- **WHEN** 用户按下输入法回车键
- **THEN** 消息被发送,输入框清空
- **AND** 不回车换行

### Requirement: Web IM composer 输入框随内容自动增高

聊天输入框会根据输入内容自动增高,直到达到最大行数;超过最大行数后输入框内部可滚动。

#### Scenario: 输入多行文字时 composer 增高
- **GIVEN** 终端用户在 composer 中输入文字
- **WHEN** 文字超过一行
- **THEN** composer 自动增高以展示更多内容
- **AND** 增高到最大行数后不再继续变高,内部可滚动

### Requirement: Web IM 消息气泡支持复制与长按/右键菜单

终端用户可以长按(移动端)或右键(桌面端)消息气泡,调出操作菜单复制消息文本;在移动端单聊里,还可以对可 fork 的 agent 回复进行 fork。

#### Scenario: 长按/右键消息气泡调出菜单
- **GIVEN** 聊天列表中有任意消息气泡
- **WHEN** 终端用户在移动端长按气泡,或在桌面端右键气泡
- **THEN** 弹出操作菜单,至少包含「复制」

#### Scenario: 复制消息文本
- **GIVEN** 操作菜单已打开
- **WHEN** 终端用户选择「复制」
- **THEN** 该消息的文本内容被复制到剪贴板

#### Scenario: 移动端单聊里长按 agent 回复进行 fork
- **GIVEN** 当前是直接用户↔agent 的会话,且某条 agent 回复已完成并可 fork
- **WHEN** 终端用户在移动端长按该 agent 回复,并在菜单中选择 fork
- **THEN** 触发 fork 流程,并给终端用户明确反馈(如进入新分支会话)

### Requirement: Web IM 桌面与移动端在聊天页保持一致的滚动与交互体验

无论是桌面浏览器还是移动浏览器,进入同一聊天页都能获得相同的分页加载、Enter 发送、composer 自动增高和消息菜单能力。

#### Scenario: 在手机端向上滚动加载历史
- **WHEN** 终端用户在移动设备上打开同一聊天并向上滚动
- **THEN** 同样触发加载更早消息,且阅读位置保持稳定

#### Scenario: 在手机端长按 agent 消息 fork
- **WHEN** 终端用户在手机端长按可 fork 的 agent 回复
- **THEN** 出现包含 fork 选项的菜单

### Requirement: 历史会话蒸馏 conversation 选择入口

用户可从 IM 左侧 conversation 列表选择已完成会话,生成一条普通聊天消息来调用历史会话蒸馏 skill。
IM 负责选择来源、执行 agent 与写入范围;Gateway 不解析蒸馏路径或注入 transcript 上下文。

#### Scenario: 用户在 IM 左侧面板选择 conversation 发起蒸馏
- **WHEN** 用户在 conversation 列表中进入"生成 skill"多选模式
- **THEN** 提供 checkbox 选择入口;`run_state=idle` 的 conversation 可选,`run_state=running` 的 conversation 禁选并显示"运行中"

#### Scenario: 单一来源 agent 时自动确定执行 agent
- **GIVEN** 用户已选择一个或多个 `run_state=idle` 的 conversation
- **WHEN** 用户点击"生成 skill"
- **THEN** 若所选 conversation 都属于同一个 agent,IM 自动把该 agent 作为执行 agent
- **AND** IM 弹窗让用户选择 agent 级或 PA 产品级写入范围
- **AND** 用户确认后跳转到执行 agent 的新对话

#### Scenario: 跨 agent 来源时选择执行 agent
- **GIVEN** 用户已选择多个 `run_state=idle` 的 conversation,且这些 conversation 来自多个 agent
- **WHEN** 用户点击"生成 skill"
- **THEN** IM 弹窗让用户选择一个执行 agent
- **AND** 同一弹窗让用户选择 agent 级或 PA 产品级写入范围
- **AND** 用户确认后跳转到执行 agent 的新对话

#### Scenario: 执行 agent 未启用历史会话蒸馏 skill
- **GIVEN** 执行 agent 的可见 skill 集合不包含 `conversation-skill-distiller`
- **WHEN** 用户点击"生成 skill"
- **THEN** IM 提示执行 agent 未启用历史会话蒸馏 skill
- **AND** 不跳转新对话,也不预填 `/skill:conversation-skill-distiller`

#### Scenario: 默认 conversation 列表不显示运行态标签
- **WHEN** 用户正常浏览 IM 左侧 conversation 列表,且未进入"生成 skill"多选模式
- **THEN** conversation 行不显示"已结束/运行中"这类运行态标签

#### Scenario: 用户通过范围弹窗指定生成级别后提交蒸馏
- **GIVEN** 新对话已预填所选 conversation 对应的 `source_jsonl_paths`
- **WHEN** 用户补充意图说明并提交
- **THEN** 对话将 `/skill:conversation-skill-distiller`、`source_jsonl_paths`、用户意图、
  `execution_agent_id` 与 `target_scope` 预填为用户可见消息
- **AND** 该消息按普通聊天消息发送;Gateway 不解析 `source_jsonl_paths`,不注入 transcript 上下文

#### Scenario: 蒸馏写入结果复用现有对话展示
- **GIVEN** 用户已发送预填后的蒸馏消息
- **WHEN** agent 成功调用 `skill_manage(create)` 写入 skill
- **THEN** IM 通过现有工具调用展示或普通 assistant 消息展示写入结果
- **AND** 不新增专门的 SKILL.md 草稿预览卡片、确认写入按钮或取消按钮
