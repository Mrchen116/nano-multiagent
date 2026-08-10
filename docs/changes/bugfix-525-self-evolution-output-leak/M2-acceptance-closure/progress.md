# bugfix-525-M2 — Progress

## Baseline

- Branch / commit: `milestone/bugfix-525-M2` / `639a5813cb9d17d7cd43c60c51864ca11e76aa84`。
- Context read: `incident.md`、`design.md`、`design-review.md`、全部 delta-spec、Round 1 `regression.md`（R1-I1/R1-I2）、current Gateway/IM contracts、testing/evidence/worktree-runtime/critical-path 规范与现有 fixture/helpers。
- Tests:
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -m 'not e2e'` → `3193 passed, 26 deselected, 22 warnings in 170.03s`。
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -m e2e tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py::test_agent_config_update_keeps_chat_context_with_stub_llm` → `1 passed in 8.03s`。
- Scope guard: M2 只建立 acceptance harness / runbook / E2E；M1 production classification、source marker、persistent unique owner 与 structured notice schema 均不修改。

## R1 — controlled no-save 真栈

- Context: Round 1 reviewer 能看到 raw 文本缺席，却无法证明 no-save review 真执行；验收还必须经过真 IM + production Gateway，而不是把 integration test 当产品证据。
- Decision: 新增 stateful OpenAI-compatible HTTP fixture；routing 只使用显式 scenario、非 classifier request 序号、message roles 与 tool result ids。fixture 的 `/state` 只提供 branch-independent 正向执行事实，用户可见结果仍从 IM REST/WS 断言。
- Rationale: fixture-owned 正向事实解决“没执行”和“执行但私有”不可区分；不新增 production debug/telemetry，也不读取 private review prompt 文案。
- TDD / debug:
  - Red 1: fixture 缺失，E2E 在 setup 明确失败：`missing fixture script: scripts/fixtures/openai_self_evolution_recording.py`。
  - Green attempt 1: 前台完成但 fixture 仅收到 1 个 request，30 秒内无 review。系统化取证：isolated session JSONL 的 metadata 已正确含 `memory_nudge_interval: 1`，但 runtime 的 `turn_count` 在 run 开始前从既有 history 统计；首轮为 0。既有 Kernel integration 同样用两个 foreground replies 触发 memory review。根因是 harness 错把首次 turn 当 nudge=1，不是 M1 路由缺陷。
  - Root fix: no-save scenario 先完成 seed turn，再在第二个 foreground turn 后进入 review；没有改生产代码或放宽等待窗。
- Evidence:
  - Tests: 新 no-save E2E + 既有 controlled Anthropic E2E → `2 passed in 15.10s`; changed-file Ruff 与 `git diff --check` 通过。
  - Entry: 真 IM HTTP/WS 发两条用户消息；第二条 foreground `FOREGROUND-NO-SAVE-COMPLETE` 以 `delivery_status=completed` 完成；fixture state 出现 `no_save_review_completed`；IM 历史只有两条 foreground Agent 消息与一条 structured memory system notice，`Nothing to save.` / `Traceback` 为 0。
  - Frontend State Matrix: N/A（无客户端变更）。
  - Browser QA: N/A（无 UI 变更；产品入口为 Web IM 使用的同一公开 REST/WS relay）。
  - E2E/Regression: `tests/e2e/critical_paths/test_self_evolution_visibility_critical_path.py::test_no_save_review_stays_private_after_foreground_completion`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 会同时移除 fixture 与对应 critical-path test，不影响 M1 production behavior。
- Commits: `fix(bugfix-525/M2/R1): 建立 no-save 确定性真栈验收`。
- Next: R2 在同一 fixture/真栈上加入 terminal gate、真实 Skill create 与 replay fault。

## R2 — terminal 后 Skill create + replay + 新 session 使用

- Context: Round 1 缺少能确定驱动真实 `skill_manage(create)`、foreground terminal 后 persistent owner/config sync，以及 reconnect/replay 不漏不重的产品旅程；Kernel stream 可见性不能替代 production composition 结果。
- Decision: 在 R1 OpenAI-compatible fixture 增加 Skill scenario。前台先真实调用 `skill_manage(list)` 形成一个 tool iteration，使 `skill_interval=1` 确定触发 review；review 请求在 fixture condition 上等待，直到 foreground `message.completed` 与 persistent subscriber `stream_opened` 都已观察到。随后放行真实 `skill_manage(create)`。测试专用 Gateway runner 只在替换 Gateway 进程中包装 production stream adapter，在 marked `skill_created(source=self_evolution)` yield 前切断一次，再记录同 sequence replay；production source/owner/filter 代码不变。
- Rationale: foreground terminal gate 排除了 per-run observer 仍存活的假阳性；fault-before-yield 强制 persistent subscriber 用既有 cursor 重连重放。最终断言全部来自真 IM/Gateway 后的 Agent config、消息历史、workspace 与新 conversation 的 tool timeline；runner record 只证明受控 transport fault 确实发生。
- TDD / debug:
  - Red: 新旅程首先以 `TypeError: restart_gateway() got an unexpected keyword argument 'gateway_entrypoint'` 失败，证明既有 harness 尚不能在 production entry 前安装受控 transport fault。
  - Green attempt 1: fork review 继承前台历史 tool result，fixture 把“历史存在任一 tool result”误判成 continuation。根因取证来自结构化 roles `[system,user,assistant,tool,assistant,user]`；分类收紧为最后一条 message role 必须是 `tool`。
  - Green attempt 2: request index 增至 7 而 record 仅两条；检查分类器确认 review fallback 未赋 `routing_basis`，导致请求在落盘前异常并被 provider retry。补齐同一 request-state routing basis。
  - Green attempt 3: review 的 create tool continuation 同时带前台与 review 历史 IDs，handler 误命中前台 ID。最终按最后一个 tool result ID 路由；不读取或匹配任何私有 prompt 文案。
- Evidence:
  - 真栈 Skill journey: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -m e2e tests/e2e/critical_paths/test_self_evolution_skill_activation_critical_path.py` → `1 passed in 20.60s`。
  - 可观察结果: foreground `FOREGROUND-SKILL-COMPLETE` 先以 `delivery_status=completed` 完成；真实 review tool call 创建 `deterministic-review-workflow`；fault record 中同一 sequence 恰好一对 `disconnected/replayed`；IM 仅一条 structured skills notice，raw `Saved: ...` / `Traceback` 为 0；Agent explicit allowlist 和隔离 workspace Skill 同步；关闭 self-evolution 后新 conversation 真实完成一次 `skill_view` 并回复 `NEW-SESSION-SKILL-USED`。
  - M1 routing/owner/config-sync focused suites → `95 passed, 2 warnings in 8.36s`。
  - 既有 fake-LLM config / prompt-cache / compaction 跨层 E2E → `3 passed in 51.72s`。
  - Frontend State Matrix / Browser QA / Visual / Prototype Comparison: N/A（无客户端或展示语义变更；实际入口为 Web IM 使用的同一 IM HTTP/WebSocket relay）。
- Rollback: 回退本 roadpoint commit 会移除 Skill/replay scenario、fixture-only Gateway runner 与对应 journey，保留 R1 no-save acceptance；M1 production behavior 不受影响。
- Commits: `fix(bugfix-525/M2/R2): 闭环 terminal 后 Skill 激活与重放验收`。
- Next: R3 固化一键 reviewer 命令、teardown 进程/端口/生成文件断言、catalog/runbook 与最终门禁。

## R3 — reviewer 入口、清理与质量门禁

- Context: 独立 reviewer 需要不读源码、不复用 integration test 的单命令入口；fixture 进程、端口、配置、workspace 与故障状态必须完全隔离且退出后可验证清理。
- Decision: 新增 `scripts/e2e-self-evolution.sh`，在 milestone worktree 内 `mktemp` runtime 并用 `--basetemp` 运行两条 permanent critical-path E2E；EXIT trap 只接受 worktree 内固定前缀并删除整套 runtime。共享 fake-LLM stack teardown 增加 production Gateway/IM/LLM PID、监听端口，以及 PID/ports/config/JWT/channel 文件清理断言；workspace 和 fault records 随 runner runtime 一起删除。critical-path catalog 与 fixture owner 文档同步登记。
- Rationale: reviewer 命令复用 production `e2e-up.sh` / `e2e-down.sh` 与既有 public IM client，不引入第二套产品入口；所有 fault/control 能力只存在于 fixture 进程。明确 teardown 断言可把“测试绿但留进程/端口/secret”变成测试失败。
- TDD / debug:
  - 首次 runner 中两条 journey 均通过，但 teardown 守卫报替换 Gateway PID 仍存在。进程随后消失且无监听残留；根因是该 Gateway 是 pytest 直接创建的 child，`e2e-down.sh` 已终止它但 shell 无法替 pytest 回收短暂 zombie。
  - Root fix: teardown 在进程退出轮询中对自己的 child 使用 non-blocking `waitpid`，对非 child 保持 `kill(pid, 0)` 检查；未放宽存活/端口/文件断言。
- Evidence:
  - Reviewer command: `scripts/e2e-self-evolution.sh` → `2 passed in 28.25s`；输出确认 runtime `/Users/czj/Repos/nano-multiagent/.worktrees/bugfix-525-M2/.e2e-self-evolution.XiYSJ6` 已删除。
  - Journey 1: fixture state 的 `no_save_review_completed` 是 branch-independent 正向事实；IM relay 前台回复完成，raw `Nothing to save.` / `Traceback` 为 0，只有 structured memory notice。
  - Journey 2: fixture state 的 `skill_review_waiting` / `skill_review_completed` 与 fault record 的同 sequence `disconnected/replayed` 证明 terminal-late review 和 transport replay 真发生；IM/Gateway 产品状态为恰好一条 structured skills notice、workspace Skill 存在、explicit allowlist 自动加入、新 conversation 实际完成 `skill_view`；raw `Saved: ...` / `Traceback` 为 0。
  - Cleanup: 每个 stack teardown 校验 Gateway/IM/LLM PID 已消失、IM/LLM ports 已关闭、`.gateway.pid` / `.im.pid` / `.e2e-ports.env` / `.e2e-jwt-secret` / `.gateway-config.yaml` / channel credentials/manifest 不存在；runner 再删除 worktree-local basetemp（含 workspace、DB、logs 与 fault state）并校验路径不存在。`pgrep` 后验无 fixture/Gateway 残留。
  - Full non-E2E: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -m 'not e2e'` → `3193 passed, 28 deselected, 22 warnings in 180.72s`。
  - Cross-layer: M1 focused → `95 passed, 2 warnings in 8.36s`; existing fake-LLM E2E → `3 passed in 51.72s`。
  - Quality: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check .` → pass；`PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs-check` → `documentation integrity passed: 228 maintained Markdown sources, 67 required routes`；`git diff --check` → pass；`bash -n scripts/e2e-self-evolution.sh` → pass。
  - Durable locators: `scripts/e2e-self-evolution.sh`、`tests/e2e/critical_paths/test_self_evolution_visibility_critical_path.py`、`tests/e2e/critical_paths/test_self_evolution_skill_activation_critical_path.py`、本文件。
  - Frontend State Matrix / Browser QA / Visual / Prototype Comparison: N/A（无客户端变更；两条自动化走 Web IM 同一实际 relay）。
- Rollback: 回退本 roadpoint commit 会移除 reviewer runner、catalog/fixture 文档和 teardown 守卫；R1/R2 单条 pytest 旅程仍保留。
- Commits: `test(bugfix-525/M2/R3): 固化 self-evolution 真栈验收入口`。
- Next: rebase 当前 `origin/unit/bugfix-525`，复验 runner/full non-E2E/质量门禁，合入并推送 unit branch。

## Promotion Candidates

None.
