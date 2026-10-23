# im/agents-nodes.md (delta for feat-645)

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示字段更新立即反映在 UI；model、有序 `model_fallbacks`、其可空 `reasoning_effort`、可见的 Custom Instructions (`custom_prompt`)、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一轮新回复开始时采用，并保持该聊天历史。完整配置不在已进行的整轮中切换；可调用工具的取消选择例外地立即收缩，新增工具仍等待当前执行空闲后的完整配置应用，不中断已开始的工具调用。IM 自有字段在 live 快照合并时仍以持久值为准。公开 Agent profile 和能力目录都不提供 `system_prompt` 或上游请求参数。缺省或空的 `model_fallbacks` 与从未配置等价。

本次取消选择若会撤销仍被开启 Feature、有效业务责任或正在执行的工具调用需要的能力，保存先被拒绝；只有通过依赖与占用校验的变更才进入上述生效流程。普通运行中不因此阻止无关配置更新。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端读取 Agent 配置
- **THEN** 响应保留既有稳定配置字段、可空 `reasoning_effort`、有序 `model_fallbacks` 及 profile version
- **AND** 专属人设只以可见的 `custom_prompt` 返回，不含 profile `system_prompt`

#### Scenario: PATCH 经 Gateway 可恢复 apply 后持久化运行配置并保持乐观锁
- **WHEN** 前端带当前 profile version 保存配置
- **THEN** IM 先持久化候选 configuration operation，并取得 owning Gateway 对完整候选配置的成功 apply operation 结果，再持久化 profile
- **AND** 成功响应与随后读取反映持久值；过期 version 被拒且不覆盖新值

#### Scenario: 既有聊天下一轮新回复采用成功保存的运行配置
- **GIVEN** 某聊天已形成历史且当前没有新回复在开始
- **WHEN** 用户成功更新 Agent 运行配置后回到该聊天发消息
- **THEN** 下一轮新回复使用更新后的模型、备用列表和推理强度，并延续原聊天历史

#### Scenario: 保存的推理强度必须属于 Gateway apply 时的有效模型目录
- **GIVEN** Agent 明确选择模型 M，或继承 Gateway 的平台默认模型 M
- **WHEN** 前端保存 M 的推理强度
- **THEN** Gateway 在 apply 时以 M 的当前能力验证该选择并确认其本地配置已落地后，IM 才持久化
- **AND** 当目录已更新而该强度失效时返回冲突、不写新 profile，也不表示保存成功

#### Scenario: 保存的备用模型必须属于 Gateway apply 时的有效模型目录
- **GIVEN** 该节点当前可用模型目录
- **WHEN** 前端保存 `model_fallbacks`
- **THEN** Gateway 在 apply 时确认每一项都在目录中、与当时有效主模型不同，并去重保序
- **AND** 目录外的项返回冲突、不写新 profile

#### Scenario: Gateway 成功 apply 后 IM 乐观锁失败会恢复 Gateway 原配置
- **GIVEN** Gateway 已成功 apply 一个候选 Agent 配置
- **WHEN** IM 以该请求的 profile version 持久化时发现并发配置已先保存
- **THEN** IM 在返回冲突前请求 Gateway 恢复之前已确认的完整配置，前端不显示候选配置已保存

#### Scenario: 已落盘但 ACK 丢失的配置操作可恢复而不伪装旧值成功
- **GIVEN** IM 已保存一个 Agent 配置 operation，Gateway 已落盘候选配置和 applied receipt
- **WHEN** ACK frame 丢失、连接重连或 IM 在 profile 持久化前重启
- **THEN** IM 使用同一 operation id 重试或查询 Gateway operation status
- **AND** 结果仍不可确认时 API 返回 `503 config_apply_pending`，页面显示正在确认且禁止重复编辑，不把旧 profile 显示为已经保存的当前配置
- **AND** 完整请求已收到后，HTTP 连接允许等待既有节点确认流程返回；不因短于该流程的 socket 空闲超时提前断开。请求体接收时限与大小限制继续生效。

#### Scenario: 配置接口遇到代理错误页面
- **WHEN** 加载或保存 Agent 配置时，代理返回 HTML 或其他非业务 JSON 错误
- **THEN** 页面显示当前语言的简短服务器响应提示和 HTTP 状态，保留正在编辑的内容，不展示代理页面源码，也不自动重发修改请求
- **AND** 业务 JSON 中的待确认状态、冲突原因与操作标识继续用于原有恢复流程

#### Scenario: 创建 Agent 的已应用结果丢失后可恢复
- **GIVEN** Gateway 已创建并为某 create operation 持久化 applied receipt
- **WHEN** IM 未收到 create ACK 或在写入 profile 前重启
- **THEN** IM 通过该 operation status 得到 canonical Agent payload 后创建 profile
- **AND** 同一 operation 重试不会在 Gateway 创建第二个 workspace 或第二次发布配置

#### Scenario: live 合并保留 IM 自有字段
- **GIVEN** 持久 profile 含 IM 自有运行字段
- **WHEN** IM 拉取并合并 Gateway live snapshot
- **THEN** live payload 省略这些字段时不把持久值清空

#### Scenario: heartbeat cadence 返回真实配置值
- **WHEN** 前端读取某 Agent 的 heartbeat cadence
- **THEN** 返回该 Agent 的真实 `heartbeat.every` 配置值；未配置时体现为默认 `30m`

### Requirement: Agent 配置页可按 Skill 来源分组批量调整选择

Agent 创建/编辑页在已有 Skill 来源分组内提供紧凑的批量选择和取消选择能力，同时保留单个 Skill 的独立选择。分组状态清楚反映当前草稿中该组可见 Skill 的未选、部分选择或全选状态；批量操作沿用既有 profile draft、保存、Gateway apply 与下一轮生效流程，不增加立即生效旁路或脱离分组的笨重全局操作区。

#### Scenario: 用户批量选择一个来源分组后继续逐项调整
- **GIVEN** Agent 配置页的一个 Skill 来源分组有多个可选 Skill
- **WHEN** 用户对该分组执行批量选择
- **THEN** 该组当前可见 Skill 一同进入配置草稿
- **AND** 用户仍可在保存前调整单个 Skill；开启 Feature 必需的 Skill 保持选中并以局部轻提示说明原因

#### Scenario: 用户批量取消部分已选分组
- **GIVEN** 某来源分组的全部或部分可见 Skill 已在配置草稿中选择
- **WHEN** 用户对该分组执行批量取消或修改其中一个 Skill
- **THEN** 页面保留开启 Feature 必需项，取消其余项，清楚反映未选、部分选择或全选的实际状态；有受保护项时用一条轻提示说明
- **AND** 不把尚未保存的草稿误显示为已在运行时生效

#### Scenario: 窄屏配置仍保持清晰的分组操作
- **GIVEN** 用户在窄屏浏览器打开 Agent 创建或编辑页
- **WHEN** 页面显示多个 Skill 来源分组和其批量选择能力
- **THEN** 分组标题、选择状态和单个 Skill 仍可辨认与触达
- **AND** 不出现脱离 Skill 分组、占据页面主要空间的独立批量操作区

### Requirement: 设置 detail 页工具勾选态按存储真值渲染

agent 设置 detail 页的工具面板按存储的 `tool_allowlist` 渲染勾选态:合法空名单不按默认值回填，运行模式固定项仍显示真实有效状态,不再按 capabilities `default_on` 显示为默认全开;用户勾选/取消直接写显式名单,空名单在 single_thread 且无开启 Feature 依赖业务工具时合法；有固定项或开启 Feature 时不能借空集绕过依赖保护。

#### Scenario: 存储为空全不亮
- **GIVEN** single_thread agent 的存储 `tool_allowlist` 为空且依赖工具的 Feature 均关闭
- **WHEN** 打开该 agent 的设置 detail 页
- **THEN** 可选业务工具均不亮，当前运行模式的固定能力保持选中

#### Scenario: 显式清空保存后保持
- **GIVEN** single_thread agent 当前启用若干工具且依赖工具的 Feature 均关闭
- **WHEN** 用户取消全部勾选、保存、刷新页面
- **THEN** 工具面板保持全部不亮

## ADDED Requirements

### Requirement: Web 与 iOS SHALL 使用一致的 Feature 依赖联动与轻提示

#### Scenario: 开启、关闭和独立重开
- **WHEN** 用户创建或编辑 Agent 的 Feature、工具或 Skill
- **THEN** 开启 Feature 完整展开依赖；合法关闭默认撤销直接工具和 Skill但保留共享及固定能力；随后单开工具或 Skill 尊重最后选择，不反开 Feature
- **AND** 默认 Task 带出 Cron；关闭 Task 不级联关闭 Cron，工具旁不增加依赖归属标注

#### Scenario: 阻止关闭时保留选择
- **WHEN** 用户点击被开启 Feature、固定基础能力或真实业务责任需要的开关
- **THEN** 开关保持原态且不闪动；操作附近轻提示说明先处理什么，约 2 秒后淡出，无关闭按钮、不遮挡目标或抢焦点；提示作为独立浮层，不挤开控件、不改变列表换行或留下空位
- **AND** 重复点击延长同一提示，不堆叠；批量取消保留需要项，页面仍可编辑其他配置

#### Scenario: 保存重新校验且保留草稿
- **GIVEN** 页面预检后新增了有效责任或出现相关在途工作
- **WHEN** 用户保存关闭候选
- **THEN** 服务端重新检查并拒绝冲突关闭，页面恢复被阻止能力及其依赖，保留其他编辑并轻提示，不自动再次提交
- **AND** API 返回明确依赖、占用、资源缺失或状态无法确认原因；未确认成功不显示已生效

#### Scenario: 查询状态不泄露业务内容
- **WHEN** 有权限用户请求 Agent 能力使用状态
- **THEN** 仅返回本 Agent 的责任计数、相关忙碌能力与检查时间，不返回任务内容或他人数据；配置保存仍以最新权威状态复核
