# Gateway Relay Protocol — feat-583 delta

Target：[docs/specs/gateway/relay-protocol.md](../../../../specs/gateway/relay-protocol.md)

## ADDED Requirements

### Requirement: Gateway 为被授权的精确执行提供只读原生轨迹观察

#### Scenario: 中心请求当前节点所属执行
- **GIVEN** 请求经已认证 IM 连接到当前节点，指向该节点全局 Agent 的主执行或真实后代
- **WHEN** IM 发起原生轨迹读取或观察
- **THEN** Gateway 复核本机绑定和执行归属，通过运行时公开读取能力返回真实历史和观察更新。
- **AND** 不因读取而激活或创建 Agent、提交输入、执行工具或修改配置。

#### Scenario: 执行不属于该 Agent 或读取操作越界
- **WHEN** 请求指向其他 Agent 的执行，或要求提交、审批、取消、配置或其他非只读操作
- **THEN** 拒绝请求，不执行部分操作或尝试扩大权限。

### Requirement: 轨迹观察跟随查看生命周期，不改变任务生命周期

#### Scenario: 查看者离开或观察链中断
- **WHEN** IM 关闭某项观察，或其认证连接／节点连接／运行时中断
- **THEN** Gateway 释放对应读取与订阅，旧观察结果不能进入新观察。
- **AND** 不取消实际任务、不重发任务；恢复查看时从原生真实记录继续检查。

#### Scenario: 慢查看者不阻塞执行交付
- **WHEN** 某查看者无法及时接收轨迹更新
- **THEN** 该观察有界失败且可重新读取，不因此阻塞 Agent 执行或正常消息投递。

### Requirement: 原生附件副本不扩大原聊天访问权

#### Scenario: 读取来源于聊天的原生附件
- **WHEN** IM 请求原生记录引用的聊天附件
- **THEN** Gateway 提供可信来源供 IM 按原有媒体权限授权，授权通过后才返回对应字节。
- **AND** 来源无法证明时明确不可预览，不以文件路径或模型声明替代授权证据。

#### Scenario: 读取来源于工作区的原生图片
- **WHEN** 请求图片的可信来源为成功读图工具读取的所属工作区文件
- **THEN** 仅在原生记录确实引用该图片时提供预览；不接受查看者提交的任意文件路径。
- **AND** 来源记录失败使预览不可用，但不会阻断正常业务输入。
