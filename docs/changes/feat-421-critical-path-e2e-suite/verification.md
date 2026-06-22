# Verification Report: feat-421

> Round 1 — 2026-06-22

## Summary

| 维度          | 结果      |
|---------------|-----------|
| Completeness  | 12/13（M2 tasks.md 退出标准未勾选为文档遗漏，实现完整；1 条 WARNING） |
| Correctness   | 10/11 covered；subagent 第二 scenario 缺独立测试（WARNING）；heartbeat 正确保留为 skip 复现资产（处置方式 WARNING） |
| Coherence     | 基本遵守；1 处违反 TESTING_GUIDE §7（WARNING） |

No critical issues. 3 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

### M1 退出标准（5/5 complete）

- [x] `scripts/e2e-critical.sh` 起真 IM+真 Gateway+真 LLM 并跑通 2 条奠基路径
- [x] 门控缺 proxy/config 时干净 skip 而非崩
- [x] catalog 列出全部 11 条 v1 路径（其余暂 TODO）+ backlog 段含「前端 UI smoke 独立 unit」
- [x] 起栈 fixture 传 `--wt <pytest tmp>` 隔离，不污染主仓；teardown 必走 `e2e-down.sh`
- [x] IM 黑盒客户端 `websockets` 依赖用 `pytest.importorskip` 可选化

### M2 退出标准（实现 4/4，文档 0/4 — tasks.md 未勾选）

tasks.md 的四条退出标准全部为 `[ ]`（未勾选），但实现均已完成：

- 9 条 test 文件落地：实测 11 个测试文件（含 M1 的 2 条），其中 9 条为 M2 新增 ✓
- 全套运行结果（progress.md）：`12 passed, 1 skipped in 229.37s`；`-m "not slow"` → `11 passed` ✓
- catalog 四列无 TODO（grep 确认 0 处 TODO）✓
- AGENTS.md 关键文档索引加挂 `docs/e2e-critical-paths.md` 链接（AGENTS.md:352）✓

**WARNING [W1]**：M2 `tasks.md` 退出标准全部为 `[ ]` 未勾选，与实际完成状态不符。
- 位置：`docs/changes/feat-421-critical-path-e2e-suite/M2-remaining-paths/tasks.md` 第 15-18 行
- 建议：将 4 条退出标准全部改为 `[x]`。

### Spec Requirement 覆盖检查

11 条 v1 关键路径在 spec 中的 Requirement 全部有对应实现（11 个测试文件）。heartbeat（原 #7）因真实产品 bug #126 保留为 skip 复现资产，属已知 out-of-unit 问题，在 catalog backlog 段诚实登记。

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 一条命令按需全跑关键路径 e2e | `scripts/e2e-critical.sh` | `conftest.py` 门控 | covered |
| 默认测试运行不触发真 LLM e2e | `conftest.py:39-52`（`_gate_or_skip()`）| M1 progress 实测 skip | covered |
| 时间驱动路径可单独跳过 | `conftest.py:164-169`（注册 slow marker），`e2e-critical.sh` 文档 | `-m "not slow"` 可筛 | covered |
| 单一权威 catalog 可对账（11条 + 四列） | `docs/e2e-critical-paths.md` | — | covered |
| 已知缺口 backlog 段诚实登记 | `docs/e2e-critical-paths.md:43-57` | — | covered |
| e2e 失败时留可诊断证据 | `conftest.py:146-152`（`_dump_logs`，起栈失败时 dump） | — | covered |
| **工具调用后回复**（agent 调工具再回复） | `test_tool_call_reply_critical_path.py::test_tool_call_then_reply_carries_sentinel` | 真跑 PASSED | covered |
| **bash 前台超时不卡死会话** | `test_bash_foreground_timeout_critical_path.py::test_foreground_bash_timeout_still_replies` | 真跑 PASSED | covered |
| **bash 后台任务完成后送达跟进通知** | `test_bash_background_notify_critical_path.py::test_background_bash_completion_sends_followup` | 真跑 PASSED | covered |
| **前台子 agent 可用且产出回带** | `test_subagent_foreground_critical_path.py::test_foreground_subagent_carries_back_output` | 真跑 PASSED | covered |
| **子 agent 失败不拖垮常驻进程**（spec 第二 Scenario） | 无独立测试函数 | **缺** | **WARNING** |
| **/stop 中止正在执行的运行** | `test_stop_run_critical_path.py::test_stop_aborts_active_run` | 真跑 PASSED | covered |
| **cron 定时任务自动推送** | `test_cron_push_critical_path.py::test_cron_job_auto_pushes_message`（slow） | 真跑 PASSED | covered |
| **heartbeat 有内容时主动冒泡**（slow） | `test_heartbeat_bubble_critical_path.py::test_heartbeat_bubbles_actionable_message` | 保留为 skip 复现资产，因 #126 | skip / WARNING（见 W3） |
| **群聊双向定向 @ — 人@A 再 A@B** | `test_group_chat_directed_mention_critical_path.py::test_human_mentions_a_then_a_mentions_b` | 真跑 PASSED | covered |
| **群聊 — 未被点名 agent 不抢话** | `test_group_chat_directed_mention_critical_path.py::test_unmentioned_agent_stays_silent` | 真跑 PASSED | covered |
| **权限审批 approve 后 run 继续** | `test_permission_approval_critical_path.py::test_permission_approve_lets_tool_run` | 真跑 PASSED | covered |
| **权限审批 deny 后工具不执行** | `test_permission_approval_critical_path.py::test_permission_deny_blocks_tool` | 真跑 PASSED | covered |
| **进程重启后会话续接** | `test_restart_session_continuity_critical_path.py::test_context_survives_gateway_restart` | 真跑 PASSED | covered |
| **经 IM 创建 agent 落地可聊** | `test_create_agent_via_im_critical_path.py::test_agent_created_via_im_lands_and_replies` | 真跑 PASSED | covered |

**WARNING [W2]**：spec Requirement「前台子 agent 可用且失败被隔离」有两个 Scenario，但只有一个测试函数只验第一个（"派子 agent 并带回结果"）。第二个 Scenario「子 agent 失败不拖垮常驻进程」在 catalog 的用户旅程描述中已声明（`docs/e2e-critical-paths.md:35`：「子 agent 失败被隔离不拖垮常驻进程」），但实际测试代码不覆盖此分支。

- 位置：`tests/e2e/critical_paths/test_subagent_foreground_critical_path.py`（只有一个测试函数）
- 建议：新增一个 `test_failed_subagent_isolated_from_main_process` 测试函数，让一个子 agent 执行注定失败的任务（如运行一个会出错的 bash），断言 Gateway 进程存活（能继续处理后续消息）。或在 catalog 第 4 条明确缩减用户旅程描述为只覆盖「产出回带」，将「失败隔离」另行登记为 backlog 条目。

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1：起栈复用 `e2e-up.sh`，fixture subprocess 调 `--wt <pytest tmp>` | 是 | `conftest.py:90-101` |
| 决策 2：新建 `_im_client.py` 封装 IM 黑盒客户端 | 是 | `tests/e2e/critical_paths/_im_client.py` |
| 决策 3：门控沿用 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` + health + config 三道 | 是 | `conftest.py:39-52` |
| 决策 4：鲁棒断言，注入随机哨兵 + 协议级 `message.completed`，不锁措辞 | 是 | 所有测试文件均使用随机哨兵 |
| 决策 5：cron/heartbeat 归 `@pytest.mark.slow` 子集，可筛 | 是 | `conftest.py:164-169`，两个测试文件 |
| 决策 6：catalog 落 `docs/e2e-critical-paths.md`，AGENTS.md 挂链 | 是 | `docs/e2e-critical-paths.md`，`AGENTS.md:352` |
| 决策 7：前端 UI 不并入本 unit，登记 backlog | 是 | `docs/e2e-critical-paths.md:51` |
| 纯新增测试 + 文档，不改产品代码（spec 非目标） | **基本是**（含 `scripts/e2e-up.sh` 鲁棒化）| M1 progress 说明该改动必需且行为等价 |

**架构自洽性**：本 unit 全部改动为新增测试文件、测试 helper、脚本、文档，不触碰任何产品包边界。`_im_client.py` 只走 IM 公开 HTTP/WS 接口，无 `src/` import，无依赖方向违反。

**WARNING [W3]**：heartbeat 测试用了 `@pytest.mark.skip`，违反 `docs/TESTING_GUIDE.md §7` 规定的已知产品 bug 处置方式。

- TESTING_GUIDE §7 明确：已知产品回归（测试正确、产品有 bug）**唯一合规例外**是 `@pytest.mark.xfail(strict=True, reason="<现象>; tracked in #<N>")`，条件：① 必须附 issue 编号；② `strict=True`（修好后转 xpass 自动报错，强制摘标）；③ 该测试不得删除。
- 位置：`tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py:29-34`
- 当前用的是 `@pytest.mark.skip(reason="... 见 #126 ...")`，而非 `@pytest.mark.xfail(strict=True)`。
- 影响：`skip` 不会在 bug 修复后自动提示「标记可以摘除」，`xfail(strict=True)` 修复后 pytest 报 xpass 强制摘标，更稳。
- 建议：将 `test_heartbeat_bubble_critical_path.py:29-34` 改为：
  ```python
  @pytest.mark.xfail(
      strict=True,
      reason="heartbeat 端到端不冒泡（真实产品 bug，见 #126）：静态启用 scheduler "
             "从未 triggered；动态 PATCH 启用虽 triggered 但 agent 回 HEARTBEAT_OK、投递被 "
             "_consume_heartbeat_run observer 静默抑制。bugfix 修复后转 xpass、去掉本标注。"
  )
  ```
  同时，由于 xfail 会尝试运行测试（当 `strict=True` 时，测试预期失败），需要确认测试在无真栈时会因门控 skip 而不运行，避免无 proxy 时触发真实 LLM 调用。可在函数体最开头加 `_gate_or_skip()` 或依赖 `e2e_stack` fixture 触发门控。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1 — M2 tasks.md 退出标准全部未勾选（文档遗漏）**

- 文件：`docs/changes/feat-421-critical-path-e2e-suite/M2-remaining-paths/tasks.md:15-18`
- 问题：4 条退出标准均为 `[ ]`，但实现已全部完成（progress.md 和 git history 可验），造成文档状态与实际不符。
- 建议：将 4 条 `[ ]` 改为 `[x]`。

**W2 — subagent 第二 Scenario「失败被隔离」无独立测试覆盖**

- 文件：`tests/e2e/critical_paths/test_subagent_foreground_critical_path.py`（只有 1 个测试函数）
- 关联：`docs/e2e-critical-paths.md:35`（catalog 声明同时守护了「失败隔离」）
- 问题：spec 的 subagent Requirement 有两个 Scenario，只有 Scenario 1「派子 agent 并带回结果」被测；Scenario 2「子 agent 失败不拖垮常驻进程」无测试函数，但 catalog 用户旅程列已声明守护它。
- 建议（二选一）：
  1. 在 `test_subagent_foreground_critical_path.py` 新增 `test_failed_subagent_isolated_from_main_process`，让子 agent 失败、断言 Gateway 进程存活后续消息仍能处理。
  2. 缩减 `docs/e2e-critical-paths.md:35` 的用户旅程描述，删去「子 agent 失败被隔离不拖垮常驻进程」，将该 scenario 移入 backlog。

**W3 — heartbeat 测试用 `skip` 而非 `xfail(strict=True)`，违反 TESTING_GUIDE §7**

- 文件：`tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py:29-34`
- 问题：TESTING_GUIDE §7 明确规定已知产品 bug 用 `xfail(strict=True)`（修复后自动报 xpass 强制摘标），`skip` 会让 bug 修复后此提示消失不见，降低可维护性。
- 建议：将 `@pytest.mark.skip(reason=...)` 替换为 `@pytest.mark.xfail(strict=True, reason=...)`；同时在函数体加 `_gate_or_skip()` 确保 xfail 只在真栈环境下尝试运行（避免无 proxy 时误触发 LLM 调用）。

### SUGGESTION（可以修）

**S1 — catalog v1 段序号 7 跳空，可读性有小瑕疵**

- 文件：`docs/e2e-critical-paths.md:37-38`（6 后直接跳 8）
- 问题：heartbeat 移入 backlog 后原序号保留，造成 v1 段序号不连续（6 → 8）。表头注释有说明（第 27 行），但直接阅读表格时会疑惑。
- 建议：要么将 7 保持空缺并在紧邻位置加一行注释解释，要么重新编号为 1-10 连续（并更新注释中的「原 #7」引用）。此为纯可读性问题，不影响功能。
