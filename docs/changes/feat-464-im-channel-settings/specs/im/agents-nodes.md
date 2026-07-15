# IM Agents and Nodes Specification (delta for feat-464)

## ADDED Requirements

### Requirement: Agent 通道页管理通用外部 channel

IM 在 Agent 详情页提供外部 channel 管理入口。列表、添加入口、状态和生命周期动作采用 provider 无关的 channel 语言；飞书是首个可配置 provider。内置 Web IM 不作为外部 channel 展示。同一个 owner 的同一个 Agent 对每种 provider 最多存在一个 channel。

#### Scenario: 未配置 channel 时显示通用空态
- **GIVEN** 当前 Agent 没有外部 channel
- **WHEN** 用户打开 Agent 详情的“通道”
- **THEN** 页面显示外部 channel 空态和“添加通道”
- **AND** 页面不展示 Web IM

#### Scenario: 已有同 provider 时不能重复添加
- **GIVEN** 当前 Agent 已有一个飞书 channel
- **WHEN** 用户打开 provider 选择器
- **THEN** 飞书显示为已添加，不能创建第二个实例

#### Scenario: 列表读取失败不伪装成空态
- **WHEN** IM 无法读取已保存的 channel
- **THEN** 页面显示失败原因和重试入口
- **AND** 不显示“尚未配置”的空态

### Requirement: 飞书 channel 提供轻量接入向导

飞书 provider 表单只提供完成接入所需的简短准备说明，不在 IM 内复刻开放平台教程。向导固定链接到 `https://open.feishu.cn/page/launcher?from=backend_oneclick`，并要求用户提供 App ID 与 App Secret；节点在线时保存后立即进入连接流程，无需修改 Gateway 配置文件或重启服务。

#### Scenario: 从 provider 选择器进入飞书向导
- **GIVEN** 当前 Agent 尚无飞书 channel
- **WHEN** 用户在“添加通道”中选择飞书
- **THEN** 页面提示在飞书开放平台创建应用、开启机器人能力并使用长连接接收事件
- **AND** 页面提供 `https://open.feishu.cn/page/launcher?from=backend_oneclick` 链接
- **AND** 页面不展开完整开放平台操作教程

#### Scenario: App ID 与 App Secret 为新增必填项
- **WHEN** 用户新增飞书 channel 但未填写 App ID 或 App Secret
- **THEN** 页面在对应字段显示必填错误
- **AND** 不提交不完整配置

#### Scenario: 节点在线时保存后立即连接
- **GIVEN** Agent 所属节点在线且用户提交有效 App ID 与 App Secret
- **WHEN** IM 成功保存飞书 channel
- **THEN** 页面进入等待应用或连接中状态
- **AND** 用户无需编辑本地配置文件或重启 Gateway

### Requirement: Channel 期望配置版本化且与实际运行状态分离

IM 持久化外部 channel 的期望配置，并对每个 channel 使用 revision 乐观锁。Gateway 上报最近处理的 revision 和实际运行状态。保存成功只表示期望配置已持久化；节点未处理该 revision 时，页面显示等待应用，不得显示已连接。

#### Scenario: 在线保存后显示真实运行结果
- **GIVEN** Agent 所属节点在线
- **WHEN** 用户保存一个有效飞书 channel
- **THEN** IM 先返回已保存/等待应用语义
- **AND** Gateway 处理后，页面通过状态事件更新为已连接、连接受限或连接失败

#### Scenario: 节点离线时保存最终期望状态
- **GIVEN** Agent 所属节点离线
- **WHEN** 用户新增、修改、启用、停用或删除 channel
- **THEN** IM 接受并持久化最终期望状态
- **AND** 页面显示“配置已保存，等待节点上线应用”
- **AND** 节点重连后 IM 下发完整 channel manifest，使 Gateway 无需用户再次保存即可收敛

#### Scenario: 首次人工绑定完成后继续 channel 初始化
- **GIVEN** Gateway 已注册但节点尚未绑定 owner，channel control 尚未初始化
- **WHEN** 用户完成人工绑定且 Gateway WebSocket 仍在线
- **THEN** IM 在绑定提交后继续 channel bootstrap，无需节点重连
- **AND** register、绑定确认和后续重连的重复触发最多初始化一次 manifest head
- **AND** owner 未绑定期间不创建归属不明的 channel 配置

#### Scenario: 并发更新发生 revision 冲突
- **GIVEN** channel 已被另一客户端更新到新 revision
- **WHEN** 当前客户端携带旧 revision 保存或删除
- **THEN** IM 返回 conflict 和最新 channel view
- **AND** 不覆盖较新的配置

### Requirement: Channel 凭据写入后保持不透明

IM 接受新增或显式替换 channel 凭据，但持久化前使用目标节点公钥封装。读取接口、用户事件、错误和日志只表达凭据是否已配置，不返回明文或密文 envelope。编辑时用户可以保留现有凭据或显式替换，不能用空字符串隐式覆盖。

#### Scenario: 已保存 App Secret 不回显
- **GIVEN** 飞书 channel 已保存 App Secret
- **WHEN** 用户重新打开编辑页或调用 channel GET/list
- **THEN** 响应只表明 secret 已配置
- **AND** 不包含原始 secret 或 credential envelope

#### Scenario: 更换 App ID 时必须同时替换 App Secret
- **GIVEN** 飞书 channel 已保存一组 App ID 与 App Secret
- **WHEN** 用户把 App ID 改为另一个应用
- **THEN** 页面要求显式选择替换并填写新 App Secret
- **AND** 不允许保留旧应用的 App Secret 提交

#### Scenario: 离线节点已有缓存公钥时可替换凭据
- **GIVEN** Agent 节点离线，但 IM 已缓存该节点 credential public key
- **WHEN** 用户提交新的 App Secret
- **THEN** IM 封装并保存新凭据，状态等待节点应用

#### Scenario: 节点尚无 credential public key
- **GIVEN** IM 从未获得目标节点 credential public key
- **WHEN** 用户尝试新增或替换 secret
- **THEN** IM 拒绝该凭据写入
- **AND** 页面说明需让节点至少上线一次，不把它误报成飞书凭据错误

### Requirement: Channel 状态诊断可操作且区分 missing 与 unknown

IM 保存并向页面展示 Gateway 上报的 channel 连接状态、诊断状态和检查项。连接可用但权限不完整时允许降级使用；每个确认缺失项显示原始权限、受影响能力和修复方向。检查本身失败时显示无法确认，不得编造缺失权限。

#### Scenario: 权限不足时显示连接受限
- **GIVEN** 飞书基础链路可用，但 Gateway 确认缺少一项或多项权限
- **WHEN** 用户查看 channel
- **THEN** 页面显示“连接受限”
- **AND** 逐项显示缺失权限、影响和修复方向

#### Scenario: 普通群消息权限缺失
- **GIVEN** Gateway 确认缺少 `im:message.group_msg`
- **WHEN** 用户展开诊断
- **THEN** 页面说明未 @Bot 的群消息不会进入群背景上下文

#### Scenario: 权限检查不可用
- **GIVEN** 飞书连接可用，但 Gateway 暂时无法读取 scope 列表或确认某项平台配置
- **WHEN** 用户查看诊断
- **THEN** 页面显示“权限状态暂时无法确认”或等效 unknown 状态
- **AND** 不把检查失败显示为某项权限确定缺失

#### Scenario: 凭据、Bot 或连接无效时给出下一步
- **GIVEN** Gateway 已确认 App Secret 无效、应用未启用 Bot、worker 退出或连接无法建立
- **WHEN** 用户查看 channel
- **THEN** 页面显示“连接失败”和可理解的具体原因
- **AND** 根据原因提供编辑凭据、检查 Bot 配置或重新连接的下一步
- **AND** 不把连接失败混同为权限受限

#### Scenario: 连接暂时中断时显示恢复过程
- **GIVEN** channel 此前已连接
- **WHEN** Gateway 上报连接暂时中断并开始恢复
- **THEN** 页面稳定显示“正在重新连接”和最后状态时间
- **AND** 自动恢复后更新为实际终态
- **AND** 自动恢复失败时保留手动重新连接入口，不丢失已保存配置

#### Scenario: 显示最近一次运行状态更新时间
- **GIVEN** Gateway 已至少上报过一次 channel 状态
- **WHEN** 用户查看 channel 卡片
- **THEN** 页面显示 IM 最近收到该状态的时间
- **AND** 不使用 desired config 的更新时间冒充运行状态更新时间
- **AND** 节点离线时把该值标为最后状态而非当前在线证明

#### Scenario: 同 revision 的旧运行状态不逆序覆盖
- **GIVEN** IM 已接收某次 runtime incarnation 的较新状态 sequence
- **WHEN** 同一 channel revision 的旧 sequence 或旧 runtime 状态迟到
- **THEN** IM 保留较新的运行状态
- **AND** 页面不会从已恢复错误回退为旧重连状态，也不会被旧 connected 覆盖新失败

### Requirement: Channel 生命周期不级联删除聊天历史

IM 支持编辑、启用、停用、手动重连和删除外部 channel。删除只移除期望配置和凭据；外部 channel 已产生的影子会话、消息和 Agent 会话历史不被级联删除。

#### Scenario: 停用前要求用户确认
- **GIVEN** 一个已启用的 channel
- **WHEN** 用户选择停用
- **THEN** 页面先说明停用后不再收发、配置和凭据仍会保留
- **AND** 用户取消时不提交变更
- **AND** 用户确认后才保存 disabled 期望状态，并在 Gateway 尚未应用时显示等待应用或正在停用

#### Scenario: 停用与重新启用
- **WHEN** 用户停用已连接 channel
- **THEN** 页面显示已停用，Gateway 后续不再通过该 channel 收发
- **WHEN** 用户重新启用
- **THEN** Gateway 使用已保存凭据重新连接，无需用户重填

#### Scenario: 删除 channel 后保留历史
- **GIVEN** 飞书 channel 已产生影子会话和消息
- **WHEN** 用户确认删除 channel
- **THEN** IM 立即删除期望配置和凭据，并在 Gateway 尚未应用时显示持久的“删除待应用”状态
- **AND** 节点离线或页面 reload 后仍不渲染空态，也不能重复添加同 provider
- **AND** Gateway 确认旧 channel 已停止后，删除中的条目才从列表移除，后续不再收发
- **AND** 停止失败时页面显示具体原因和重新尝试入口
- **AND** 既有影子会话和消息仍可读取

#### Scenario: 手动重连
- **GIVEN** channel 仍存在且节点在线
- **WHEN** 用户发起重新连接
- **THEN** 页面显示连接进度和最终结果
- **AND** 该动作不创建新的 channel revision

## MODIFIED Requirements

### Requirement: 设备绑定把节点归属到当前用户

终端用户在本机发起绑定：`POST /im/v1/bind {action:"start", node_id}` 取得绑定链接，浏览器登录后以 `{action:"confirm", bind_id|bind_token}` 确认。节点尚无 owner 时，确认把节点及其 Agent 归属到当前用户；节点已归属当前用户时保持幂等；节点已归属其他 owner 时拒绝确认，不迁移节点、Agent 或 channel 控制面数据。缺必填字段大声失败（400），不静默。

#### Scenario: start 返回绑定结构
- **GIVEN** 已授权用户、一个已知节点
- **WHEN** 用户 `POST /im/v1/bind {action:"start", node_id}`
- **THEN** 201 返回 `{bind_id, node_id, user_id, status, bind_url, created_at, confirmed_at}`

#### Scenario: 首次确认把未归属节点绑定到当前用户
- **GIVEN** 节点尚无 owner
- **WHEN** 当前用户确认该节点的有效绑定请求
- **THEN** IM 把节点及其上 Agent 归属到当前用户
- **AND** 绑定提交后可以初始化该 owner 的 channel control

#### Scenario: 同 owner 重复绑定保持幂等
- **GIVEN** 节点已经绑定当前 owner
- **WHEN** 当前 owner 再次确认该节点绑定
- **THEN** IM 保持原 owner、Agent 与 channel 数据不变
- **AND** channel initialization 可以安全重试

#### Scenario: 另一个 owner 尝试绑定现有节点
- **GIVEN** 节点已经绑定 owner A，并保存或运行其外部 channel
- **WHEN** owner B 确认同一 node 的新绑定请求
- **THEN** IM 返回 `node_owner_transfer_not_supported`
- **AND** 不修改 node、Agent profile、channel、manifest head、removal 或 credential key 的 owner
- **AND** owner B 不能读取或控制 owner A 的 channel

#### Scenario: 缺动作必填字段返回稳定 400
- **WHEN** `start` 缺 `node_id`
- **THEN** 400 `{detail:"node_id is required for start"}`
- **WHEN** `confirm` 缺 `bind_id` 且缺 `bind_token`
- **THEN** 400 `{detail:"bind_id or bind_token is required for confirm"}`
