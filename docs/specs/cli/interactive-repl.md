# cli (coding_cli) - Interactive REPL Specification

> 对齐: refactor-486-agent-native-repository-knowledge-system
> 上级: [cli (coding_cli) Specification](spec.md)

## Purpose

约束开发者直接使用交互式终端时可观察的启动、会话、命令、流式反馈、运行中输入和错误行为。

## Requirements

### Requirement: 无参启动即进入进程内异步 REPL，无 HTTP 或 agent 子进程

终端用户无需任何参数、无需先拉起任何服务，直接运行 CLI 即进入交互式异步 REPL；内核在同进程内经
`agent.sdk` 装配，不监听端口、不启动 agent 子进程。

#### Scenario: 直接运行进入交互式 REPL
- **GIVEN** 一个开发者在终端
- **WHEN** 他不带任何子命令运行 CLI（`python -m coding_cli.main`）
- **THEN** 进入交互式 REPL 等待输入；全程在本进程内运行，不连接 loopback agent HTTP 服务，也不启动
  agent 子进程

### Requirement: REPL 会话懒创建并绑定当前工作目录，可经 --resume 复用既有会话

REPL 启动时不预先创建会话；用户首次发普通消息时才创建会话，工作区根绑定为 CLI 启动时的当前工作目录。
该会话持续复用，直到用户 `/new` 新建或 `/use <id>` 切换。带 `--resume <session_id>` 启动则使用指定会话。

#### Scenario: 首次发消息时懒创建会话并绑定 cwd
- **GIVEN** 刚进入的 REPL，尚无活跃会话
- **WHEN** 用户输入第一条普通消息
- **THEN** CLI 创建一个会话并提示其 id，工作区根等于启动时 cwd，该会话内后续工具执行都在此根下进行

#### Scenario: --resume 复用既有会话
- **WHEN** 用户以 `--resume <session_id>` 启动 REPL 并发消息
- **THEN** CLI 使用该既有会话，后续对话延续其历史

### Requirement: REPL 提供固定一组斜杠命令管理会话与上下文

REPL 暴露稳定的斜杠命令集合管理会话生命周期、查看工具、压缩上下文、回看历史与退出；斜杠命令不计入
对话消息历史。

#### Scenario: 斜杠命令集合稳定
- **WHEN** 用户在 REPL 中查看可用命令
- **THEN** 至少包含 `/help`、`/new`、`/use <id>`、`/session`、`/tools`、`/compact`、
  `/history [n]`、`/exit`

#### Scenario: /new 与 /use 切换活跃会话
- **WHEN** 用户执行 `/new`
- **THEN** 创建并切到新会话；执行 `/use <session_id>` 则切到指定既有会话，后续消息发往切换后的会话

#### Scenario: /tools 与 /compact 作用于当前会话
- **WHEN** 用户执行 `/tools`
- **THEN** 列出当前会话可用工具；执行 `/compact` 则手动触发当前会话的上下文压缩
- **AND** 无活跃会话时给出可执行提示，而非报栈

#### Scenario: /exit 退出 REPL
- **WHEN** 用户执行 `/exit`
- **THEN** REPL 干净退出，退出码为 0

### Requirement: REPL 实时呈现工具调用与文本增量，每轮后给出用量与上下文预算

发送普通消息后，CLI 实时显示该轮的工具调用进度与助手文本增量；该轮结束后渲染最终响应，并显示本轮
token 用量与上下文预算。预算接近上限时给出渐进的 `/compact` 提示。

#### Scenario: 一轮对话呈现工具与文本，收尾给出用量
- **GIVEN** 一个活跃会话
- **WHEN** 用户发一条触发工具调用的消息
- **THEN** 终端实时显示工具调用与文本增量，该轮完成后显示最终响应和本轮用量摘要

#### Scenario: 上下文预算分级提示
- **WHEN** 本轮后上下文占比跨过 70% / 85% / 95% 阈值
- **THEN** 分别提示 monitor、尽快 compact、立即 compact 的渐进建议

#### Scenario: 预算查询失败不阻塞对话
- **GIVEN** 上下文预算指标暂不可得
- **WHEN** 一轮对话结束
- **THEN** 对话主流程照常完成，不因预算显示失败而中断或报错退出

### Requirement: REPL 在 run 执行中可继续输入，输入 steer 进当前 run

run 执行期间 REPL 输入不被阻塞；用户在 run 运行中提交的普通消息注入当前 run 的下一轮，而非排队等其结束。

#### Scenario: run 执行中输入被注入当前 run 下一轮
- **GIVEN** REPL 的某个 run 正在流式输出
- **WHEN** 用户在 run 未结束时输入并提交一条普通消息
- **THEN** 输入在当前 run 的下一次模型调用前被带入上下文，不等待当前 run 整体结束
- **AND** 该输入触发的助手回复在终端呈现，注入轮进入会话历史

#### Scenario: 空闲时输入仍开新 run
- **GIVEN** REPL 当前无执行中的 run
- **WHEN** 用户输入并提交
- **THEN** 照常作为新 run 处理

### Requirement: 错误对终端用户分层呈现，携带可执行修复建议

CLI 把异常归类到 `input` / `network` / `runtime` 三层之一，并随错误给出一条可执行的修复建议。REPL 内
的轮次错误就地内联呈现，不打断 REPL 循环。

#### Scenario: REPL 内轮次错误内联呈现且不中断循环
- **GIVEN** 一个会话在发消息时遇到错误
- **WHEN** 该轮失败
- **THEN** 错误就地内联呈现，标明所属层与建议；REPL 继续等待下一次输入

#### Scenario: 错误层级按性质分类
- **WHEN** 错误源于参数或校验、网络，或运行执行
- **THEN** 其 `layer` 分别落为 `input` / `network` / `runtime`

### Requirement: 非 TTY 环境可用，退化为基础行输入而不崩溃

CLI 在非 TTY 环境中把输入退化为基础行读取，输出不发送终端控制码，不因缺少交互终端而崩溃。

#### Scenario: 管道输入下退化运行
- **GIVEN** stdin 非 TTY，管道喂入若干行和 `/exit`
- **WHEN** 运行 CLI
- **THEN** 逐行读取并处理，正常退出；输出不含面向终端的 ANSI 转义控制序列
