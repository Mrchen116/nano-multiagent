# feat-788: 本机 Global worker 支持 Antigravity CLI

## Relations

- Related: feat-778

## 原始需求

> raft支持agy吗。我们现在subagent只支持codex和cc。

> 我现在就是在T3 code中通过acp连的agy跟你沟通，你可以把T3 code的代码也拉下来我的开源仓库存放的目录下，研究下。他是可以看到当前上下文token的

> 好，开始弄个unit做

## 澄清记录

- 已核实参考基线（Agent 解读）：
  - Raft（`~/Repos/opensource-hub/raft-source` @ `5214e34e34e726ed715f455e78c96fa521791ef2de3`）通过 `@botiverse/oar` 的常驻会话支持 `agy`，但启动时跳过权限检查，且未接入每轮 token 统计。
  - T3 Code（`~/Repos/opensource-hub/t3code` @ `16acd71825142d1b8e5abd0aaa5b84f6982e6b13`）直接连接本机 `agy`（当前本机已安装 `agy 1.5.16`），保留 Auto 权限审核与宿主拒绝、支持原会话无重放续做及运行中追加说明，同时展示当前上下文窗口占用（已用/上限）和每轮输入、缓存命中与输出 token。
  - Nano 现行本机一级 worker 契约由 `feat-778` 建立（见 [global-agent.md](../../specs/gateway/global-agent.md)、[tool-approval.md](../../specs/gateway/tool-approval.md)、[agent-work.md](../../specs/im/agent-work.md)）：本机外部 CLI worker 使用系统运行用户的登录态与默认模型、Auto 待裁决或被拒动作交回父 Global、不消费或写入 Nano 长期记忆，并在 IM Work 中共用派工关系与持久化工作记录。
- Q1: 本次接入 Antigravity（`agy`）的一级 worker 框架选择粒度怎么定？
  A(原话): (Recommended) 沿用 feat-778 按机器统一配置（在 gateway.worker_runtime 新增 antigravity，与 dsh / codex / claude 并列）——改动边界最清晰，改一行配置即可让本机普通 Global 和 PA 切换使用 agy

## 用户场景

用户在运行 Gateway 的机器上安装并登录 Google Antigravity CLI（`agy`），将该机器的 `gateway.worker_runtime` 配置为 `antigravity`。重启 Gateway 后，用户在 IM 向普通 Global Agent 或 PA 交办需要独立执行的事项：Global 使用本机已登录的 `agy` 账号、工作区和默认模型派出后台 worker，并在同一事项收到用户补充时继续交给原 worker 会话处理，收到停止要求时中止该 worker 并反馈真实结果。

执行过程中，若 `agy` 在 Auto 模式下遇到需要额外授权、澄清提问或越权的动作，不会卡在无人响应的交互等待，也不会放行未获准动作，而是把具体操作、目标与原因交回原 Global，由 Global 在现有授权内处理或在原聊天询问用户。用户打开 Web IM 的 Work 页面时，除了在派工关系和活动弹窗中辨认 `Antigravity` 框架、已结束轮次、累计 token 以及查看任务输入、消息和工具明细外，还能在展开该 worker 轮次统计时看到当前上下文占用（已用 token / 上下文窗口上限及百分比）、本轮输出与缓存命中统计。

## 验收标准

### Requirement: 在本机使用 Antigravity worker 完成委派事项

#### Scenario: 配置 Antigravity 后的派工、原会话续做与停止
- **GIVEN** 本机配置选择 `antigravity` 作为一级 worker 框架，且运行 Gateway 的系统用户已安装并登录 `agy`
- **WHEN** 用户在 IM 向普通 Global 或 PA 交办事项，随后追加更正，或要求停止该事项
- **THEN** 新事项由 Antigravity worker 承接，追加更正回到同一原会话继续处理，完成成果由原 Global 交付回来源聊天；用户要求停止时，Global 停止原 worker 并反馈实际停止结果
- **AND** 配置切换前已创建的既有事项继续按其创建时的框架处理，不因机器配置变更丢失或混用会话

#### Scenario: 使用本机 Antigravity 的登录态与默认模型
- **GIVEN** 运行 Gateway 的系统用户已在宿主机登录 `agy`（包括节点由 SSH 会话启动或受管后台运行的情形）
- **WHEN** Global 使用 `antigravity` 派出新的 worker
- **THEN** worker 沿用该宿主机用户直接运行 `agy` 时的登录账号、工作区和默认模型，不被 Global 自身的模型配置覆盖
- **AND** 若本机缺少 `agy` 可执行文件或登录失效，原 Global 收到明确失败原因并可向用户如实说明

#### Scenario: Antigravity worker 遇到待授权动作或交互提问
- **WHEN** Antigravity worker 在 Auto 模式下请求执行需要人工确认的动作、向用户发起交互式提问，或触发被拒绝的操作
- **THEN** 该未获准动作不被放行、不弹出子级权限卡也不无限挂起，具体动作、对象与原因交回原 Global，由 Global 按现有权限处理或在原聊天向用户澄清；明确拒绝保持有效

#### Scenario: Antigravity worker 与 Nano 长期记忆解耦
- **WHEN** Global 将事项委派给 Antigravity worker，之后执行长期记忆整理
- **THEN** Nano 不向该 worker 注入长期记忆正文、路径或读写指引，Dreaming 也不从该 worker 的内部执行记录取材

### Requirement: 在 Work 中查看 Antigravity 派工关系、过程明细与上下文 Token

#### Scenario: 辨认 Antigravity 委派关系与执行过程
- **WHEN** Global 派出 Antigravity worker 执行事项并产生消息与工具调用
- **THEN** 用户在 Web IM 活动弹窗、派工关系与工作记录中可辨认 `Antigravity` 框架名称、任务标题及真实运行/完成/中断/失败状态，并能打开同一份持久化工作记录查看任务输入、消息、工具参数与结果

#### Scenario: 查看 Antigravity 轮次的当前上下文占用与 Token 统计
- **WHEN** Antigravity worker 完成轮次并报告上下文窗口与单轮 token 数据，用户在 Work 中查看派工关系及该 worker 的轮次统计
- **THEN** 派工关系按已结束轮次累计该 worker 的总 token，且展开该轮统计时可见当前上下文已用 token、上下文窗口上限与占用百分比，以及本轮输出、缓存命中与本轮总 token；未报告字段仍按既有规则如实显示未报告

## 范围与非目标

- 在范围：
  - 在本机 `gateway.worker_runtime` 中支持 `antigravity`（与 `dsh`、`codex`、`claude` 并列），覆盖普通 Global 与 PA 的一级派工、同会话续做、停止、冷启动中断恢复回报及运行临时资源回收。
  - Antigravity worker 的 Auto 权限拦截、交互提问拦截与向父 Global 回报，以及父子内部通信工具接入。
  - IM Work 对 `Antigravity` 框架的标识展示、过程明细持久化，以及轮次当前上下文窗口占用与单轮 token 统计展示。
- 非目标：
  - 按次由主 Agent 动态选择不同 worker 框架，或在 Web IM 按数字人单独配置 worker 框架。
  - 在 Nano 内置托管 `agy` 二进制下载更新或网页端 Google OAuth 登录界面（沿用本机 CLI 安装与登录）。
  - Antigravity 内部二次派生子任务的独立轨迹树展开或原生客户端查看器嵌入。
