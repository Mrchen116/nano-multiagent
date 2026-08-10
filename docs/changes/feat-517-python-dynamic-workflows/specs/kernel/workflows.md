# kernel (agent) - Workflows Specification (delta for feat-517)

## ADDED Requirements

### Requirement: 消费者可按会话选择是否向模型提供 Workflow 完整能力

#### Scenario: 会话启用 Workflow
- **GIVEN** 消费者创建或重配置会话时选择了 `Workflow`
- **WHEN** 该会话开始一轮新运行
- **THEN** 模型请求包含 Python Workflow 的完整 tool schema 与使用说明
- **AND** 消费者可查询到 `Workflow` 属于该轮可用工具

#### Scenario: 会话未启用 Workflow
- **GIVEN** 该会话未选择 `Workflow`
- **WHEN** 会话开始一轮新运行或消费者预览其 prompt
- **THEN** 模型请求和预览都不含 Workflow tool schema、使用说明或 Workflow 专属 reminder
- **AND** 名单外的 Workflow 调用不能在执行层运行

#### Scenario: 工具选择在下一轮整体替换
- **GIVEN** 一轮运行已经按启动时工具集开始
- **WHEN** 消费者在该轮进行中增加或移除 `Workflow`
- **THEN** 进行中的该轮保持启动时完整工具集
- **AND** 下一轮整体采用更新后的有或无 Workflow 配置

#### Scenario: opt-in reminder 保持独立 system turn
- **GIVEN** Workflow 已启用且本轮符合可信 keyword 或 session ultracode 条件
- **WHEN** 内核组装最终模型请求
- **THEN** 对应逐字 reminder 作为当前 human message 后的独立尾部 system message 出现
- **AND** reminder 不并入 leading system 或 user text；Workflow 未启用时该 message 不出现

### Requirement: Workflow 接受受限 Python 编排程序并在取得系统能力前拒绝越界脚本

#### Scenario: 合法 Python Workflow 启动
- **WHEN** 模型提交包含 literal metadata、`async def main()` 和受支持 primitives 的 Python script
- **THEN** 工具返回可识别的后台 task/run、持久化 script 路径和诊断目录
- **AND** 调用方无需同步等待 Workflow 完成

#### Scenario: 从 script path 或命名定义启动
- **WHEN** 调用方提供可读的 `scriptPath` 或可发现的 `name`
- **THEN** 内核运行对应 Python script，并把 `args` 作为原结构化值提供给脚本

#### Scenario: 脚本语法或 metadata 不合法
- **WHEN** script 不是合法 Python、缺少必填 metadata 或包含不可计算的 metadata
- **THEN** Workflow 在派发任何子 Agent 前失败，并返回脚本位置和可理解原因

#### Scenario: 脚本尝试直接访问系统能力
- **WHEN** script 尝试 import、读写文件、执行进程、访问网络、反射或动态生成代码
- **THEN** Workflow 在这些副作用发生前拒绝该 script
- **AND** 合法脚本仍可通过子 Agent 的既有工具完成对应工作

### Requirement: Workflow primitives 提供确定的并行、流水线、阶段、嵌套和返回值语义

#### Scenario: parallel 保持输入位置并等待全部分支
- **WHEN** script 以 `parallel` 启动多个 callable
- **THEN** 分支在并发槽内推进，返回集合与输入位置一一对应
- **AND** 单一分支不可恢复失败或被停止时该位置为 `None`，其他分支继续

#### Scenario: pipeline 按 item 独立推进
- **WHEN** script 以多个 stage 处理多个 item
- **THEN** 一个 item 完成当前 stage 后可立即进入下一 stage，不等待其他 item
- **AND** stage 取得前序结果、原 item 与稳定 index

#### Scenario: 并发 Agent 有可恢复的开始顺序
- **WHEN** parallel、pipeline 或一层嵌套 Workflow 产生多个 Agent 调用
- **THEN** parallel 首批调用按输入位置、pipeline 首 stage 按 item index、后续 stage 按前序完成顺序取得全运行唯一的开始序号
- **AND** 同一批完成以 item index 破平，嵌套调用不另起序号空间

#### Scenario: 阶段和日志可观察
- **WHEN** script 调用 `phase()` 或 `log()`
- **THEN** Workflow snapshot 按调用顺序暴露阶段与进度日志，不把它们伪装成主会话普通消息

#### Scenario: 一层嵌套 Workflow
- **WHEN** script 调用一个保存、内置或 path 引用的子 Workflow
- **THEN** 子 Workflow 与父运行共享并发、总 Agent 数、停止信号和 token budget，并把结果返回父脚本
- **AND** 子 Workflow 再嵌套时以明确错误拒绝

#### Scenario: 调度硬上限
- **WHEN** Workflow 超出并发槽、1000 个总 Agent 或一次组合 4096 items
- **THEN** 超出并发槽的工作排队
- **AND** 超出总量或 item 硬上限的请求明确失败，不静默截断

### Requirement: Workflow 子 Agent 复用内核 Agent 能力且不能扩大父会话权限

#### Scenario: 子 Agent 继承父模型、effort 与工具范围
- **GIVEN** 父运行已解析模型、effort 和工具白名单
- **WHEN** Workflow 派发一个未显式覆盖模型或 effort 的子 Agent
- **THEN** 子 Agent 继承父运行的模型、effort 与工具范围
- **AND** 子 Agent 的可用工具不含 `Agent` 或 `Workflow`

#### Scenario: 显式模型、effort、agent type 和 worktree
- **WHEN** `agent()` 明确提供受支持的 model、effort、agent type 或 worktree isolation
- **THEN** 该调用采用有效覆盖，并按现有模型目录、Agent type registry、工具权限和 workspace 安全边界执行

#### Scenario: 进程级 Workflow child 模型最终覆盖
- **GIVEN** 消费者装配了 Workflow child model override
- **WHEN** Workflow 派发子 Agent
- **THEN** 该模型优先于 `agent()` 的 model 与父轮模型
- **AND** 若该模型不在当前 catalog，则改用父轮已解析模型并向消费者显示一次 requested/resolved 替换告警

#### Scenario: 文本结果成为脚本值
- **WHEN** 无 schema 的 Workflow 子 Agent 完成
- **THEN** 它的 final text 原样成为 `agent()` 返回值，不作为面向用户的独立回复

#### Scenario: 结构化结果在 tool-call 层验证
- **WHEN** `agent()` 提供 JSON Schema
- **THEN** 子 Agent 只能以该 schema 约束的结构化 tool call 交付结果
- **AND** 不匹配结果作为可重试的工具错误反馈给子 Agent，脚本不解析 final prose

#### Scenario: 子 Agent 请求额外权限
- **WHEN** 子 Agent 使用父白名单内但当前权限模式仍需确认的能力
- **THEN** child adapter 使用同一 broker request id 向父会话发布既有通用 permission request/resolved 事件，并附 Workflow run/call 关联
- **AND** 交互式消费者的长驻 parent session consumer 在前台父轮结束后仍可响应该 request
- **AND** 无人值守消费者按既有 unattended 策略处理，不出现无人可答的挂起

### Requirement: 消费者可查询和控制持久化 Workflow 运行并只收到一次完成通知

#### Scenario: 查询完整运行快照
- **GIVEN** 一个运行中或已结束的 Workflow
- **WHEN** 消费者经 SDK 查询它
- **THEN** 返回带单调 revision 的完整快照，包含状态、metadata、阶段、Agent、日志、用量、耗时和诊断位置

#### Scenario: 暂停和继续 live run
- **WHEN** 消费者暂停一个运行中 Workflow
- **THEN** 新 Agent 不再开始，已运行 Agent 可收口，快照显示 paused
- **AND** 继续后从同一个 live run 的 checkpoint 恢复派发

#### Scenario: 停止 Agent 或整个 Workflow
- **WHEN** 消费者停止选中 Agent 或整个 Workflow
- **THEN** 选中 Agent 的脚本返回值为 `None`，或整个运行进入 stopped
- **AND** 终态不会继续显示为 running

#### Scenario: 重启选中 Agent
- **WHEN** 消费者重启一个仍在运行的 logical Agent call
- **THEN** 原 attempt 被替换，脚本等待最终取得 replacement result
- **AND** 运行详情仍把它显示为同一个 logical call

#### Scenario: 顶层执行控制流决定 whole-run 终态
- **WHEN** `main()` 正常返回，即使值为空、质量不佳或含 child `None`
- **THEN** Workflow 状态为 `completed`
- **AND** 只有未捕获的顶层异常使其为 `failed`，已接受的 whole-run cooperative stop 使其为 `stopped`
- **AND** runtime 不按 result 文本内容猜测成功或失败

#### Scenario: 终态通知只出现一次
- **WHEN** Workflow 完成、失败或被停止
- **THEN** parent session 收到一条含结果或错误、usage、diagnostics 与 resume 提示的 task notification
- **AND** 同一终态不会再经通用后台通知重复投递

### Requirement: Workflow resume 只复用同会话最长相同且已完成的 Agent 调用前缀

#### Scenario: 相同 script 与 args 完全命中
- **GIVEN** 同一 parent session 中一条 Workflow 已完成
- **WHEN** 消费者以相同 script、args 和行为选项从其 run id 恢复
- **THEN** 已完成 Agent 结果按原开始序号复用，并按原完成序号释放给并发脚本，Workflow 得到相同脚本结果

#### Scenario: 中途调用发生变化
- **GIVEN** 恢复脚本的前若干 Agent 调用不变，后续某个 prompt 或行为选项改变
- **WHEN** 从原 run id 恢复
- **THEN** 变化前的最长已完成前缀复用
- **AND** 第一个变化、不完整或缺失调用及其后所有调用实时重跑

#### Scenario: label 或 phase 改变不使行为 cache 失效
- **WHEN** 恢复脚本只修改 Agent 的显示 label 或 phase group
- **THEN** 对应已完成结果仍可作为相同调用前缀复用

#### Scenario: 跨会话不复用
- **WHEN** 消费者在另一 parent session 以旧 run id 请求恢复
- **THEN** 恢复被拒绝或从头运行，不把跨会话结果报告为 prefix cache hit

### Requirement: 消费者可保存、发现并按名称运行 Python Workflow

#### Scenario: 保存项目或个人 Workflow
- **WHEN** 消费者把某次运行的 script 保存为 project 或 personal scope
- **THEN** 返回稳定名称和 Python 文件位置，之后可按名与结构化 args 运行

#### Scenario: 同名发现优先级
- **GIVEN** 从当前目录到项目根的多个 project scope 与 personal scope 都有 Workflow
- **WHEN** 消费者按名称解析
- **THEN** 所有不同名称都可发现，同名由最近适用的 project 定义优先；没有 project 定义才使用 personal 定义

#### Scenario: built-in 与 namespaced Workflow
- **WHEN** 消费者查询命名 Workflow
- **THEN** 可同时发现 built-in `/deep-research` 与消费者装配的 namespaced definitions
- **AND** 它们启动后使用相同审批、运行、控制与诊断语义

#### Scenario: project save 拒绝任一级 symlink
- **WHEN** project config dir、其 workflows dir 或目标 Python 文件任一级是 symlink
- **THEN** project save 拒绝写入并返回明确原因

#### Scenario: personal save 只拒绝 symlink target
- **WHEN** personal config/workflows 目录是 symlink 而目标 Python 文件不是 symlink
- **THEN** personal save 可以写入
- **AND** 只有目标文件本身是 symlink 时才拒绝保存

### Requirement: Workflow 向消费者暴露共享 token budget、规模提示和实际模型用量

#### Scenario: 本轮共享 token target
- **GIVEN** 消费者为可信人工 turn 提供一个 output-token target
- **WHEN** 父运行及其 Workflow 子 Agent 产生 output tokens
- **THEN** `budget.spent()` 汇总同一 turn 的父与子用量，`remaining()` 反映共同余额
- **AND** 到达 target 后后续 `agent()` 在派发前被拒绝

#### Scenario: 没有 token target
- **WHEN** 本轮未提供 target
- **THEN** `budget.total` 为 `None`，`remaining()` 为无穷，不凭空增加 token 上限

#### Scenario: 规模 guideline 与大型运行提示
- **WHEN** 消费者选择 small、medium、large 或 unrestricted
- **THEN** Workflow tool description 和运行快照暴露同一 guideline
- **AND** 达到大型运行条件时产生 advisory warning，但已获准运行不会被 warning 自动暂停

#### Scenario: 用量按运行、阶段和 Agent 汇总
- **WHEN** 消费者查看运行快照
- **THEN** 可取得总 usage、各阶段/Agent usage 与耗时，并据此决定是否停止
