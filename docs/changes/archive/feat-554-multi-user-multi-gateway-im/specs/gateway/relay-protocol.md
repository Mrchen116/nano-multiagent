# feat-554 — gateway/relay-protocol

> 目标: docs/specs/gateway/relay-protocol.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## MODIFIED Requirements

### Requirement: Gateway 向 IM 中继的工具调用携带授权决策

Gateway 把内核工具执行事件中继到 IM 时，除既有的 reason 徽标 / emoji / presentation detail 外，一并透传「该工具调用是否经用户显式授权/拒绝」的标识；自动放行的调用不携带。

#### Scenario: 经用户授权的工具调用被中继
- **WHEN** 内核报出一次经用户允许的工具调用执行
- **THEN** Gateway 中继给 IM 的该工具调用数据携带「经用户授权允许」标识

#### Scenario: 经用户拒绝的工具调用被中继
- **WHEN** 内核报出一次经用户拒绝的工具调用
- **THEN** Gateway 中继的该工具调用数据携带「经用户拒绝」标识

#### Scenario: 单 Thread 多人卡片决定返回原执行
- **GIVEN** Gateway 上报一张带稳定请求与执行身份的批准卡
- **WHEN** IM 转交任一聊天真人成员的决定，并可能在重连后重传
- **THEN** Gateway 仅处理与原请求匹配的执行，同一请求只生效一次，已结束请求不触发新的工具执行；解析结果及实际决定反馈到同一聊天。

## ADDED Requirements


### Requirement: Gateway 为 IM 数据调用使用当前连接的运行凭据

#### Scenario: 注册后处理机器 HTTP 数据
- **WHEN** Gateway 完成 owner 登录、绑定及节点注册
- **THEN** 从注册 ACK 获取当前 node 的运行凭据，图片交付／下载和 shadow 数据请求使用该凭据；不把它放入附件 URL、模型输入、外部请求或日志。

#### Scenario: shadow 身份校验与镜像数据分别认证
- **GIVEN** Gateway 正在恢复旧 owner 记录或处理新的外部镜像消息
- **WHEN** 同步流程查询真实账号、校验节点归属并向 IM 写入镜像数据
- **THEN** `/im/v1/me` 和 `/im/v1/nodes` 继续使用 owner JWT，原有真实身份校验及旧 owner 恢复保持有效；镜像数据请求使用当前节点运行凭据。身份校验失败时保留待同步记录，不冒用本地 owner 或改用真人凭据写机器数据；运行凭据仍不能读取账号和设备管理入口。

#### Scenario: IM 连接恢复后继续镜像
- **GIVEN** IM 或连接暂时不可用
- **WHEN** Gateway 重连注册成功并重试已有持久镜像或附件操作
- **THEN** 现取新运行凭据并沿用原请求身份，不重复交付；等待 IM 的镜像不阻断外部聊天的既有主路径。
