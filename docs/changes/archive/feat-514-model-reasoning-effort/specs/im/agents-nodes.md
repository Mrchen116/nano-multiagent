# IM - Agents and Nodes Specification (delta for feat-514)

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。
展示字段更新立即反映在 UI；model、其可空 `reasoning_effort`、可见的 Custom Instructions
(`custom_prompt`)、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一轮新回复
开始时采用，并保持该聊天历史。已在进行的整轮不切换。IM 自有字段在 live 快照合并时仍以持久
值为准。公开 Agent profile 和能力目录都不提供 `system_prompt` 或上游请求参数。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端读取 Agent 配置
- **THEN** 响应保留既有稳定配置字段、可空 `reasoning_effort` 及 profile version
- **AND** 专属人设只以可见的 `custom_prompt` 返回，不含 profile `system_prompt`

#### Scenario: PATCH 经 Gateway 可恢复 apply 后持久化运行配置并保持乐观锁
- **WHEN** 前端带当前 profile version 保存配置
- **THEN** IM 先持久化候选 configuration operation，并取得 owning Gateway 对完整候选配置的成功 apply
  operation 结果，再持久化 profile
- **AND** 成功响应与随后读取反映持久值；过期 version 被拒且不覆盖新值

#### Scenario: 既有聊天下一轮新回复采用成功保存的运行配置
- **GIVEN** 某聊天已形成历史且当前没有新回复在开始
- **WHEN** 用户成功更新 Agent 运行配置后回到该聊天发消息
- **THEN** 下一轮新回复使用更新后的模型和推理强度，并延续原聊天历史

#### Scenario: 保存的推理强度必须属于 Gateway apply 时的当前模型目录
- **GIVEN** Agent 明确选择模型 M
- **WHEN** 前端保存 M 的推理强度
- **THEN** Gateway 在 apply 时以 M 的当前能力验证该选择并确认其本地配置已落地后，IM 才持久化
- **AND** 当目录已更新而该强度失效时返回冲突、不写新 profile，也不表示保存成功

#### Scenario: Gateway 成功 apply 后 IM 乐观锁失败会恢复 Gateway 原配置
- **GIVEN** Gateway 已成功 apply 一个候选 Agent 配置
- **WHEN** IM 以该请求的 profile version 持久化时发现并发配置已先保存
- **THEN** IM 在返回冲突前请求 Gateway 恢复之前已确认的完整配置
- **AND** 前端不显示候选配置已保存

#### Scenario: 已落盘但 ACK 丢失的配置操作可恢复而不伪装旧值成功
- **GIVEN** IM 已保存一个 Agent 配置 operation，Gateway 已落盘候选配置和 applied receipt
- **WHEN** ACK frame 丢失、连接重连或 IM 在 profile 持久化前重启
- **THEN** IM 使用同一 operation id 重试或查询 Gateway operation status
- **AND** applied 结果继续完成 profile persist；rejected 结果保留草稿并返回冲突
- **AND** 结果仍不可确认时 API 返回 `503 config_apply_pending`，页面显示正在确认且禁止重复编辑，
  不把旧 profile 显示为已经保存的当前配置

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

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

新建/编辑 Agent 页需要的 runtime 候选项(skills / tools / models / features)由 IM 当场经 gateway
WS 向在线节点解析后返回,IM 不在本地持久化该能力目录,也不据 IM 部署机文件系统推断。节点级
`GET /im/v1/nodes/{id}/capabilities` 与 agent 级 `GET /im/v1/agents/{id}/capabilities` 都把网关返回
的 `features` 和每模型安全的 reasoning descriptor 透传给前端。

#### Scenario: 节点能力含 features 列表供创建页渲染
- **GIVEN** 一个已知节点,网关在线
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities`
- **THEN** 200 返回 node、skills、tools、models、platform default model 与 features 候选项

#### Scenario: 可选模型列表每项携带 provider 和可选推理能力
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 每个 model 含其注册 provider
- **AND** 若节点将其声明为可调推理模型，model 含 `{kind:"selectable", default, levels}`；固定思考模型含 `{kind:"fixed"}`；未声明的模型不含 reasoning 字段
- **AND** 响应不含模型静态请求参数或上游密钥

#### Scenario: 用户按模型能力选择推理设置
- **GIVEN** 创建或编辑页已取得在线节点能力
- **WHEN** 用户先选择一个可调推理模型
- **THEN** 页面只提供该 model descriptor 声明的 levels，并初始选择其 default
- **WHEN** 用户选择 fixed 模型、未选择模型或目录未声明推理能力的模型
- **THEN** 页面分别显示固定思考说明、需先选模型说明或不可配置说明，不提交脱离模型的强度

#### Scenario: agent 能力透传 features 五元字段
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 200 含既有 `features` 列表，由网关 FEATURE_REGISTRY 投影原样转发
