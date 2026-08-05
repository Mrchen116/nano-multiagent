# Gateway Agent Capabilities Specification (delta for feat-502)

## ADDED Requirements

### Requirement: PA 产品说明书按需回答产品问题

PA 随当前安装版本提供可选的产品说明书 skill，覆盖 Web IM、Gateway、Agent 配置、模型、skills、tools、memory、heartbeat、cron、外部渠道、启动和常见故障处理。启用该 skill 的 Agent 在相关问题上按需读取；普通任务不因其启用而加载。coding CLI、Kernel 内部和开发流程不属于该手册。

#### Scenario: 在 PA 对话入口询问产品问题

- **GIVEN** 当前 Agent 已启用产品说明书与 `skill_view`
- **WHEN** 用户从 Web IM、飞书或其他 PA 对话入口询问 PA 能力、使用、配置或故障处理
- **THEN** Agent 按需读取产品说明书，并基于当前安装版本直接回答

#### Scenario: 普通任务不加载产品说明书

- **WHEN** 用户提出与 PA 产品自身无关的普通任务
- **THEN** Agent 不因为产品说明书处于启用状态而读取它

#### Scenario: 基础问答离线可用

- **WHEN** 用户询问当前安装版本的 PA 产品能力或使用方法
- **THEN** Agent 可只依据随包手册回答，不要求远端文档服务

#### Scenario: 最新版与本机版本分开回答

- **WHEN** 用户明确询问最新版、升级变化或远端当前行为
- **THEN** Agent 区分查到的官方远端信息与本机安装版本，不把远端行为表述为本机已经具备
- **AND** 远端信息不可用时明确限定为本机手册事实

#### Scenario: 现场状态以实际核实为准

- **WHEN** 用户询问自己的 Agent、节点、渠道或任务当前状态
- **THEN** Agent 在能力允许时核实现场后回答，并区分产品规则与观察结果
- **AND** 无法核实或手册未覆盖时明确不确定，不编造能力、配置或处理步骤

## MODIFIED Requirements

### Requirement: PA 内置 skill 启动自举

Gateway 随包提供 PA 产品说明书与当前产品定义的完整 Lark skill bundle。启动时，Gateway 以当前安装包完整刷新运行态全局 skill root 中所有随包内置名称的目录；这些名称是 PA 托管资源，本地修改和旧版本额外文件不保留。名称不属于当前随包内置集合的用户 skill 不受影响。资源刷新不改变 Agent 的 skills 选择。绑定 Feishu channel 的 Agent 能发现完整 Lark bundle，并默认沿用 Gateway 所在机器已登录的 Lark 用户身份；只有各 skill 的既有规则明确要求时才使用其他身份。

#### Scenario: 新安装发现产品说明书与完整 Lark bundle

- **WHEN** Gateway 使用一个没有 PA 内置 skill 的全局 root 启动
- **THEN** Agent capabilities 和会话可发现产品说明书与完整 Lark skill bundle

#### Scenario: 升级刷新全部随包内置 skills

- **GIVEN** 全局 root 中已有旧版或本地改写的 PA 内置 skill 目录
- **WHEN** 新版本 Gateway 启动
- **THEN** 当前包仍声明的每个内置名称都呈现包内完整内容，旧版额外文件不残留

#### Scenario: 非内置用户 skill 保持不变

- **GIVEN** 全局 root 中存在名称不属于 PA 随包内置集合的用户 skill
- **WHEN** Gateway 刷新内置 skills
- **THEN** 该用户 skill 的目录和内容保持不变

#### Scenario: 刷新失败保留旧完整目录并继续启动

- **GIVEN** 某个内置 skill 在 staging 或切换时失败，且目标已有旧完整目录
- **WHEN** Gateway 执行启动刷新
- **THEN** 该名称恢复旧完整目录、其他名称继续刷新，Gateway 继续启动并暴露失败原因

#### Scenario: 显式 skill allowlist 不因资源刷新改变

- **GIVEN** 某 Agent 已保存显式 skills 列表并关闭部分内置 skills
- **WHEN** Gateway 刷新资源、连接或重连 IM
- **THEN** 该 Agent 的启用和关闭选择保持不变

#### Scenario: 显式 skill allowlist 的飞书 Agent 获得完整 bundle

- **GIVEN** 飞书绑定 Agent 的本地 skills allowlist 非空且缺少一个或多个 Lark skill
- **WHEN** Gateway 启动静态 `config.channels` 中的该飞书 channel，或调和 IM 托管的该飞书 channel
- **THEN** Gateway 保留已有条目并将完整 Lark skill bundle 加入 allowlist
- **AND** 重复调和不会重复写入或重复列出 bundle skill

#### Scenario: 空 skill allowlist 保持默认发现语义

- **GIVEN** 飞书绑定 Agent 的本地 skills allowlist 为空
- **WHEN** Gateway 启动或调和该飞书 channel
- **THEN** Gateway 不将完整 bundle 物化写入该 allowlist
- **AND** 该 Agent 仍按默认全局 skill discovery 发现内置 skills

#### Scenario: 静态 Feishu Agent 的 IM profile ingress 保留完整 bundle

- **GIVEN** Gateway 的静态 `config.channels` 绑定了一个 skills allowlist 非空的 Feishu Agent
- **AND** IM 中该 Agent 已存在一个尚未包含完整 Lark skill bundle 的 mirror profile
- **WHEN** Gateway 连接、重连 IM，或接收该 Agent 的 `config.sync` profile 更新
- **THEN** Gateway 将完整 Lark skill bundle 补齐到该 Agent 的显式 profile 后再应用到本地运行态
- **AND** 该 Agent 后续会话仍可发现完整 Lark skill bundle

#### Scenario: 用户明确请求独立 Lark 事件监听

- **WHEN** 用户要求飞书绑定 Agent 监听并处理一种 Lark 事件
- **THEN** Agent 可使用内置 Lark event skill 建立独立监听
- **AND** 普通 Gateway Feishu 对话的入站与回复所有权不转交给该独立监听
