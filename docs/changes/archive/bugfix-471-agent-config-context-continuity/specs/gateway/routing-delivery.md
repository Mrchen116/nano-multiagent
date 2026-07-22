# gateway Routing and Delivery Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: 配置更新不改变 active run 与被其采纳的插话

Gateway 为 active run 冻结其启动时的 Agent 运行配置。配置更新期间到达、且成功注入该 active run 的插话继续属于同一配置代次；只有随后真正开始的新 run 使用最新配置。

#### Scenario: 回复进行中修改配置
- **GIVEN** Agent 正在使用配置 A 回复
- **WHEN** 用户把 Agent 更新为配置 B
- **THEN** 当前 run 继续使用 A，下一新 run 使用 B

#### Scenario: 配置更新后的插话进入 active run
- **GIVEN** active run 使用配置 A，Agent 已更新为 B
- **WHEN** 用户插话被 active run 采纳
- **THEN** 该插话与当前整轮继续使用 A，不在同一 run 中混入 B

### Requirement: 实际配置边界最终可靠同步到 Web IM

当既有聊天的新 run 首次采用不同的有效运行配置时，Gateway 为该聊天和首条用户消息产生一条稳定、可重试的配置边界事实。IM 暂时离线或 Gateway 重启不会永久丢失该事实；重复投递不会产生重复边界。外部 channel 的业务回复不因 IM 暂时离线而被阻塞，恢复后其 Web IM 影子会话补齐边界，外部平台不收到伪造消息。边界事实只携带定位、幂等和代次证明所需的非敏感身份，不携带 prompt、完整配置、secret、工具参数或变更字段明细。

#### Scenario: Web IM 新 run 采用新配置
- **GIVEN** 既有 Web IM 聊天的有效运行配置已改变
- **WHEN** 首条用户消息实际开始使用新配置的 run
- **THEN** Gateway 把配置边界关联到该聊天和该用户消息，供 IM 持久显示

#### Scenario: IM 断线后最终补齐唯一边界
- **GIVEN** Gateway 已实际采用新配置，但 IM 连接暂时不可用
- **WHEN** IM 连接恢复，或 Gateway 在恢复前重启
- **THEN** 同一配置边界最终投递成功且至多显示一次

#### Scenario: 外部 channel 不等待 Web IM 标记
- **GIVEN** 用户在外部 channel 的既有对话中触发新配置，IM 暂时离线
- **WHEN** Agent 完成回复
- **THEN** 回复照常发回外部 channel
- **AND** IM 恢复后 shadow conversation 补齐原用户消息、Agent 回复与其前唯一配置边界，外部 channel 不收到边界文本

#### Scenario: Gateway 在 shadow 同步任一步骤后崩溃
- **GIVEN** 外部消息已进入本地可恢复同步流程，IM 写入某一步后 Gateway 尚未记录成功
- **WHEN** Gateway 重启并重放同一外部事件
- **THEN** IM 复用同一 shadow conversation、用户消息和 Agent 回复，配置边界仍唯一且锚点正确

#### Scenario: 纯展示变化与保存失败不产生边界
- **WHEN** Agent 只发生展示信息变化，或配置保存没有成功
- **THEN** Gateway 不产生实际运行配置边界

## MODIFIED Requirements

### Requirement: 会话映射与实际运行配置状态持久化，进程重启后续接不丢历史

Gateway 持久化“会话键 → 内核会话”绑定及该聊天实际采用的运行配置身份。配置更新不删除绑定；同一聊天的新 run 在原内核会话应用最新配置。进程重启后恢复同一绑定、历史与实际配置状态。升级前没有配置身份的旧绑定惰性建立基线，不因部署升级产生虚假配置提示。

#### Scenario: 重启后同一通道会话续接原内核会话
- **GIVEN** 某通道聊天已绑定内核会话并跨过一次配置更新
- **WHEN** Gateway 重启后同一聊天再来消息
- **THEN** 恢复原内核会话及实际配置状态，保留配置边界两侧历史，不退回旧配置

#### Scenario: Agent 配置更新不删除休眠聊天绑定
- **GIVEN** 同一 Agent 有多个已持久化聊天，其中一些休眠
- **WHEN** Agent 运行配置更新
- **THEN** 这些 binding 均保留；休眠聊天在自己下一次新 run 时才采用最新配置

#### Scenario: 旧 binding 首次恢复不产生虚假边界
- **GIVEN** 升级前 binding 没有持久运行配置身份
- **WHEN** 升级后首次恢复并继续该聊天
- **THEN** Gateway 建立兼容基线并延续原会话，不仅因软件升级产生“Agent 配置已更新”边界

#### Scenario: 不同聊天保持隔离
- **GIVEN** 同一 Agent 有直聊、群聊和外部 channel 多个独立聊天
- **WHEN** 配置更新后各自继续
- **THEN** 每个聊天只延续自己的历史和配置边界，不读取其他聊天内容

#### Scenario: 未知会话键返回空绑定
- **WHEN** 查询从未绑定的会话键
- **THEN** 返回空绑定且无副作用

## REMOVED Requirements

N/A.
