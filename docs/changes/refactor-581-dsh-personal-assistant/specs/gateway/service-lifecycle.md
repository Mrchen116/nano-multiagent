# gateway service-lifecycle Specification (delta for refactor-581)

## ADDED Requirements

### Requirement: 节点产品与执行运行时状态分别可观察且由节点统一管理

#### Scenario: 启动后区分在线和可执行
- **WHEN** 个人助手节点启动并连接IM，但执行运行时尚未就绪
- **THEN** 状态如实区分渠道在线与Agent可执行，不把接收连接成功当作模型已可工作；就绪后既有个人助手入口可用。

#### Scenario: 执行运行时退出后恢复
- **WHEN** 执行运行时退出而节点产品仍可运行
- **THEN** 保留已接收业务输入、发送回执和真实中断状态；受管恢复后新会话按正确数字人配置恢复，不能把未知结果伪装成成功或盲目重放副作用。

#### Scenario: 停止所属进程
- **WHEN** 运维者停止该节点
- **THEN** 停止新的工作接收/派发并收拢节点管理的运行时和子任务，保留需要恢复的业务事实，不停止其他节点或无关进程。

#### Scenario: 旧Coding CLI退役
- **WHEN** 用户安装最终迁移版本并查看启动入口
- **THEN** 个人助手启停、IM管理和客户端入口继续可用，旧自研Coding CLI不再作为产品入口或运行依赖。
