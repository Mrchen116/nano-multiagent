# refactor-387 — Review-A: coding_cli 验收报告

> 对齐: motivation.md 验收标准 `Requirement: coding_cli 多步工具调用的 agent 任务正常完成` + `Requirement: LLM provider 选择与调用保持一致`
>
> Review round: 1 | 日期: 2026-05-29 | Reviewer: review-cli

---

## Verdict

**fail**

---

## Highest Required Action

**fix-implementation**

---

## Issues

### Issue #1 — CLI 完全无法启动（blocking）

- **Severity**: blocking
- **Symptom**: 任何入口启动 `python -m coding_cli.main` 均报 `{"error": "model registry not initialized — call init_model_registry(payload) at process startup", "layer": "runtime"}`，包括 `--text` 模式、交互式 REPL、以及 `llm-config get/set` 子命令。
- **操作步骤**:
  1. `PYTHONPATH=src python -m coding_cli.main --text "say hello"` → 报错退出 1
  2. `PYTHONPATH=src python -m coding_cli.main llm-config get` → 同样报错退出 1
  3. 设置完整 env 变量（`NANO_MULTIAGENT_LLM_PROVIDER=anthropic NANO_MULTIAGENT_LLM_MODEL=kimiCoding:K2.6 NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000`）后重试 → 仍报同样错误
- **预期**: 直接进入可交互 REPL；或 `llm-config` 命令正常响应。
- **实际**: 任何入口均立即失败，用户无法使用 CLI。
- **根因分析方向（供 fix worker 参考，不作归因）**: `_build_llm_config_from_args` 总是先调 `LLMFactoryConfig.from_env()`，而 `from_env()` 中 `os.getenv("NANO_MULTIAGENT_LLM_PROVIDER", get_default_provider())` 会无条件执行 `get_default_provider()`（Python 在调用 `os.getenv()` 前先求值所有参数）；`get_default_provider()` 需要 model registry 已初始化，但 coding_cli 整个启动路径中从未调用 `init_model_registry(payload)`。结果：即使 env 变量全部设置，`from_env()` 仍报错。
- **Recommended Action**: fix-implementation
- **Action Rationale**: `_async_main` 在走任何分支前都先调 `_build_kernel`，后者调 `_build_llm_config_from_args`，后者无条件调 `from_env()`，后者无条件调 `get_default_provider()`——这是纯实现问题，design.md 明确要求「进程内直跑」且「CLI 参数 `--provider`/`--model`/`--llm-base-url` 覆盖默认值」。fix 方向：`from_env()` 在 registry 未初始化时应退化到仅读 env var（无 registry fallback），或在 `_build_llm_config_from_args` 中当 args 提供全部必要值时完全不调 `from_env()`，或 coding_cli 启动时从 `~/.nanocode/config.yaml` 加载 LLM payload 并 `init_model_registry`。

---

## User Journeys Exercised

| # | 旅程 | 覆盖的 Scenario | 结果 |
|---|---|---|---|
| J1 | 无模式直接进入 REPL（`python -m coding_cli.main`） | Scenario: 无模式直接进入 REPL | CLI 立即报 model registry 错误退出，旅程无法推进 |
| J2 | `--text` 非交互模式提交简单任务（`--text "say hello"`） | Scenario: 多步工具调用 + Scenario: anthropic provider 应答 | 同样报 model registry 错误，旅程无法推进 |
| J3 | 设置完整 env 变量后重试 | Scenario: 无模式进入 REPL + LLM provider Scenario | 仍报 model registry 错误，env 变量路径无效 |

由于 CLI 完全无法启动，旅程 J1–J3 均在第一步即阻塞，后续所有 Scenario 均无法走到。

---

## 验收标准覆盖

### Requirement: coding_cli 多步工具调用的 agent 任务正常完成 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 多步工具调用完成一个真实编码任务 | motivation.md §Scenario: 多步工具调用 | 旅程 J1/J2：启动 REPL，提交 read+edit+bash 任务，观察流式输出 | CLI 启动即报 `model registry not initialized`，无法进入 REPL | **fail** | blocking：Issue #1 阻塞所有旅程 |
| 工具权限确认 | motivation.md §Scenario: 工具权限确认 | 旅程 J1：触发 bash/write 工具，观察 REPL 权限弹出 | CLI 未启动，无法触发 | **fail** | 被 Issue #1 阻塞 |
| 任务执行中途打断 | motivation.md §Scenario: 任务执行中途打断 | 旅程 J1：多步任务运行中触发 Ctrl-C，观察停止行为 | CLI 未启动，无法触发 | **fail** | 被 Issue #1 阻塞 |
| 后台任务完成通知 | motivation.md §Scenario: 后台任务完成通知 | 旅程 J2：发起后台 bash 任务，等待通知回显 | CLI 未启动，无法触发 | **fail** | 被 Issue #1 阻塞 |
| 子 agent / task 工具 | motivation.md §Scenario: 子 agent/task 工具 | 旅程 J1：agent 任务中调用 task 工具派发子任务 | CLI 未启动，无法触发 | **fail** | 被 Issue #1 阻塞 |
| skill 调用 | motivation.md §Scenario: skill 调用 | 旅程 J1：触发 skill，观察 skill 加载并参与轮次 | CLI 未启动，无法触发 | **fail** | 被 Issue #1 阻塞 |
| REPL 内置命令 | motivation.md §Scenario: REPL 内置命令 | 旅程 J1：在 REPL 执行 `/compact`/`/tools`/`/history`/`/new`/`/use` | CLI 未启动，无法执行 | **fail** | 被 Issue #1 阻塞 |
| 无模式直接进入 REPL | motivation.md §Scenario: 无模式直接进 REPL | 旅程 J1/J3：`python -m coding_cli.main`（不带任何参数） | 报错 `model registry not initialized` 退出 1 | **fail** | 直接验证，证据：Exit code 1，错误输出见 Issue #1 |

### Requirement: LLM provider 选择与调用保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| anthropic provider 正常应答 | motivation.md §Scenario: anthropic provider | 旅程 J2：配置 anthropic provider，`--text` 发消息，观察应答 | CLI 启动即报 model registry 错误，无法到达 LLM 调用 | **fail** | 被 Issue #1 阻塞 |
| openai_compat provider 正常应答 | motivation.md §Scenario: openai_compat provider | 旅程 J2：配置 openai_compat provider，同上 | 同上 | **fail** | 被 Issue #1 阻塞 |
| 不支持的 provider 报错不变 | motivation.md §Scenario: 不支持的 provider 报错 | 配置未注册 provider，观察错误信息 | CLI 启动即报 model registry 错误（不是「unsupported provider」类错误），错误信息不符合预期 | **fail** | 报的是 registry 未初始化，不是 provider 不支持；错误类型混淆 |

---

## 辅助可观察证据

`--help` 输出确认以下有意移除的内容**已正确删除**（非 Scenario，仅记录）：
- `--mode {managed,remote}` 参数：已删除 ✓
- `--base-url` 参数：已删除 ✓
- `health` / `create-session` / `send-message` HTTP 子命令：已删除 ✓
- REPL 说明行 `In-process kernel: CLI holds Kernel directly via agent.sdk — no HTTP, no subprocess`：已显示 ✓

以上删除项符合 motivation.md「影响范围」中「有意移除的用户可观察面」要求。

---

## Side Findings

- CLI `--help` 中的 `--llm-base-url` 参数名与 `args.llm_base_url` 对应，但实际 argparse `dest` 是 `llm_base_url`（带下划线），而 `_build_llm_config_from_args` 读 `args.llm_base_url`——与参数相符，无 issue。

---

## 上层文档同步

（本轮因 blocking issue 未做全量旅程，文档同步检查在 pass 后补全）

- [x] `SPEC.md`（架构总览）：M4 清理阶段更新，本轮 N/A
- [x] `docs/内核设计SPEC.md`（agent 内核）：M4 阶段，本轮 N/A
- [x] `AGENTS.md` / `CLAUDE.md`：M4 阶段，本轮 N/A
- [x] `docs/CodingCLI-SPEC.md`：M4 阶段，本轮 N/A

---

# Round 2 — 2026-05-29

> **修复说明**：Round 1 blocking issue（Issue #1，`init_model_registry` 缺失）已由 commit 1f117be4 修复。
> `llm-config get` 验证正常返回。本轮重走全部 Scenario。

## Verdict

**fail**

## Highest Required Action

**fix-implementation**

## Issues

### Issue #2 — CLI 事件流消费崩溃：`StreamEvent.get` AttributeError（blocking）

- **Severity**: blocking
- **Symptom**: `--text` 模式和 REPL 模式发送任何消息后立即报错并退出，REPL 无法收到 agent 任何响应。
- **操作步骤与输出**:
  ```
  $ cd /tmp/reviewer-r2 && python -m coding_cli.main --text "hello"
  {"event": "submit_response", "run_id": "run_2767b5e1ce226fa0"}
  {"error": "'StreamEvent' object has no attribute 'get'", "layer": "runtime", ...}
  exit 1
  ```
  同一错误在三次独立调用（`--text "hello"`、`--text "你好"`、`--text "读取 calc.py"`）中均复现。
- **预期**: agent 响应流式输出在 REPL/--text 模式中可见，run 完成后正常退出 0。
- **实际**: `kernel.stream()` 产出 `StreamEvent` dataclass 对象，但 `commands.py` 的事件消费循环（`_run_text_mode` 第 410、415–416 行；`_run_repl` 第 716、731、736、744、747–748、760、763 行）全部调用 `event.get("key")`，dict 方法在 dataclass 对象上不存在，第一个事件即崩溃。
- **对比**: PA 侧同样问题已在 commit 189c356d 中修复（`inbound_pipeline.py`），`coding_cli/commands.py` 未同步更新。
- **Recommended Action**: fix-implementation
- **Action Rationale**: `commands.py` 中所有 `event.get("X")` 应改为 `event.data.get("X")`（或按 `StreamEvent` 的字段访问 `.event`/`.run_id` 等），对齐 PA 侧的修复方式。

### Issue #3 — 后台 worker ContextVar 跨 Context reset 报 ValueError（major）

- **Severity**: major（每次 run 结束时出现在 stderr，Issue #2 修复后需单独确认是否仍存在）
- **Symptom**:
  ```
  ValueError: <Token var=<ContextVar name='agent_observability_context'...> was created in a different Context
  Exception ignored in: <coroutine object RunsRegistry._run_worker_async at ...>
  ```
- **预期**: `RunsRegistry` worker 中 `bind_correlation` context manager 正常进入退出，无 ValueError。
- **实际**: `bind_correlation.__exit__` 调用 `_context.reset(token)` 失败——token 在不同 asyncio Context 中被创建（`RunsRegistry` 后台 loop vs CLI `asyncio.run` loop），Python 不允许跨 Context reset。
- **Recommended Action**: fix-implementation
- **Action Rationale**: 修复方向是确保 `ContextVar` token 的 set/reset 在同一 asyncio Context 内完成；或在 `RunsRegistry` 后台 loop 中运行 worker 时显式 copy 外层 context，让 `bind_correlation` 在 worker 自己的 context 内完成生命周期。此问题在 Issue #2 修复前被掩盖，需独立验证。

---

## User Journeys Exercised（Round 2）

| # | 旅程 | 覆盖的 Scenario | 结果 |
|---|---|---|---|
| J4 | `llm-config get` 命令 | REPL 内置命令（非 slash，llm-config 子命令） | **pass**：正常返回 `{"provider":"anthropic",...}` |
| J5 | `--text "hello"` —— 最基础通信 | 无模式进入 REPL + anthropic provider 应答 | **fail**：`StreamEvent.get` 崩溃，exit 1 |
| J6 | `--text "读取 calc.py"` —— 工具调用 | 多步工具调用完成真实编码任务 | **fail**：同上 |
| J7 | `--text "hello"` 连续 3 次验证可重现 | 重现性验证 | **fail**：每次均报同一错误 |

Issue #1（round 1）已修复：`init_model_registry` 不再报错，`llm-config get` 正常。
所有需要 `kernel.stream()` 的 Scenario 均被 Issue #2 blocking。

---

## 验收标准覆盖（Round 2 更新）

### Requirement: coding_cli 多步工具调用的 agent 任务正常完成 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 多步工具调用完成一个真实编码任务 | motivation.md §多步工具调用 | 旅程 J6：`--text "读取 calc.py"` | `StreamEvent.get` 崩溃，exit 1；agent 工具调用未到达 | **fail** | Issue #2 blocking |
| 工具权限确认 | motivation.md §工具权限确认 | 需先到达工具触发点 | 事件流崩溃，无法到达 | **fail** | Issue #2 blocking |
| 任务执行中途打断 | motivation.md §任务中途打断 | 需任务在运行中 | 无法到达 | **fail** | Issue #2 blocking |
| 后台任务完成通知 | motivation.md §后台任务完成通知 | 需任务运行完成后收到通知 | 无法到达 | **fail** | Issue #2 blocking |
| 子 agent / task 工具 | motivation.md §子 agent/task 工具 | 需在 run 中调 task 工具 | 无法到达 | **fail** | Issue #2 blocking |
| skill 调用 | motivation.md §skill 调用 | 需在 run 中触发 skill | 无法到达 | **fail** | Issue #2 blocking |
| REPL 内置命令 | motivation.md §REPL 内置命令 | 旅程 J4：`llm-config get` 正常；`/compact`/`/tools`/`/history`/`/new`/`/use` 需交互式 REPL，`--text` 路径因 Issue #2 无法到达 | `llm-config get` pass；slash 命令 inconclusive | **inconclusive** | llm-config 子命令 pass，slash 命令需修 Issue #2 后再验 |
| 无模式直接进入 REPL | motivation.md §无模式直接进 REPL | 旅程 J5：`python -m coding_cli.main --text "hello"` | CLI 启动正常（Issue #1 已修），submit 成功，stream 第一个事件即崩溃 | **fail** | Issue #1 已修；Issue #2 blocking |

### Requirement: LLM provider 选择与调用保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| anthropic provider 正常应答 | motivation.md §anthropic provider | 旅程 J5：默认 anthropic，`--text "hello"` | submit 成功，stream 崩溃，LLM 应答未到用户 | **fail** | Issue #2 blocking |
| openai_compat provider 正常应答 | motivation.md §openai_compat provider | 需切换 provider | 无法到达 provider 应答 | **fail** | Issue #2 blocking |
| 不支持的 provider 报错不变 | motivation.md §不支持 provider 报错 | 配置未注册 provider，观察报错 | stream 路径在 provider 应答前即崩溃于 `StreamEvent.get`，无法验证 provider 层错误 | **inconclusive** | 需先修 Issue #2 |

---

## 上层文档同步（Round 2）

（仍因 blocking issue 未完成全量旅程，延至 pass 后检查）

- [x] `SPEC.md`：无需更新（M4 已更新）
- [x] `docs/内核设计SPEC.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/CodingCLI-SPEC.md`：无需更新
