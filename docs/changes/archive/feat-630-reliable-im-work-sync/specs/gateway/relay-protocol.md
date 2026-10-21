# Gateway relay-protocol Specification (delta for feat-630)

## MODIFIED Requirements

### Requirement: Gateway 为 IM 数据调用使用当前连接的运行凭据

消息镜像与附件等原机器数据继续使用当前注册连接凭据。仅 Work 专用同步采用当前有效设备绑定的持久机器身份，可在 WS 暂断时补传；不得将该身份跨用真人、管理或其他机器入口。

#### Scenario: 注册后处理机器 HTTP 数据
- **WHEN** Gateway 完成 owner 登录、绑定及节点注册
- **THEN** 从注册 ACK 获取当前 node 的运行凭据，图片交付／下载和 shadow 数据请求使用该凭据；不把它放入附件 URL、模型输入、外部请求或日志。

#### Scenario: shadow 身份校验与镜像数据分别认证
- **GIVEN** Gateway 正在恢复旧 owner 记录或处理新的外部镜像消息
- **WHEN** 同步流程需要核实当前机器管理者、校验节点归属并向 IM 写入镜像数据
- **THEN** 按 IM 的机器身份契约，通过当前注册运行凭据查询 `GET /im/v1/gateway/identity`，核对当前 node_id 与 owner_id 后沿用已有 owner 调和及镜像路径；不使用真人 `/me` 或节点管理列表，也不信任本地旧 owner 作为授权事实。身份校验失败时保留待同步记录，不改用真人凭据写机器数据；运行凭据仍不能读取账号和设备管理入口。此处对齐既有 IM 规则，不增加外部镜像能力或放宽其认证。

#### Scenario: IM 连接恢复后继续镜像
- **GIVEN** IM 或连接暂时不可用
- **WHEN** Gateway 重连注册成功并重试已有持久镜像或附件操作
- **THEN** 现取新运行凭据并沿用原请求身份，不重复交付；等待 IM 的镜像不阻断外部聊天的既有主路径。

#### Scenario: Work 独立于实时连接恢复
- **GIVEN** 设备绑定、账号和 epoch 有效，但实时连接暂不可用
- **WHEN** Gateway 同步本节点的待补工作记录
- **THEN** 使用仅限 Work 专用入口的持久机器身份，不等待重注册取得临时运行凭据；撤销或交接后旧身份被拒绝。

#### Scenario: 新节点接入不支持可靠同步的旧中心
- **WHEN** 新节点发现中心缺少必要的请求关联或独立 Work 同步能力
- **THEN** 明确要求先升级中心，保留本机输入与待同步记录，不退回以大帧阻塞实时请求的旧路径。

