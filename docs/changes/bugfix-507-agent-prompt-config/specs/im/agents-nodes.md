# IM Agents and Nodes Specification (delta for bugfix-507)

> 对齐 canonical: `docs/specs/im/agents-nodes.md`。

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示字段更新立即反映在 UI；model、可见的 Custom Instructions (`custom_prompt`)、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一轮新回复开始时采用，并保持该聊天历史。已在进行的整轮不切换。IM 自有字段在 live 快照合并时仍以持久值为准。公开 Agent profile 不提供也不接受 `system_prompt`；能力目录中的只读 `default_system_prompt` 仍仅表示产品默认提示词。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端读取 Agent 配置
- **THEN** 响应保留既有稳定配置字段及 profile version
- **AND** 专属人设只以可见的 `custom_prompt` 返回，不含 profile `system_prompt`

#### Scenario: PATCH 持久化运行配置并保持乐观锁
- **WHEN** 前端带当前 profile version 保存配置
- **THEN** 成功响应与随后读取反映持久值；过期 version 被拒且不覆盖新值

#### Scenario: 既有聊天下一轮新回复采用成功保存的运行配置
- **GIVEN** 某聊天已形成历史且当前没有新回复在开始
- **WHEN** 用户成功更新 Agent 运行配置后回到该聊天发消息
- **THEN** 下一轮新回复使用更新配置并延续原聊天历史

#### Scenario: live 合并保留 IM 自有字段
- **GIVEN** 持久 profile 含 IM 自有运行字段
- **WHEN** IM 拉取并合并 Gateway live snapshot
- **THEN** live payload 省略这些字段时不把持久值清空

#### Scenario: heartbeat cadence 返回真实配置值
- **WHEN** 前端读取某 Agent 的 heartbeat cadence
- **THEN** 返回该 Agent 的真实 `heartbeat.every` 配置值；未配置时体现为默认 `30m`

## ADDED Requirements

### Requirement: Agent 专属说明只有可见的 Custom Instructions，预览覆盖全部稳定公开配置

Agent owner 通过 Custom Instructions 管理该 Agent 的专属职责或约束；它是公开 profile 唯一会改变专属人设的文本。提示词预览使用已保存或当前草稿的同一 `custom_prompt`、features、tools 与 skills 组装稳定提示词，并明确排除群聊、记忆等仅在运行时才确定的上下文。

#### Scenario: 留空的 Custom Instructions 没有隐藏专属人设
- **WHEN** owner 打开或保存 Agent 配置，Custom Instructions 为空
- **THEN** Agent 不带任何由公开 Agent profile 注入的专属说明

#### Scenario: 预览可检查当前稳定专属说明
- **WHEN** owner 展开提示词预览，或编辑 Custom Instructions 后再次查看预览
- **THEN** 预览包含该 Agent 已保存或待保存的专属说明和已选能力配置
- **AND** 页面明确说明群聊、记忆等运行时内容不在预览内

#### Scenario: 升级保留已有有效说明且不重复
- **GIVEN** 某 Agent 在升级前因 legacy `system_prompt` 实际带有专属说明
- **WHEN** 系统升级且 owner 打开该 Agent 配置
- **THEN** owner 能在 Custom Instructions 中看到并编辑这段说明
- **AND** 该说明不丢失、不重复注入；如已有不同 Custom Instructions，则保留原来 legacy 在前、custom 在后的有效顺序

#### Scenario: 旧 Gateway 初次注册空 IM 时保留本地有效说明
- **GIVEN** Gateway 的本地旧配置中某 Agent 有有效 legacy 专属说明，且 IM 尚无该 Agent profile
- **WHEN** 升级后的 Gateway 首次注册该 Agent
- **THEN** IM 创建的 Agent profile 将规范化后的说明作为 Custom Instructions 持久化
- **AND** 后续 Gateway 对账、重连或 owner 已明确清空 Custom Instructions 时，不以旧本地 seed 覆盖已存在的 profile
