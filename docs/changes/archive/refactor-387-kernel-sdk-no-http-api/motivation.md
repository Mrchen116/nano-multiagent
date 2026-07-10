# refactor-387: 移除内核内置 HTTP API，内核改为纯 SDK 形态

## Relations

- Depends on:
- Blocks:
- Related: refactor-382（LLM models 收到 Gateway config）
- Closes: #39（coding_cli/kernel_app.py 直接 import agent 违反 HTTP-only 边界——kernel_app.py 本 unit 删除，边界规则改写）、#40（agent.core.llm.factory 直接 import agent.platform 的具体 client，违反 core 不依赖 platform——本 unit 一并修，provider 装配移出 core）
- Refs: #52 #64 #47 #8 #1（均属内核 HTTP / SSE 路径上的缺陷：Gateway→kernel HTTP 错误透传、stream_session 漏传 workspace_root 404、REPL+ASGI 测试 hang、SSE 订阅在 user run 结束即关闭漏 background 通知、text_delta 增量语义不明——HTTP 路径移除后这些路径随之消失或重做，但本 unit 非专门为修它们）

## 原始诉求

> （架构审视结论，用户认可后立项）当前 agent 内核对外只暴露 HTTP API，coding_cli 和 personal_assistant 都是「import 内核内部装配 FastAPI app → spawn uvicorn 子进程 → 走 loopback HTTP 调自己」，是分布式单体——两头成本都付、好处没拿全。

用户原话：

> 我觉得内核API就完全没必要保留，未来要做云化的agent，也应该是基于sdk包一层，根据实际做成api产品。

> coding_cli 现有的 --mode remote没人用

## 澄清记录

- Q1: 内核 HTTP API 删掉后，coding_cli 的命令行表面变成什么样？（`--mode {managed,remote}` / `--base-url` / `health`·`create-session`·`send-message` 等对 HTTP 端点喊话的子命令是否一并清掉）
  A(原话): 同意
  Agent 解读: `--mode`、`--base-url` 整个消失，coding_cli 进程内直跑，直接进 REPL；`health`/`create-session`/`send-message` 这类只为「对 HTTP server 喊话」而存在的子命令一并删除；`llm-config` 改为直接读/改进程内配置后保留。"模式"概念本身消失。

- Q2: personal_assistant gateway 把内核从「独立 uvicorn 子进程」收进 gateway 进程内、运维可观察面随之改变（不再有独立 kernel 进程 / kernel.log / 健康轮询，gateway 生命周期 == 内核），能接受？
  A(原话): 好
  Agent 解读: 接受进程内。这是删 API 的强制结果（无 API 则无法再用 HTTP 跟子进程说话）。换来 main.py 里 spawn / 健康轮询 / killpg / 单例锁纠缠大幅消失。原进程边界并未买到真正故障隔离（内核挂则 gateway 也无法工作），故收进进程内无隔离损失。

- Q3: 未来云化的 agent API 产品是否划为本 unit 的非目标？
  A(原话): 非目标，我讲的意思是想说，要区分好内核和产品，就算是云化产品，内核还是内核，产品是API还是直接用的软件，和内核无关
  Agent 解读: 云 API 产品明确非目标，将来另立 unit。本 unit 确立的核心原则——**内核与产品形态正交**：产品呈现为 API 还是直接使用的软件，纯属产品层决策，内核一概不关心、不内置任何形态偏好（包括不内置通用 HTTP API）。

- Q4: 依赖内核 HTTP API 的开发/联调工具链（e2e 脚本里「起 Kernel API」、文档中的 curl/非交互命令、直接打 HTTP 端点的 contract test）本期是否一并处理？
  A(原话): 对
  Agent 解读: 一并纳入本期。e2e 脚本去掉「起 Kernel API」段；HTTP 端点 contract test 平移为针对 `agent.sdk` 表面的契约测试（语义不变，是平移不是重写）；AGENTS.md / SPEC.md 等基于 HTTP 的联调示例与已失效的 §5「禁止 import」硬规则一并改写。属删 API 的必然清理，非额外 scope。

## 现状痛点

可证据化，均按当前 `src/` 实测：

1. **分布式单体调用链**：产品既深度 import 内核内部装配 app，又把它当独立服务跑、再走 loopback HTTP 调回去——两头成本都付。
   - `coding_cli/kernel_app.py:38-41`、`personal_assistant/kernel_app.py:25-28`：`from agent.platform.http_api.app import create_app` + import ProductProfile，进程内装配 FastAPI app。
   - `coding_cli/managed_server.py`：spawn `uvicorn coding_cli.kernel_app:app` 子进程 + 端口占用检测 + 健康轮询 + terminate/kill。
   - `personal_assistant/main.py:1304`：spawn kernel uvicorn 子进程；运行期经 `client/kernel_api_client.py` 走 HTTP。

2. **文档与实现背离且已被制度化**：SPEC.md §5 把「`coding_cli`/`personal_assistant` 禁止直接 import agent、四包零 import」写成「唯一架构权威」的硬规则，但实现全线违反；`tests/contract/test_cli_http_only_contract.py:64` 把验收该规则的测试标成 `@pytest.mark.xfail(strict=True)`，理由直书「kernel_app.py intentionally imports agent.platform …, tracked in #39」——违例被固化为预期状态。SPEC v1.2 对齐 M84，当前已 M170+。

3. **假 SDK + client 三重复**：`agent/platform/sdk/client.py` 名为 SDK，实为 HTTP client（`ServerClient`），与 `coding_cli/client.py`、`personal_assistant/client/kernel_api_client.py` 近乎逐行重复三份。重复正是被「禁止跨包 import」逼出来的，而该规则在装配路径上早已被破，故重复无任何收益。真正该被 SDK 封装的 `core/agent/runtime.py:AgentRuntime`（已具备进程内 async 表面：`run`/`create_session`/`continue_turn`/`compact`/`fork_session`）无任何消费方直调，全被逼上 HTTP。

4. **运维复杂度外溢**：`personal_assistant/main.py` 2501 行，混 argv 解析 / 进程 supervisor / pid 单例锁 / killpg / runtime 装配 / 健康轮询；AGENTS.md 中「A/B 两种启停范式不要混用」「撞单例锁 4-5 次」「env 名卡 30 分钟」等运维告警均源于此双进程生死管理。

5. **core→platform 反向依赖（#40）**：`agent/core/llm/factory.py:16-17` 在 core 层直接 import platform 的具体 client（`OpenAICompatClient` / `AnthropicClient`）并维护 provider→具体类的静态注册表 `_PROVIDER_CLIENTS`，违反「core 不依赖 platform/products」的分层硬规则。`tests/contract/test_core_no_platform_imports.py` 同样以 `@pytest.mark.xfail(strict=True)` 把该违例固化为预期状态、挂在 #40——与 #39 同一套路。本属于「内核分层不干净」的同一主题，与本 unit 的 SDK 装配接缝天然同向。

## 目标状态

**指导原则：内核与产品形态正交。** 内核只做「单 agent 可运行 + 可扩展 + 可持久化 + 可观测」的纯库；产品以何种形态呈现（终端软件 / 常驻 gateway / 未来的云 API）是产品层决策，内核不内置任何形态偏好，尤其不内置通用 HTTP API。

终态结构：

```
agent/
├── core/        AgentRuntime（已是进程内 async 核，不变）
├── platform/    providers / persistence / tools / hooks / safety（去掉 http_api、sdk/client）
└── sdk/         ← 内核唯一对外表面：薄封装 AgentRuntime + ProductProfile
                   暴露 run / 流式(async iterator) / 权限(on_permission_request callback) / 取消(RunHandle.cancel)
     ✗ 删除 platform/http_api/   ✗ 删除三份 ServerClient/KernelApiClient
     ✗ 删除 coding_cli/kernel_app.py、personal_assistant/kernel_app.py、coding_cli/managed_server.py

coding_cli/            import agent.sdk 进程内直跑；无 --mode / --base-url；无 HTTP 子命令
personal_assistant/    import agent.sdk，gateway 进程内持有 runtime；main.py 砍掉子进程管理
IM/                    不受影响（本就不直接调内核）
未来云 API 产品         非本期；将来另起独立可部署包 import agent.sdk 包出其所需 API
```

边界规则从「产品禁止 import agent」（错且已破）改写为可执行的：**产品只能 import `agent.sdk`（已发布表面），禁止 import `agent.core` / `agent.platform` 内部**。

同时修复 core→platform 反向依赖（#40）：`core` 不再 import `platform` 的任何具体实现。LLM provider 的具体 client 装配移出 core——core 只持有 `LLMClient` 端口（接口）与 provider 注册接缝，具体 provider 实现由 platform / SDK bootstrap 在启动时注册（依赖反转；具体机制留 design）。`test_core_no_platform_imports.py` 随之去掉 xfail、转为常规守卫。

## 用户侧验收标准（不变性）

镜头为「回归基线」：内核换形态后，两个现有产品的用户/运维可观察行为必须与变更前一致。下列既有行为是变更前的快照，reviewer 照此逐 Scenario 走回归。（被有意移除的 CLI 模式与 HTTP 子命令见「影响范围」，不在不变性清单内。）

### Requirement: coding_cli 多步工具调用的 agent 任务正常完成

回归基线的核心：agent 是工具调用循环，必须验真实 agentic 任务（读/写/编辑/执行），而非寒暄式纯对话。流式、权限、取消、后台任务事件这些接缝只有在多步工具 run 里才真正被压到。

#### Scenario: 多步工具调用完成一个真实编码任务
- **GIVEN** 一个有真实代码的工作区
- **WHEN** 用户在 REPL 要求 agent 完成一个需要多步工具的任务（如「读 X 文件、改一处、跑测试」）
- **THEN** agent 依次调用 read / edit / bash 等工具，每步工具调用与结果在 REPL 流式可见，任务最终完成，全过程与变更前一致

#### Scenario: 工具权限确认（真实工具使用语境）
- **GIVEN** agent 在任务执行中触发需确认的工具（如 bash / write）
- **WHEN** REPL 弹出权限请求且用户做出 allow / deny 选择
- **THEN** 工具按用户决定执行或拒绝、agent 据此继续后续步骤，交互与变更前一致

#### Scenario: 任务执行中途打断
- **GIVEN** agent 正在一个多步工具任务中（例如正在跑一条 bash）
- **WHEN** 用户触发中断
- **THEN** 当前 run 及在途工具停止、可继续输入下一条，行为与变更前一致

#### Scenario: 后台任务完成通知
- **GIVEN** agent 在一轮中发起一个后台 bash 任务，该轮 user run 已结束
- **WHEN** 后台任务随后完成
- **THEN** 完成通知仍能送达并在 REPL 呈现（不因 user run 结束而丢失），与变更前一致

#### Scenario: 子 agent / task 工具
- **WHEN** agent 在任务中调用 task / 子 agent 工具派发子任务
- **THEN** 子 agent 执行并回灌结果，主 agent 据此继续，行为与变更前一致

#### Scenario: skill 调用
- **WHEN** 任务触发某个 skill（自动或显式）
- **THEN** skill 正常加载并参与本轮，行为与变更前一致

#### Scenario: REPL 内置命令
- **WHEN** 用户执行 `/compact`、`/tools`、`/history`、`/new`、`/use`
- **THEN** 各命令结果与变更前一致

#### Scenario: 无模式直接进入 REPL
- **WHEN** 用户运行 `python -m coding_cli.main`（不带 `--mode` / `--base-url`）
- **THEN** 直接进入可交互 REPL，无需先起任何本地服务

### Requirement: personal_assistant 经 IM / channel 的工具型 agent 任务保持一致

同样不能只验寒暄——必须验 agent 经 IM 完成含工具调用的真实任务。

#### Scenario: 经 IM 完成一个含工具调用的任务
- **GIVEN** gateway 已连上 IM
- **WHEN** 用户在 IM 中要求某 agent 完成一个需要工具的任务（读/写文件、跑命令等）
- **THEN** agent 调用工具、完成任务并经 IM 回发结果，过程与时序与变更前一致

#### Scenario: 后台任务完成回发
- **GIVEN** agent 在响应某条 IM 消息时发起后台任务、该次 run 已结束
- **WHEN** 后台任务随后完成
- **THEN** 完成结果仍经 IM 回发给用户（不因 run 结束丢失），与变更前一致

#### Scenario: heartbeat / cron 触发的工具型任务
- **WHEN** 到达 heartbeat / cron 触发点且该任务含工具调用
- **THEN** agent 按既有行为执行工具并回发，与变更前一致

#### Scenario: 多 agent 互发消息
- **WHEN** 一个 agent 通过 `send_message` 向另一个 agent 发消息
- **THEN** 目标 agent 收到并处理（含可能的工具调用），行为与变更前一致

### Requirement: gateway 运维命令保持可用

#### Scenario: stop / restart
- **WHEN** 运维执行 gateway 的 `stop` / `restart`
- **THEN** gateway 干净停止 / 重启并恢复服务，且不残留任何 kernel 子进程（内核已进程内，随 gateway 一起起停）

### Requirement: LLM provider 选择与调用保持一致（#40 修复的不变性）

#### Scenario: anthropic provider 正常应答
- **GIVEN** 配置选用 anthropic 类 provider 的某模型
- **WHEN** 用户向 agent 发消息
- **THEN** agent 经该 provider 正常应答，行为与变更前一致

#### Scenario: openai_compat provider 正常应答
- **GIVEN** 配置选用 openai_compat 类 provider 的某模型
- **WHEN** 用户向 agent 发消息
- **THEN** agent 经该 provider 正常应答，行为与变更前一致

#### Scenario: 不支持的 provider 报错不变
- **WHEN** 配置了一个未注册的 provider
- **THEN** 启动 / 调用时给出与变更前一致的「unsupported provider」类错误，不静默

## 影响范围

- **删除**：`agent/platform/http_api/`（app / routes / sse / auth / deps）、`agent/platform/sdk/client.py`、`coding_cli/client.py`、`personal_assistant/client/kernel_api_client.py`、`coding_cli/kernel_app.py`、`personal_assistant/kernel_app.py`、`coding_cli/managed_server.py`。
- **新增**：`agent/sdk` 真实表面（封装 `AgentRuntime` + `ProductProfile`，提供 run / 流式迭代器 / 权限 callback / 取消句柄）。
- **改造**：`coding_cli`（去 mode/base-url/HTTP 子命令，改 import `agent.sdk` 进程内跑）；`personal_assistant`（gateway 进程内持有 runtime，`main.py` 移除 kernel 子进程 spawn / 健康轮询 / 相关 killpg / 单例锁逻辑）。
- **有意移除的用户可观察面**（非回归项，是刻意行为变更）：`--mode {managed,remote}`、`--base-url`、`health`/`create-session`/`send-message` 等 HTTP 子命令。`--mode remote` 经确认无人使用。
- **内核可注入接缝改出口**（非删除，换消费方式）：事件流 `set_session_event_publisher_factory` → 由 SDK 安装进程内 sink（async 队列/迭代器）替代 `EventStreamHub`/SSE；权限 `PermissionBroker` → SDK 的 `on_permission_request` callback；取消 `RunController` → `RunHandle.cancel`。
- **core→platform 反向依赖修复（#40）**：`agent/core/llm/factory.py` 不再 import `agent.platform.llm.providers.*` 的具体 client；provider 具体实现的装配移出 core（依赖反转，机制留 design）。`tests/contract/test_core_no_platform_imports.py` 去掉 `xfail`、转常规守卫。
- **工具链 / 测试 / 文档**：`scripts/e2e-up.sh` 去掉「起 Kernel API」段；直接打 HTTP 端点的 contract test（`test_sse_event_contract` / `test_runs_async_contract` / `test_run_cancel_contract` / `test_session_interrupt_contract` / `test_health_contract` 等）平移为 `agent.sdk` 表面契约测试；`test_cli_http_only_contract.py` 重写为「产品只能 import `agent.sdk`」边界检查（去掉 xfail）；SPEC.md §5、AGENTS.md 运行时章节、相关联调文档改写。
- **不受影响**：`IM`（本就不直接调内核）；内核 `core` 逻辑（`AgentRuntime` 表面已具备，主要是新增 SDK 封装层与替换事件出口，不重写核心）。

## 迁移与回滚策略

- **行为不变保证**：现有针对内核能力的 contract / 单测平移到 SDK 表面（语义不变），覆盖流式 / 权限 / 取消 / 打断 / compact 等；再以两个产品的真实用户旅程（coding_cli REPL、PA 经 IM 对话）做端到端回归，对照「用户侧验收标准」逐 Scenario 验。
- **迁移顺序（原则层，细化留 design）**：先立 `agent.sdk` 表面并以 SDK 测试钉死契约 → 改 coding_cli 上 SDK → 改 PA 上 SDK → 删 HTTP API / 三份 client / kernel_app / managed_server → 迁移 e2e 脚本、contract test 与文档。增量推进，每步独立可验。
- **回滚**：HTTP API 删除是终态目标；实施过程分步 commit，删除动作集中在消费方完成迁移之后，任一步出问题可单独 revert 该步而不回退已迁好的 SDK 与产品改造。
