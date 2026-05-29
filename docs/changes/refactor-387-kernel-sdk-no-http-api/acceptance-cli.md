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
