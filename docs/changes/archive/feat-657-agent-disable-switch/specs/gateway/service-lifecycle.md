# gateway service-lifecycle Specification (delta for feat-657)

## ADDED Requirements

### Requirement: Agent 停用终止全部受管执行并持续禁止唤醒

#### Scenario: 停止整个 Agent
- **WHEN** 主人停用 Agent
- **THEN** 立即禁止新执行，并停止跨聊天主会话、所有层级子 Agent、前后台 Bash、持久终端及其他受管后台工作
- **AND** 不等待模型决定是否停止，其他独立 Agent 继续工作
- **AND** 按 DSH 的平台受管范围确认清理，未确认全部停止时不能报告已停用

#### Scenario: 自动输入与恢复
- **GIVEN** Agent 被停用
- **WHEN** 收到消息、提及、Task、Heartbeat、Schedule、子任务回报或自动恢复信号
- **THEN** 均不能启动模型或工具，不能补发旧输出；停用跨节点重启和重连保持

#### Scenario: 节点离线时请求停用
- **WHEN** 节点尚未收到停用请求
- **THEN** 中心保留意图并阻断新的中心路由，明确等待节点确认；重连时先应用停用后处理普通恢复

#### Scenario: 保留记录和管理能力
- **WHEN** Agent 已停用或全部 Agent 均停用
- **THEN** 已有工作记录和历史仍按原权限可读，生命周期、模型设置及已保存普通配置等不需执行的管理仍可用，读取历史不唤醒 Agent
- **AND** 依赖执行的插件操作与能力探测保留最近已知信息并明确不可执行，不为读取临时启动停用 Agent

#### Scenario: 旧共享运行数据升级
- **GIVEN** 节点仍使用旧共享运行目录
- **WHEN** 启动采用独立 Agent 进程的新版本
- **THEN** 明确要求先停止旧服务并完成离线迁移的规划、执行和校验；普通启动不扫描复制全部历史，不自动拆分数据
- **AND** 迁移保留原始源数据，校验成功后才发布新目录布局；进程拓扑以仓库 `SPEC.md` 为权威

#### Scenario: 已提交的外部动作
- **WHEN** 停用前外部系统已经接受动作，或进程已超出 DSH 可管理范围
- **THEN** 保留真实结果或未知状态，不把停止描述成副作用回滚；不扩展到其他独立 Agent 或远端服务
