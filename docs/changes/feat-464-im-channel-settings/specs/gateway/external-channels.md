# Gateway External Channels Specification (delta for feat-464)

## ADDED Requirements

### Requirement: Gateway 按完整 manifest 调和 managed external channels

支持 IM channel control 的 Gateway 将 IM 下发的完整 desired manifest 调和为本机 managed external channel 运行集合，并向 IM 回报该 manifest 的实际应用结果。manifest revision 只用于内部传输排序，channel revision 只用于一致性关联，两者都不构成用户可见的通道版本历史。已成功应用的重复 manifest 幂等，旧 manifest 不覆盖新状态；上次应用失败的同 revision 可以重试未完成动作。内置 `web_relay` 不属于 managed external manifest。

#### Scenario: 在线新增 channel 无需重启 Gateway
- **GIVEN** Gateway 已连接 IM
- **WHEN** IM 下发包含新飞书 channel 的 manifest
- **THEN** 该飞书 Bot 的新消息可以触发目标 Agent，Agent 可以通过同一 Bot 回复
- **AND** 运维者不需要修改 YAML 或重启 Gateway

#### Scenario: 重复 manifest 不重复启动
- **GIVEN** Gateway 已处理 manifest revision N
- **WHEN** IM 再次下发相同 revision 和内容
- **THEN** channel 保持当前连接状态，不出现新的连接周期
- **AND** 同一条飞书入站消息仍只触发一次 Agent 处理和一次回复

#### Scenario: 更高 revision 中缺少旧 channel
- **GIVEN** Gateway 本地运行某 managed channel
- **WHEN** 已初始化节点收到更高 manifest revision，且其中不再包含该 channel
- **THEN** 该飞书 Bot 的后续消息不再触发 Agent，Agent 也不再通过它发送
- **AND** Gateway 重启后该 channel 仍不会从旧 YAML 恢复
- **AND** Gateway 在实际停止旧 channel 并提交本地 cache 后向 IM 回报 removal applied

#### Scenario: 空 manifest 也回报实际应用结果
- **GIVEN** 已初始化节点的 desired manifest 不含任何 managed channel
- **WHEN** Gateway 完成所有旧 channel 的停止与本地 cache 提交
- **THEN** Gateway 向 IM 回报该 manifest 已应用及成功 removal 列表
- **AND** IM 可以据此结束删除待应用状态

#### Scenario: channel 在首次同步前已被删除
- **GIVEN** 用户在节点离线期间新增又删除 channel，Gateway 从未见过该 channel
- **WHEN** IM 下发不含该 item 但包含其 removal intent 的 manifest
- **THEN** Gateway 确认本地运行集合与 cache 均无该 identity 后回报 already absent
- **AND** IM 可以结束该 channel 的删除待应用状态

#### Scenario: removal result 确认丢失后继续重放
- **GIVEN** Gateway 已完成 channel 删除，但 IM 对 removal result 的确认丢失
- **WHEN** Gateway 重连或在确认前又处理更高 manifest revision
- **THEN** 未确认的 removal outcome 仍随 result 重放，不被新 revision 覆盖
- **AND** IM 返回 accepted、already applied 或 applied-head 已覆盖的等价终态后 Gateway 才停止重放该 outcome
- **AND** Gateway 离线超过 IM applied receipt 保留期也不会永久重放

#### Scenario: channel 停止失败时回报可重试结果
- **GIVEN** 更高 manifest 要求删除旧 channel
- **WHEN** Gateway 无法停止旧 channel 或无法提交移除后的本地 cache
- **THEN** Gateway 向 IM 回报 removal failed 和可理解错误码
- **AND** 不宣称该 manifest 已完整应用
- **AND** IM 重发同一 revision 时 Gateway 重试未完成的删除

### Requirement: Gateway 从本地密文 manifest 离线启动

Gateway 在连接 IM 前先读取上次成功调和的 encrypted channel manifest，并启动其中 enabled 的 external channels。IM 不可达不得阻塞这些 channel 的消息主路径；IM 恢复后以完整 manifest 收敛到最新 desired state。

#### Scenario: IM 离线重启后飞书仍可用
- **GIVEN** Gateway 已成功缓存一个 enabled 飞书 channel 的密文 manifest 和节点私钥
- **WHEN** Gateway 在 IM 不可达时重启
- **THEN** Gateway 解封本地凭据并启动飞书 channel
- **AND** 飞书消息主路径继续工作

#### Scenario: IM 重连后收敛离线变更
- **GIVEN** 用户在 Gateway 离线期间通过 IM 修改了 channel
- **WHEN** Gateway 重新连接 IM 并收到较新完整 manifest
- **THEN** Gateway 自动应用最终新增、修改、启停和删除状态

### Requirement: Managed Feishu 保持既有身份与能力

通过 IM 新建和从旧 YAML 导入的飞书 channel 使用与既有配置相同的稳定 Agent channel 身份，并继续提供 owner 绑定、审批交互与飞书文档能力。控制面的 channel UUID 不改变外部会话归属或消息 session continuity。

#### Scenario: 控制面迁移不改变外部会话身份
- **GIVEN** `feishu:<agent_id>` 已产生私聊或群聊影子会话
- **WHEN** 该 channel 被导入 IM control plane 或在其中更新
- **THEN** 同一飞书用户或群的后续消息继续进入原有 Agent 会话语义
- **AND** 不因 control-plane channel UUID 创建另一套 channel 身份

#### Scenario: 新建 managed Feishu 完成 owner 绑定
- **GIVEN** 用户通过 IM 新建飞书 channel，尚未记录 owner open ID
- **WHEN** owner 首次通过该 Bot 发送合法消息
- **THEN** 后续需要人工决定的工具调用可以向该 owner 发送审批卡
- **AND** Gateway 重启后仍保持该 owner 绑定

#### Scenario: 更换 App ID 后重新建立应用内身份
- **GIVEN** 飞书 channel 已保存旧 App 的 owner 与 Bot 身份
- **WHEN** 用户把该 channel 更换为另一个 App ID
- **THEN** 旧 App 的 owner 与 Bot 身份不再用于新 App
- **AND** 新 App 的首个合法 owner 消息重新建立 owner 绑定
- **AND** 旧 runtime 或离线 cache 的迟到身份更新不能恢复旧绑定
- **AND** 新 App 的审批卡仍遵守 first-wins 与 resolved/expired 语义

#### Scenario: Managed Feishu 保持文档 skill 可用
- **GIVEN** Agent 使用显式非空 skill allowlist，且其中尚无 `feishu-doc`
- **WHEN** 飞书 channel 被启用
- **THEN** 该 Agent 后续运行可以发现 `feishu-doc`
- **AND** 停用或删除 channel 不移除用户已拥有的 skill

#### Scenario: 审批卡操作返回确定结果
- **GIVEN** 飞书 Bot 已向 owner 发送权限审批卡
- **WHEN** owner 允许、拒绝、提交拒绝原因，或点击已处理/过期卡片
- **THEN** 飞书客户端收到与既有 first-wins、resolved 或 expired 语义一致的卡片响应
- **AND** worker 重启或暂时不可用时显示可重试结果，不重复应用决定

### Requirement: Managed channel 动态生命周期立即影响实际收发

Gateway 对 managed external channel 的 disable、delete、replace 和 shutdown 必须使实际消息收发与新期望状态一致，不能只改变 IM 展示状态。不同 Agent 的飞书 Bot 生命周期相互隔离。

#### Scenario: 停用后不再接收或发送
- **GIVEN** 一个已连接的飞书 channel
- **WHEN** desired manifest 将其设为 disabled
- **THEN** 后续飞书消息不再触发该 Agent
- **AND** Agent 也不再通过该 Bot 发送消息

#### Scenario: 替换凭据不留下旧收发路径
- **GIVEN** 一个正在运行的飞书 channel
- **WHEN** manifest 提供新 App ID 或替换后的 App Secret
- **THEN** 旧飞书应用的后续消息不再触发该 Agent
- **AND** 新飞书应用连接成功后可以触发该 Agent 并收到回复
- **AND** 单条入站消息不会产生重复 Agent 处理或重复回复

#### Scenario: 多个飞书 Bot 生命周期隔离
- **GIVEN** 同一 Gateway 节点上不同 Agent 各有一个飞书 Bot
- **WHEN** 其中一个 Bot 重连、停用或失败
- **THEN** 其他 Bot 的入站触发和出站回复不受影响

### Requirement: Gateway 上报 channel 实际状态与权限诊断

Gateway 为每个 managed channel 上报当前内部配置代次、连接状态、诊断状态和结构化检查项。内部配置代次只用于让 IM 拒绝旧状态，不作为用户可见版本。凭据无效、Bot 不可用、连接中断、权限缺失和检查不可用必须使用不同错误码/状态表达。飞书权限诊断必须读取租户授权状态，只把 `grant_status=1` 且 `scope_type=tenant` 的条目作为应用身份已授权权限；缺字段、未知枚举或响应不可解析时结果为 unknown，不得仅凭 scope 名存在判定权限充足。

#### Scenario: 连接成功且权限完整
- **WHEN** 飞书通道已连接，且 Gateway 已确认所需权限与平台配置完整
- **THEN** Gateway 上报 `connection_state=connected`、`diagnostics_state=complete`

#### Scenario: 权限不足但仍可降级
- **GIVEN** 飞书通道已连接，但 Gateway 确认有权限或平台配置缺失项
- **WHEN** Gateway 上报状态
- **THEN** 保持已连接的消息能力
- **AND** 上报 `diagnostics_state=limited`，每项含 raw scope、影响和修复方向

#### Scenario: 普通群消息权限缺失
- **GIVEN** 租户授权状态查询成功且结构完整，但应用身份已授权集合同时不包含当前权限 `im:message.group_msg` 和 legacy 等价权限 `im:message.group_msg:readonly`
- **WHEN** Gateway 生成诊断
- **THEN** 对应检查项说明未 @Bot 的群消息与群背景上下文不可用

#### Scenario: 存量应用持有 legacy 等价权限
- **GIVEN** 某项能力的当前推荐权限未授权，但一个仍受飞书支持的 legacy 等价权限以应用身份授权
- **WHEN** Gateway 生成该能力的诊断
- **THEN** 对应 `accepted_scope_sets` 检查为 satisfied
- **AND** Gateway 不要求用户替换仍有效的旧权限，也不把它上报为 missing

#### Scenario: scope 名存在但未按应用身份授权
- **GIVEN** scope 响应含目标名称，但 `grant_status=2` 或 `scope_type=user`
- **WHEN** Gateway 生成依赖该 scope 的诊断
- **THEN** 该条目不能满足应用身份权限要求
- **AND** Gateway 不得仅凭 scope 名存在上报 complete

#### Scenario: scope 检查失败
- **GIVEN** scope API 暂时失败，或返回缺少授权状态/身份类型、未知枚举或其他不可完整解析结果
- **WHEN** 飞书基础连接仍然可用
- **THEN** Gateway 上报 `diagnostics_state=unknown`
- **AND** 不生成虚假的 missing scope

#### Scenario: SDK 自动重连
- **GIVEN** 飞书通道此前已连接
- **WHEN** SDK 检测连接中断并开始恢复
- **THEN** Gateway 上报 reconnecting
- **AND** 恢复或最终失败后再次上报终态

#### Scenario: 同一配置代次的状态保持因果顺序
- **GIVEN** 自动或手动重连在同一内部配置代次产生多个状态
- **WHEN** 较新的恢复、再次中断或失败状态已经上报
- **THEN** 较早状态不会随后覆盖较新状态
- **AND** IM 最终看到的状态与当前 runtime 一致

#### Scenario: 离线缓存状态已被新 desired 淘汰
- **GIVEN** Gateway 在 IM 离线时从 revision N cache 启动 channel 并保留状态 barrier
- **AND** 用户已在 IM 把 channel 更新到 N+1 或删除
- **WHEN** Gateway 重连并先重放 revision N barrier
- **THEN** IM 返回可消费的 stale revision 或 channel removed 终态
- **AND** Gateway 丢弃旧状态、释放上行队列并继续接收完整 manifest
- **AND** channel removed 时旧 cached runtime 立即停止，不能用旧状态复活

### Requirement: 旧 YAML channel 只在控制面首次初始化时导入

Gateway 在节点 channel control 未初始化时，把旧 YAML 中的 Feishu channel 作为一次性 bootstrap 候选上传；初始化完成后，以 IM manifest 和本地 encrypted cache 为权威，不再从旧 YAML 复活已删除配置。未配置 IM 的 standalone Gateway 继续支持旧 YAML。

#### Scenario: 首次导入旧 Feishu 配置
- **GIVEN** Gateway YAML 已配置 Feishu，IM 中该节点 channel control 尚未初始化
- **WHEN** Gateway 首次连接支持 channel control 的 IM
- **THEN** Gateway 上传旧配置，IM 返回权威 manifest
- **AND** channel 随后能在 IM 通道页查看和管理

#### Scenario: 人工绑定完成后无需重连即可初始化
- **GIVEN** Gateway 已注册并等待用户确认节点绑定，channel control 尚未初始化
- **WHEN** 用户在 IM 完成人工绑定且当前 Gateway WebSocket 仍在线
- **THEN** IM 立即继续该节点的 channel bootstrap
- **AND** 用户不需要重启或等待 Gateway 偶然重连
- **AND** register、绑定确认或后续重连的重复触发不会重复导入 channel

#### Scenario: bootstrap 半途失败
- **GIVEN** 旧 YAML channel 尚未成功写入 IM 并缓存权威 manifest
- **WHEN** bootstrap 任一步失败
- **THEN** Gateway 保留并继续使用旧 YAML
- **AND** 下次连接可安全重试

#### Scenario: standalone Gateway 保持兼容
- **GIVEN** Gateway 未配置 IM service
- **WHEN** Gateway 启动
- **THEN** 继续按旧 YAML 构建 external channels
