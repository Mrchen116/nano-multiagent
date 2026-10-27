# im Agents Nodes Specification (delta for feat-635)

## ADDED Requirements

### Requirement: Web 与原生 iOS SHALL 支持逐项选择默认关闭的 Goal 工具

#### Scenario: 默认及保存反馈
- **WHEN** 用户进入现有或新建 Agent 的能力配置
- **THEN** Features 中没有 DSH Goal 开关，普通工具列表中的 create_goal、get_goal、update_goal 默认不选；已保存的显式选择如实显示。
- **AND** 用户可分别选择或取消三个工具且互不联动，保存结果和生效时机沿用普通工具配置；失败不能展示已生效，Task 配置不受影响。

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示字段更新立即反映在 UI；model、有序 `model_fallbacks`、其可空 `reasoning_effort`、可见的 Custom Instructions (`custom_prompt`)、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一轮新回复开始时采用，并保持该聊天历史。完整配置不在已进行的整轮中切换；可调用工具的取消选择例外地立即收缩，新增工具仍等待当前执行空闲后的完整配置应用，不中断已开始的工具调用。IM 自有字段在 live 快照合并时仍以持久值为准。公开 Agent profile 和能力目录都不提供 `system_prompt` 或上游请求参数。缺省或空的 `model_fallbacks` 与从未配置等价。

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
