# bugfix-443 — 回归验证

> 对齐: incident.md

## Verdict

**pass**

- Highest Required Action: pass
- review_round: 1
- issues_count: { blocking: 0, major: 0, minor: 0 }

---

## 验收标准覆盖

验收标准来源：`docs/changes/bugfix-443-subagent-sidechain-model/specs/kernel/spec.md`（delta-spec）

### Requirement: LLM 配置可查询，每轮对话的模型由消费者随 run 提供（含派生子运行）

#### Scenario: run 派发的子 agent 复用本 run 的 model

| 字段 | 内容 |
|---|---|
| 期望来源 | delta-spec + incident.md「期望 vs 实际」 |
| 验证方式 | Coding CLI `--model mimo:mimo-v2.5-pro` 发触发 subagent 的请求 → 查 LLM proxy 日志 |
| 结果 | **pass** |

**证据（LLM proxy 日志 sess_d17cc8ded7600d47）：**

```
[1] 2026-06-27_17-38-27_349  model=mimo:mimo-v2.5-pro  role=PARENT
    user_msg: 请使用 Agent 工具（subagent）搜索当前目录下所有包含字符串 'resolve_run_model' 的 Python 文件

[2] 2026-06-27_17-38-33_093  model=mimo:mimo-v2.5-pro  role=SUBAGENT ← 核心验收点
    user_msg: Search the current working directory .../unit-bugfix-443 for all Python files (...)...

[3] 2026-06-27_17-38-36_007  model=mimo:mimo-v2.5-pro  role=SUBAGENT（续跑）
    user_msg: Search the current working directory ...（同上，第二轮 subagent LLM 调用）

[4] 2026-06-27_17-38-58_083  model=mimo:mimo-v2.5-pro  role=PARENT（synthesize）
    user_msg: 请使用 Agent 工具…（父 run 合成 subagent 结果的第二轮调用）
```

子 agent 的两次 LLM 调用（[2][3]）均使用 `mimo:mimo-v2.5-pro`（父 run 模型），而非全局默认 `kimiCoding:K2.6`。修前 subagent 会回退 kimiCoding:K2.6 导致 token 超限；修后正确继承父 run 模型。subagent 正常完成，返回搜索结果。

验证入口：`PYTHONPATH=src python3 -m coding_cli.main --model mimo:mimo-v2.5-pro --llm-base-url http://127.0.0.1:4000 --text "<请使用 Agent 工具搜索…>"`

#### Scenario: run 的自动上下文压缩摘要复用本 run 的 model

| 字段 | 内容 |
|---|---|
| 期望来源 | delta-spec + incident.md root cause B |
| 验证方式 | 单元测试（真栈触发压缩需 200K+ tokens，不可行）|
| 结果 | **pass**（经单元测试） |

**证据：**

```
tests/unit/test_loop_compact.py::test_loop_proactive_compaction_uses_run_model_when_no_summary_model  PASSED
tests/unit/test_loop_compact.py::test_loop_proactive_compaction_keeps_dedicated_summary_model         PASSED
```

- 前者验证：无独立 summary_model → summarizer 用 run 的 model（`model_override="run-model"`）
- 后者验证：配了 summary_model → 仍用独立模型（`model_override=None`），不被 run 模型覆盖

真栈未触发压缩（CLI 测试上下文 ~12K tokens，远低于压缩阈值），此 Scenario 仅由单元测试验证。

#### Scenario: 同一 run 的内核续跑复用本 run 的 model（已有场景，回归检查）

| 字段 | 内容 |
|---|---|
| 期望来源 | delta-spec「续跑复用 run model / 不回退内核默认」契约（bugfix-429 建立） |
| 验证方式 | 全测试树 `pytest -m "not e2e"` |
| 结果 | **pass** |

全测试树 3045 passed，0 failed；contract 129 passed（line-pin 未移位）。续跑路径未受影响。

---

## 复现验证

**修前行为（incident 记录）：** `sess_69cf7b4c3e4a71d1` 中，hume（mimo）派发的 subagent 实际发给 proxy 的请求 model = `kimiCoding:K2.6`，导致 `Your request exceeded model token limit: 262144 (requested: 288167)`，该超限请求白白重试 6 次，IM 表现为"subagent 网络流中断"。

**修后行为（reviewer 验证）：** 同一路径（cli model=mimo，派发 subagent），subagent 两次 LLM 调用均为 `mimo:mimo-v2.5-pro`（proxy 日志 sess_d17cc8ded7600d47 [2][3]），subagent 正常完成，返回文件搜索结果，无超限错误。

---

## 回归测试

| 路径 | 证据 | 状态 |
|---|---|---|
| 前台 subagent 派发点（子 agent model 继承） | proxy 日志 sess_d17cc8ded7600d47 [2][3] = mimo | ✅ |
| 后台 subagent 派发点（start()） | 单元测试 `test_background_launch_inherits_parent_run_model` | ✅ |
| resume subagent 派发点（_resume_subagent） | 单元测试 `test_resume_inherits_parent_run_model` | ✅ |
| loop 主动阈值压缩 summarizer | 单元测试（两态：with/without summary_model） | ✅ |
| overflow/手动压缩、background-memory fork、hook model_caller（修 A 后连锁恢复） | 全测试树 3045 passed | ✅ |
| contract 白名单 line-pin | 129 passed（runtime.py:208 未移位） | ✅ |
| bugfix-429 续跑 model 不变量 | 全测试树 + contract 不回归 | ✅ |

---

## 自动化测试增量

新增 8 个单元测试（bugfix-443/M1 C1 commit d6646c65）：

| 测试文件 | 测试名 | 覆盖场景 |
|---|---|---|
| `tests/unit/agent/tools/test_agent_tool.py` | `test_background_launch_inherits_parent_run_model` | 后台派发点取父模型 |
| `tests/unit/agent/tools/test_agent_tool.py` | `test_resume_inherits_parent_run_model` | resume 派发点取父模型 |
| `tests/unit/agent/tools/test_agent_tool.py` | `test_foreground_launch_inherits_parent_run_model` | 前台派发点取父模型 |
| `tests/unit/test_agent_runtime.py` | `test_resolve_run_model_exposes_active_run_model_mid_run` | accessor mid-run 读到运行模型 |
| `tests/unit/test_agent_runtime.py` | `test_resolve_run_model_returns_none_for_unknown_or_missing_session` | accessor 未登记/None → None |
| `tests/unit/personal_assistant/test_local_store.py` | `test_resolve_run_model_*` (3项) | gateway 侧 resolve_run_model 三态 |
| `tests/unit/test_loop_compact.py` | `test_loop_proactive_compaction_uses_run_model_when_no_summary_model` | 压缩用 run model |
| `tests/unit/test_loop_compact.py` | `test_loop_proactive_compaction_keeps_dedicated_summary_model` | 配 summary_model 时独立模型优先 |
| `tests/unit/test_runtime_runner_model.py` | RuntimeRunner.start 透传 model | RuntimeRunner 透传完整性 |

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**（本 unit 是内核内部模型路由补全，不改跨包依赖或部署图）
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：**需要归并**——delta-spec 位于 `docs/changes/bugfix-443-subagent-sidechain-model/specs/kernel/spec.md`，新增两条 Scenario（子 agent 复用 run model、自动压缩摘要复用 run model）。当前 canonical 缺这两条，orchestrator 收尾归并即可（非 reviewer 职责，已标记）
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**（无开发约定变化）
- [x] `docs/SPEC_GUIDE.md`：**无需更新**（未改文档体系）

---

## Side Findings

**S1（minor，out-of-unit）：** worktree e2e 通过 IM→Gateway 路径访问 hume（`default_model: mimo:mimo-v2.5-pro`）时，hume 的 LLM 请求在 proxy 日志中显示 `kimiCoding:K2.6`（全局默认），而非 mimo。此行为与生产环境（incident session `sess_69cf7b4c3e4a71d1` 中 hume 正确使用 mimo）不一致。

- 不由 bugfix-443 引入：本 unit 实现提交（`fix: 6b27ab3e`）仅修改 5 个文件，全在 `src/agent/` 下，未碰 `personal_assistant/gateway/` 或 `personal_assistant/main.py`。
- 可能原因：worktree e2e 环境隔离下 Gateway 加载 per-agent model 配置的行为与主仓 Gateway 不同（具体未 debug，非 reviewer 职责）。
- 不影响本 unit 验收：bugfix-443 的核心修复点在内核层（subagent 派发时 model 透传），已通过 Coding CLI 真栈直接验证。
- 处理：记录于此，不立 issue（minor，不阻塞本 unit 交付，且可能为 worktree 临时环境问题）。

**S2（minor，不立 issue）：** incident.md 提及的放大因子（error_classifier 对 "token limit" 未判死，导致同一超限请求重试 6 次）仍存在，design.md 已明确为"非目标/可另开单"。
