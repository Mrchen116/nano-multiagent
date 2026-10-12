# gateway/relay-protocol Specification (delta for refactor-581)

## MODIFIED Requirements

### Requirement: Gateway 为同节点历史会话生成 distill prompt

IM 请求已选择的同节点 source conversations 的 distill prompt 时，Gateway 用自己持有的 durable
conversation/session binding 在本机解析迁移后DSH历史的可读导出paths，并复核 execution Agent 的
`conversation-skill-distiller` 和对应DSH原生Skill加载能力。它以 request_id 返回当前普通
`conversation-skill-distiller` 消息格式的 prompt 或 actionable error。Gateway 不返回 transcript 内容，也不执行
模型或 skill；后续由 IM 固定路由的普通聊天 relay 回到同一 Gateway 并按该 prompt 读取本机 paths。对已有
external shadow conversation，Gateway 先查常规 `web_relay` binding；仅当它不存在时，才用 IM 从已授权 shadow
record 附带的既有 external identity 查常规 external binding。这个 fallback 不成为 browser 或 ordinary relay 字段。

#### Scenario: 本机 binding 生成可直接预填的 prompt
- **GIVEN** 所有 source conversation/Agent 与 execution Agent 都属于当前 Gateway，且 source 有本机可读 binding
- **WHEN** Gateway 收到 `node.distill.prompt.request`
- **THEN** 它以相同 request_id 和 node_id 返回当前 distiller 格式的 prompt，包含 slash command、全部本机历史导出paths、execution Agent 与 scope
- **AND** 不读取 transcript、不启动模型、不创建 session 或 skill

#### Scenario: 任一 source 不能解析时不返回部分 prompt
- **GIVEN** 至少一个 source binding 缺失、path 不可读或不是当前 Gateway 的本机 source
- **WHEN** Gateway 收到 prompt request
- **THEN** 它以相同 request_id 和 node_id 返回可理解错误而非部分 prompt
- **AND** 不读取其余 transcript、不启动模型、不创建 session 或 skill

#### Scenario: execution Agent 缺少 distiller 能力时不返回 prompt
- **WHEN** Gateway 收到 prompt request，但 execution Agent 缺少 `conversation-skill-distiller` 或对应DSH原生Skill加载能力
- **THEN** 它以相同 request_id 和 node_id 返回可理解错误
- **AND** 不读取 transcript、不启动模型、不创建 session 或 skill

#### Scenario: 已有 external shadow source 沿用 external binding
- **GIVEN** source 是同节点的已有 external shadow conversation，且没有 `web_relay` binding、但其既有 external binding 存在
- **WHEN** Gateway 收到由 IM 授权 shadow record 补充 external identity 的 prompt request
- **THEN** Gateway 用该 external binding 解析本机历史导出path 并返回当前格式 prompt
- **AND** browser 不获得或提交 external identity

#### Scenario: 开发态不适配旧内核档案
- **WHEN** source指向迁移前旧内核历史
- **THEN** 返回明确不支持的错误，不生成部分prompt，也不读取或删除旧档案。

### Requirement: Gateway 受 IM 委托对某 agent 会话按 fork 点 fork 出独立新会话

IM 不持有 conversation↔session 映射、也不直读 Gateway 侧会话日志，故「让分支单聊的 agent 记得历史」由 Gateway 受委托完成。Gateway 收到 IM 的 fork 请求后：复制**源会话在指定 fork 点那一刻所用的上下文视图**（源若已压缩则含当时的压缩摘要；未压缩则为到 fork 点的完整内容），生成一个独立的新会话，并把请求里的新 conversation 预绑定到该新会话——之后该新会话的首条入站消息命中预绑定、agent 带着「与源在 fork 点时一致」的记忆回复。新会话独立：对它的后续追加不回流源会话。

#### Scenario: 受委托 fork 后新会话带源在 fork 点的记忆
- **GIVEN** 一个迁移后已有多轮对话的Agent会话，IM 经 WS RPC 请求对它在某 agent 回复处 fork 出新 conversation
- **WHEN** Gateway 处理该 fork 请求
- **THEN** Gateway 生成一个新会话，其上下文 = 源会话在该 fork 点那一刻所用的视图；新 conversation 被绑定到该新会话；该会话首条入站消息复用此绑定、不另建空会话
- **AND** 用户在新 conversation 继续对话时，agent 表现出对这段历史的记忆

#### Scenario: fork 复刻源在 fork 点的上下文（含压缩态），与源体验一致
- **GIVEN** 源会话在 fork 点之前曾发生过上下文压缩（喂模型时历史被摘要替代）
- **WHEN** Gateway 受委托 fork 该会话到该 fork 点
- **THEN** 新会话复制的是源在该 fork 点的视图（含当时已生效的压缩摘要），与源在该点的记忆一致——不还原压缩前的完整原始历史（不比源记得更多），也不丢失源当时已有内容

#### Scenario: fork 点之后的源历史不进入新会话、两会话独立
- **GIVEN** fork 点之后源会话还有更晚的对话
- **WHEN** fork 完成后用户在新会话与源会话各自继续对话
- **THEN** 新会话不含 fork 点之后的源历史；两会话各自独立演进，互不影响对方记忆

#### Scenario: fork 失败回包让 IM 可回滚
- **GIVEN** Gateway 处理 fork 请求时失败（如源会话绑定缺失、运行时fork出错）
- **WHEN** Gateway 回复该 WS RPC
- **THEN** 回包标明失败，IM 据此回滚已建的新 conversation；Gateway 不留下半成品绑定

#### Scenario: 分支沿用消息点配置
- **WHEN** 用户从迁移后消息分支
- **THEN** 新会话初始装配使用消息点对应配置快照，不能用当前其他会话配置替代。

#### Scenario: 开发态不兼容旧消息分支
- **WHEN** fork目标是迁移前旧内核消息
- **THEN** 返回明确不支持的错误，不转换旧上下文或生成摘要交接分支。
