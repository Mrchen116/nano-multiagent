# IM - Agents and Nodes Specification — feat-541 delta

> 落点: `docs/specs/im/agents-nodes.md`
> 投影自: feat-541 spec.md 验收标准 + design.md 决策 3、前端原型

## ADDED Requirements

### Requirement: Agent 配置页可设置有序备用模型，且默认不占地方

Agent 新建页与编辑页的主模型选择器仍在原位置。备用模型是紧挨该选择器的次要入口：默认收起，不把表单撑高；未展开时仍能看出已配备用数量。展开后从该节点可用模型目录按优先级添加与主模型不同的模型，保存后再次打开顺序不变。清空备用并保存后与从未配置等价。自动切换不会改写页面上保存的主模型。

#### Scenario: 默认折叠，主模型选择仍是重点
- **WHEN** 打开 Agent 新建页或编辑页
- **THEN** 主模型选择器仍在原位置，可单独完成「这个 Agent 用哪个模型」
- **AND** 备用模型区域默认收起，不把表单撑高到需要滚动才能看到主模型以外的常用项

#### Scenario: 展开后按序添加备用并保存
- **GIVEN** 该 Agent 所在节点有多个可用模型
- **WHEN** 用户展开备用区域，按优先级加入一个或多个与主模型不同的模型并保存
- **THEN** 再次打开该 Agent 编辑页时，展开后仍看到同一顺序的备用列表
- **AND** 未展开时仍能看出已配备用数量，不必先展开才能知道配没配

#### Scenario: 清空备用后与从未配置等价
- **GIVEN** 某 Agent 已保存过备用列表
- **WHEN** 用户把备用全部去掉并保存
- **THEN** 该 Agent 不再有备用链

#### Scenario: 自动切换不改写编辑页主模型
- **GIVEN** 某聊天已经自动改用备用模型
- **WHEN** 用户打开该 Agent 的编辑页
- **THEN** 主模型选择器与备用列表仍是保存过的配置

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示字段更新立即反映在 UI；model、有序 `model_fallbacks`、其可空 `reasoning_effort`、可见的 Custom Instructions (`custom_prompt`)、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一轮新回复开始时采用，并保持该聊天历史。已在进行的整轮不切换。IM 自有字段在 live 快照合并时仍以持久值为准。公开 Agent profile 和能力目录都不提供 `system_prompt` 或上游请求参数。缺省或空的 `model_fallbacks` 与从未配置等价。

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

## REMOVED Requirements
