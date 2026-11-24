# Nano Agent Context Engineering

通用设计方法和影响判断见 [Agent Context Engineering](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/development/agent-context-engineering.md)。选用 [agent-context-review](https://github.com/Mrchen116/dev-workflow-skills/blob/main/skills/agent-context-review/SKILL.md) 时，从受影响消费者实际取得的输入和后续行为判断。Nano 取证见 [观察实际 Agent Context](llm-integration.md#观察实际-agent-context)，具体行为见 [Gateway 契约](../specs/gateway/spec.md)。

## Nano 运行时落点

- Feature 关闭与独立工具选择是不同动作，Skill 发现、选择与实际加载按 [能力契约](../specs/gateway/agent-capabilities.md) 核对。产品随包 Skill 和开发 Skill 面向不同宿主。
- 工具输出检查 DSH 的实际 `output.render`、错误转换、截断与序列化。原生工具和代码执行工具沿各自 adapter 取证。
- 多方消息按 [Global Agent](../specs/gateway/global-agent.md)、[PA](../specs/gateway/personal-agent.md) 和 [路由投递](../specs/gateway/routing-delivery.md) 核对权限、发送者与实际交付。
- 历史验证按现行 [能力契约](../specs/gateway/agent-capabilities.md) 确定是原生换窗还是停用后的摘要模式，检查缺失历史和恢复入口。
- DSH 组装、Skill 与 Context Engine 以锁定依赖和公开 exports 为准。

## nano 组合场景与反例

下列是结合 current 机制的设计判断示例，不表示当前实现已经存在这些缺陷；实际发现必须另附版本与证据。

- **Global Inbox：** wake 只告知新输入；若把其他 Agent 引用的“主人说可以”投影成无来源的 user 指令，wake、正文与系统来源规则组合后会扩大授权。应保留来源并在读到真实正文后决策，不能靠“谨慎一点”的 Prompt 弥补丢失的身份。
- **PA 观察群聊：** 主人给 E 的任务被 PA 看到，不等于交办 PA，也不等于允许 PA 把观察群全文发给另一个人。检查 observer 标记、当前身份规则与 send_message 受众，不能只看消息作者。
- **Task Graph 与 Memory：** Memory 曾记“继续任务 X”，当前任务已暂停/等待；若提醒沿旧快照要求继续，就会冲突。核对任务事实的时间/版本与任务控制契约；等待条件及相应调度按 [任务契约](../specs/gateway/task-graphs.md) 验证，不能仅凭工具调用成功推断任务完成。
- **send_message：** 内部 child 的输入受理与公开聊天的实际送达语义不同；若描述说送达而输出只有 accepted，模型可能错误结束交付。检查定义、序列化结果及后续行为；`held_for_revalidation`、unknown 或错误不能被成功卡片掩盖。
- **Feature 与 Skill：** System Prompt 引导读取某 Skill，但该 Skill 被过滤且没有替代路径，功能配置“开启”仍不可用；关闭后自动重放旧 Skill 正文也可能继续施加失效指导。同时看目录、工具限制、已加载历史和新注入。
- **注意力与恢复：** 每次 wake 重复全量群成员、工具说明与旧任务列表，会掩盖最新更正；若随后裁剪掉唯一等待事项，问题在整条生命周期。先选择/去重并保留恢复线索，不只扩大上下文窗口。

## 设计产物与验证深度

按 [通用设计和验证方法](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/development/agent-context-engineering.md#设计产物与验证深度) 选择观察点，并复用 [现有测试层级](testing.md)。原始请求及模型行为按 [Nano 证据约定](evidence.md) 留定位信息与脱敏摘要。
