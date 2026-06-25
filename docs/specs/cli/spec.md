# cli (coding_cli) Specification

> 对齐: bugfix-426-midrun-message-steering
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本契约层只收 **终端用户在 CLI 上可观察的对外
> 行为**;CLI 内部如何编排内核、渲染、消费事件不在此层(那在代码 + 归档 design)。每条 Scenario 的主语 =
> 在终端敲命令/读输出的人,或脚本/CI(消费 `--text` NDJSON、单命令 JSON),或 `tests/contract/` 契约测试。

## Purpose

`coding_cli` 是面向开发者的本地编码助手终端应用:在终端内与 Agent 交互式对话,辅助读代码、写代码、执行
命令、调试问题。

它经 `import agent.sdk` **进程内**装配并持有内核(`build_kernel()` → `Kernel`),没有独立 HTTP server、
不起子进程(refactor-387)。它对外呈现两种面:面向人的交互式异步 REPL,以及面向脚本/CI 的非交互输出
(`--text` 流式 NDJSON、`llm-config` 单命令 JSON)。

它面向低心智负担的日常使用:默认无参启动即可用,内部连接/端口参数不得成为日常必填项。

**显式不负责**:不实现 Agent Loop、不直接调 LLM、不管会话持久化(均由内核承担);不做 IM 接入 / channel
路由 / heartbeat(那是 Gateway)。

## Requirements

### Requirement: 无参启动即进入进程内异步 REPL,无 HTTP / 无子进程

终端用户无需任何参数、无需先拉起任何服务,直接运行 CLI 即进入交互式异步 REPL;内核在同进程内经
`agent.sdk` 装配,不监听端口、不 spawn 子进程。

#### Scenario: 直接运行进入交互式 REPL
- **GIVEN** 一个开发者在终端
- **WHEN** 他不带任何子命令运行 CLI(`python -m coding_cli.main`)
- **THEN** 进入交互式 REPL 等待输入;全程在本进程内运行,不连任何 loopback HTTP、不起 agent 子进程

### Requirement: REPL 会话懒创建并绑定当前工作目录,可经 --resume 复用既有会话

REPL 启动时不预先创建会话;用户首次发普通消息时才创建会话,工作区根绑定为 CLI 启动时的当前工作目录。
该会话持续复用,直到用户 `/new` 新建或 `/use <id>` 切换。带 `--resume <session_id>` 启动则直接复用该
既有会话而不新建。

#### Scenario: 首次发消息时懒创建会话并绑定 cwd
- **GIVEN** 刚进入的 REPL(尚无活跃会话)
- **WHEN** 用户输入第一条普通消息
- **THEN** CLI 创建一个会话并提示其 id,工作区根 = 启动时 cwd,该会话内后续工具执行都在此根下进行

#### Scenario: --resume 复用既有会话
- **WHEN** 用户以 `--resume <session_id>` 启动 REPL 并发消息
- **THEN** CLI 复用该既有会话(不新建),后续对话延续其历史

### Requirement: REPL 提供固定一组斜杠命令管理会话与上下文

REPL 暴露稳定的斜杠命令集合管理会话生命周期、查看工具、压缩上下文、回看历史与退出;斜杠命令不计入对话
消息历史。

#### Scenario: 斜杠命令集合稳定
- **WHEN** 用户在 REPL 中查看可用命令
- **THEN** 至少包含 `/help`、`/new`、`/use <id>`、`/session`、`/tools`、`/compact`、`/history [n]`、`/exit`

#### Scenario: /new 与 /use 切换活跃会话
- **WHEN** 用户执行 `/new`
- **THEN** 创建并切到新会话;执行 `/use <session_id>` 则切到指定既有会话,后续消息发往切换后的会话

#### Scenario: /tools 与 /compact 作用于当前会话
- **WHEN** 用户执行 `/tools`
- **THEN** 列出当前会话可用工具;执行 `/compact` 则手动触发当前会话的上下文压缩
- **AND** 无活跃会话时这类命令给出可执行提示(如"run /new or /use <session_id>")而非报栈

#### Scenario: /exit 退出 REPL
- **WHEN** 用户执行 `/exit`
- **THEN** REPL 干净退出(退出码 0)

### Requirement: REPL 实时呈现工具调用与文本增量,每轮后给出用量与上下文预算

发送普通消息后,CLI 实时显示该轮的工具调用进度与助手文本生成增量;该轮结束后渲染最终响应,并显示本轮
token 用量与上下文预算(已用/上限/占比)。预算接近上限时给出渐进的 `/compact` 提示。

#### Scenario: 一轮对话呈现工具与文本,收尾给出用量
- **GIVEN** 一个活跃会话
- **WHEN** 用户发一条触发工具调用的消息
- **THEN** 终端实时显示工具调用与文本增量,该轮完成后显示最终响应 + 本轮用量摘要

#### Scenario: 上下文预算分级提示
- **WHEN** 本轮后上下文占比跨过 70% / 85% / 95% 阈值
- **THEN** 分别提示"monitor context and consider /compact"/"consider /compact soon"/"run /compact now"

#### Scenario: 预算查询失败不阻塞对话
- **GIVEN** 上下文预算指标暂不可得
- **WHEN** 一轮对话结束
- **THEN** 对话主流程照常完成(fail-open),不因预算显示失败而中断或报错退出

### Requirement: REPL 在 run 执行中可继续输入，输入 steer 进当前 run

run 执行期间 REPL 输入不被阻塞；用户在 run 运行中提交的输入注入当前 run 的下一轮，而非排队等其结束。

#### Scenario: run 执行中输入被注入当前 run 下一轮
- **GIVEN** REPL 的某个 run 正在执行（流式输出进行中）
- **WHEN** 用户在 run 未结束时输入并提交一条消息
- **THEN** 输入在当前 run 的下一次模型调用前被带入上下文，不阻塞、不等当前 run 整体结束
- **AND** 该注入消息触发的助手回复在终端呈现，后续对话可引用其内容（注入轮进入会话历史）

#### Scenario: 空闲时输入仍开新 run
- **GIVEN** REPL 当前无执行中的 run
- **WHEN** 用户输入并提交
- **THEN** 照常作为新 run 处理

### Requirement: 错误对终端用户分层呈现,携带可执行修复建议

CLI 把异常归类到 `input` / `network` / `runtime` 三层之一,并随错误给出一条可执行的修复建议。REPL 内
的轮次错误就地内联呈现(不打断 REPL 循环);非交互单命令的失败以单行 JSON 输出。

#### Scenario: REPL 内轮次错误内联呈现且不中断循环
- **GIVEN** 一个会话在发消息时遇到错误(如连接被拒)
- **WHEN** 该轮失败
- **THEN** 错误就地内联呈现,标明所属层(如 `layer=network`)与建议;REPL 不崩溃,继续等待下一次输入

#### Scenario: 错误层级按性质分类
- **WHEN** 错误源于参数/校验(如 `ValueError`)、网络(连接拒绝/超时/未授权)、或运行执行(run failed /
  stop_reason 异常)
- **THEN** 其 `layer` 分别落为 `input` / `network` / `runtime`

### Requirement: 非交互单命令输出单个 JSON 对象供脚本消费

`llm-config get` / `llm-config set` 等单命令把结果作为**恰好一个** JSON 对象打印到 stdout,供脚本无噪
解析;命令出错时 stdout 输出单行 `{error, suggestion, layer}` JSON,退出码非零。

#### Scenario: llm-config get 输出单个 JSON
- **WHEN** 脚本运行 `llm-config get`
- **THEN** stdout 是恰好一个 JSON 对象,含 `provider` / `model` / `base_url` 等字段(无 REPL 噪声、无多行)

#### Scenario: 单命令参数错误输出单行错误 JSON
- **WHEN** 脚本运行 `llm-config set`(未给任何字段)
- **THEN** 退出码为 1,stdout 是单行 JSON,含 `{error, suggestion, layer}` 三键,`layer == "input"`

### Requirement: --text 非交互模式单次提交并流式 NDJSON,退出码反映运行结局

带 `--text <内容>` 运行时,CLI 创建(或 `--resume` 复用)会话、提交一次该文本,把过程事件逐行以 NDJSON
流到 stdout,运行到终态后退出;退出码 0 表示 `completed`,非 0 表示 `failed` / `cancelled`。

#### Scenario: --text 流式 NDJSON 到 stdout 并按结局给退出码
- **WHEN** 脚本运行 `--text "..."`
- **THEN** stdout 逐行输出 NDJSON 事件(首行含提交回执的 `run_id`),运行 `completed` 时退出码 0,
  否则非 0

#### Scenario: --text 配合 --resume 复用会话
- **WHEN** 脚本运行 `--text "..." --resume <session_id>`
- **THEN** 提交发往该既有会话(不新建)

### Requirement: 非 TTY 环境可用,退化为基础行输入而不崩溃

CLI 在非 TTY 环境(如管道喂输入、CI)必须可用:输入退化为基础 `input()` 行读取,输出不发终端控制码
(ANSI 转义),不因缺少交互终端而崩溃。

#### Scenario: 管道输入下退化运行
- **GIVEN** stdin 非 TTY(管道喂入若干行 + `/exit`)
- **WHEN** 运行 CLI
- **THEN** 逐行读取并处理,正常退出;输出不含面向终端的 ANSI 转义控制序列

### Requirement: 产品边界——只经 agent.sdk 触达内核,不依赖内核内部

`coding_cli` 只允许 `import agent.sdk`,不得 import `agent.core` / `agent.platform` / `agent.products`
内部,也不得 import 兄弟产品包(`personal_assistant` / `IM`)。这是由契约测试把守的硬不变量。

#### Scenario: 越界 import 内核内部或兄弟包被拦
- **WHEN** `coding_cli` 任一文件 import `agent.core` / `agent.platform` / `agent.products` 或
  `personal_assistant` / `IM`
- **THEN** 契约测试(`tests/contract/test_cli_http_only_contract.py`)失败,挡住越界

### Requirement: 使用 local_coding 产品 profile,扩展走 nanocode 配置目录

CLI 以 `local_coding` 产品 profile 装配内核:配置命名空间为 `nanocode`,全局配置目录 `~/.nanocode/`、
工作区配置目录 `<workspace>/.nanocode/`。用户可在这两处的 `tools/` / `hooks/` / `skills/` 下追加扩展,
无需改 CLI 代码即被该 profile 纳入。

> 默认启用哪些内置工具属内核 profile 装配的实现细节(会随产品演进增删),不在此对外契约层固定清单;
> 当前默认工具集见 `src/agent/products/local_coding/toolsets.py`。

#### Scenario: 工作区扩展目录被纳入
- **GIVEN** 工作区下存在 `<workspace>/.nanocode/tools/`(或 hooks / skills)的扩展
- **WHEN** 用户在该工作区启动 CLI 并发消息
- **THEN** 该会话可用工具/扩展包含这些工作区追加项(在内置工具之上),且 `/tools` 能列出
