# perf-609: 缩短本仓模型工具引用

## Relations

- Depends on: 无。
- Related: 已有 Gateway global Agent、外部聊天与 Workflow 行为。

## 原始诉求

> 现在代码中的会话id规则是啥，这么贵长的id，简直浪费token

> 举一反三，看看还有没有其他工具，需要agent写这种没啥意义的超长id

> `schedule_update/delete/run/history.id`是DSH自己的设计是吧，DSH内置的设计我们暂时不动，只考虑我们本仓做的

> 就按这个方案改，快修模式

## 澄清记录

- 用户先要求确认实际生成规则，再要求检查其他工具的长引用；已查看本仓代码及当前安装的 DSH 依赖。
- 用户明确排除 DSH 内置 schedule 与 subagent ID，不修改依赖、runtime exports 或 native 工具协议。
- 已确认的范围：飞书 target、Inbox/conversations/task_graph 的 cursor、本仓 Workflow runId/resumeFromRunId，以及 Inbox、发送结果和 Workflow 输出中的重复或内部身份字段。
- 已确认短编号由宿主分配并保存映射，不直接截断原路由 ID；已有长引用继续可用。
- 用户明确选用快速开发，允许先实现再补记录；尚未提供实际产品验收确认，unit 保持 active。

## 现状痛点与量化基线

这些字段进入工具结果后需要模型再次抄写。2026-10-14 用固定字符串和真实 `NodeStore.toolReferences` 序列化测量字符长度如下。基线来自改动前生成规则；这是引用字符量比较，不是 tokenizer、计费或生产流量 benchmark。

| 引用样例 | 改前字符数 | 目标上限 | 改后字符数 | 减少 |
|---|---:|---:|---:|---:|
| 飞书私聊 target | 89 | 12 | 12 | 87% |
| Inbox cursor（UUID、offset=4） | 75 | 12 | 10 | 87% |
| conversations cursor（UUID、offset=20、part=0） | 96 | 12 | 10 | 90% |
| task_graph cursor（空查询、用户、排序时间、图与节点） | 202 | 12 | 10 | 95% |
| 新建 Workflow run ID | 36 | 12 | 11 | 69% |

模型不需要理解上述路由、快照或预算身份。后台仍需完整保留它们用于真实投递、权限检查、分页一致性、恢复及统计。

## 目标状态

- 本仓模型工具输出稳定短引用，宿主恢复原目标和分页状态后进入原权威处理链。
- 多个 Agent、工具与查询之间不能因引用缩短而串用身份或分页状态。
- Inbox 单页会话目标只出现一次；发送结果不重复返回相同 target/conversation_id；Workflow 模型结果不包含父 session、input、budget、重放 hash 与子执行 attempt ID。
- 普通 IM、任务图节点、后台 job 和 DSH 内置工具保持原行为。

## 用户侧验收标准（不变性）

### Requirement: 消息回复和附件仍属于原聊天

#### Scenario: 飞书输入与后续修改
- **WHEN** 用户在飞书发消息、补充修改，助手读取并回复
- **THEN** 与变更前一致，回复发给原收件人，新消息复核有效，图片正常读取，工作记录仍指向真实来源。

### Requirement: 分页与恢复继续可靠

#### Scenario: 分页期间到来新消息并重启
- **WHEN** 助手持有分页引用，期间有新消息到来且节点重启
- **THEN** 继续读取原快照，不漏读、不误吞后来消息，不把其他 Agent 的引用视为访问授权。

### Requirement: Workflow 继续可查询和恢复

#### Scenario: 查询、控制和服务重启后恢复
- **WHEN** 用户查询、暂停、继续或恢复一个 Workflow
- **THEN** 原结果、子调用控制、重放和预算语义保持不变，原有 UUID 仍可定位旧记录。

## 影响范围

仅本仓 `packages/personal-assistant` 与 `packages/dsh-integration`，不改 IM HTTP/relay 的权威身份和游标协议，不改前端、iOS、配置或生产服务。

## 迁移与回滚策略

Node SQLite 新增工具引用表，首次输出时分配并持久化；保留原聊天/消息/快照记录。Workflow 新建运行采用短 ID，旧记录和 UUID 不迁移。回滚代码不会删除原数据，但旧版本不能解释新工具结果中的短 target/cursor，需要保留新版本解析层或重新打开执行上下文；不能宣称任意旧模型上下文可直接回滚复用。
