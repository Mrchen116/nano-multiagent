# Verification Report: refactor-668-deterministic-e2e

> Validation snapshot: `8d428779b5ebe0bb0c5c277f2ca5b56c0a303b82 → 83a8f4d74d8f51e520be88dbef08f8c55b746bf4`
>
> Round R1 full + R2 targeted-closure (`c71d9dd05..83a8f4d74`); verification_mode: full with retained evidence; branch: `codex/refactor-668-deterministic-e2e`; requires_full_verification: false.

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 全部退出标准满足；全部 27 项具有适用通过证据 |
| Correctness | 32 项映射成立；R1 autostart 测试等待缺陷已在 R2 关闭 |
| Coherence | provider 边界控制、真进程/真工具与无产品改动边界遵守 |

**最终 verdict: pass — 0 CRITICAL、0 WARNING、0 SUGGESTION。** R1 曾有 1 CRITICAL、1 WARNING；R2 已关闭等待缺陷与完整 E2E 证据缺口。默认全量 **26 passed / 1 skipped / 329.26s**，原有显式 macOS gate 对应项另行 **1 passed / 38.28s**；不是单次 27 passed。代码审查 R1 发现保存在 `code-review-R1.json`，R2 patch/closure 无存活问题（`code-review-R2.json` 为 `[]`）。早期产品 LaunchAgent stop 缺陷怀疑未被最终证据支持，不作为已确认产品 bug。

## Round R2 / Retained Evidence

- Caller 固定新版本 `83a8f4d74d8f51e520be88dbef08f8c55b746bf4`；逐项检查 `c71d9dd05..83a8f4d74`，仅 `scripts/e2e-gateway-autostart.sh:42` 的未就绪返回值从 `0` 改为空串，以及 coverage 的证据事实校正。R1 对其余完整 diff 的源码审查、覆盖映射、no spec delta 和有效测试证据保留；无新增产品或 Context 影响，无需重跑整套静态审查。
- 独立抽取新固定版本的实际 `wait_for_new_gateway` 函数，以隔离状态文件验证：`ready=false/connected=false` 和 `ready=true/connected=false` 均 exit 1、无 PID；`ready=true/connected=true` 返回真实活 PID / exit 0。harness 仅把 `seq` 和 `sleep` 改为一次循环、无等待，函数与条件保持原样；未触发真实 stop/kill。
- 读取 `/tmp/refactor-668-autostart-final.log`：显式 `NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 python -m pytest -q --basetemp=/tmp/refactor-668-autostart-final tests/e2e/critical_paths/test_gateway_autostart_critical_path.py` 为 **1 passed / 38.28s**。脚本保留 crash、stop、bootstrap、disable 全部原断言，没有改产品、宽限、重试 stop 或新增 skip/xfail。W1 closed；原 stop 产品缺陷怀疑 refuted as a confirmed finding（不推断已证明所有平台不存在产品问题）。
- 读取 `/tmp/refactor-668-full-e2e-final.log`：默认 `tests/e2e` 全量为 **26 passed / 1 skipped / 329.26s**。caller 明确该轮从 `c71d9dd05` 启动，唯一 skip 是原有显式 macOS gate；随后代码 delta 只影响此轮跳过的 autostart 脚本及 coverage 文档，因此其余 26 项证据可 retained 至 `83a8f4d74`。与最终版本的显式 macOS 完整通过结合，全部 27 项有适用通过证据，C1 closed。

## Completeness

- M1-e2e 实现已覆盖 32 项旧测试的逐项处置。独立执行 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest --collect-only -q tests/e2e` 得到 27 items（22 critical + 5 environment）；逐项核对 `coverage.md:11` 起的映射及被删除源码，没有按文件名或测试数量推断覆盖。
- 合并的 5 个旧文件均有实际替代断言：前台 timeout 纳入后台生命周期参数；fork 纳入历史配置分叉；普通重启纳入 IM 创建；失败隔离纳入前台 child；工具后回复纳入 read/compact/restart。没有发现遗失的独有接线风险。
- `git diff --name-only 8d428779b..c71d9dd05 -- apps packages src` 为空，新 fix delta 仅脚本和 coverage；产品代码、运行配置与生产状态未修改。`git diff --check` 通过。
- 完整默认 E2E 26 passed / 1 skipped，显式 macOS 在正确 ready barrier 下另行完整 1 passed。逐项覆盖全部 27 项；版本保留依据见 R2。审批与 resilience 的早期定向证据已被默认全量再次覆盖。
- Prototype / Reference：N/A，零用户面。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 / 观察点 | 状态 |
|---|---|---|---|
| 全 32 项按失败原因审计与合并 | `coverage.md:11`；catalog `docs/development/e2e-critical-paths.md:29` | 新旧源码及 27 项实际收集；不同 seam 的环境生命周期保留 | covered |
| 默认无需真实 provider、真模型或凭据 | `tests/e2e/critical_paths/_recording.py:120`；`scripts/e2e-critical.sh:1` | 全 provider URL 重写本地；approval 独立 provider 也仅本地；其他路径不发送聊天任务 | covered |
| 配置变化保持历史、正确 system/tools | `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py:28` | wire 中旧/新用户内容、更新后的 prompt/read、持久配置 | covered |
| fork 截断与两线隔离、历史 runtime | `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py:126` | 分支无 later、源无 branch；旧/新 system 与 tools 分别成立；公开源消息不变 | covered |
| 创建前 capabilities/preview、创建落地、普通重启续接 | `tests/e2e/critical_paths/test_create_agent_via_im_critical_path.py:58`、`:129` | 真实 workspace/Agent 注册；重启后 messages 历史结构前缀、顺序、system/tools | covered |
| 工具执行后回复、压缩及重启保留目标 | `tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py:87` | 文件哨兵不在初始 prompt；真实 read tool_result、配对 ID、summary 请求与继续/重启请求 | covered |
| bash 显式后台与前台超时转后台 | `tests/e2e/critical_paths/test_bash_background_notify_critical_path.py:29` | 真 bash/job_output、两种不同返回形态、完成通知和不同 IM 气泡 | covered |
| /stop 中止真实执行且后续可用 | `tests/e2e/critical_paths/test_stop_run_critical_path.py:47` | 实际 shell PID 退出、完成文件不产生、停止反馈和后续 provider 请求/回复 | covered |
| Schedule / Heartbeat 自动触发与交付 | `tests/e2e/critical_paths/test_cron_push_critical_path.py:29`；`test_heartbeat_bubble_critical_path.py:29` | 真 schedule_create 结果、自动 wake 正文、仅 1 条用户输入；心跳文件/cadence，finally 关闭 | covered |
| 群聊定向提及与未点名 gate | `tests/e2e/critical_paths/test_group_chat_directed_mention_critical_path.py:27` | 真 IM mention、B wire 正文；独立第二群 B 无消息且无 provider 请求 | covered |
| 原生 child 成功/失败隔离 | `tests/e2e/critical_paths/test_subagent_foreground_critical_path.py:20` | 成功 tool_result 正文、失败 is_error、2 个实际 child sessions、后续健康回复 | covered |
| Global Inbox → 同一 child → 原聊天投递 | `tests/e2e/critical_paths/test_global_agent_inbox_critical_path.py:183`、`:216` | 真实 Inbox body 与 committed facts、同主/子 session、child Work/wire 修订、仅一条公开 dispatch | covered |
| 人工审批及审核模型接线 | `tests/e2e/critical_paths/test_permission_approval_critical_path.py:72`；`test_tool_approval_model_critical_path.py:228` | allow/deny 写入与持久状态；configured/omitted/failure/unregistered model 的 wire/启动事实 | covered，6 passed |
| 进程连接恢复与生命周期 | `scripts/e2e-resilience.sh:70`；`tests/e2e/critical_paths/test_gateway_autostart_critical_path.py:64` | resilience 定向 1 passed；autostart 正确 ready barrier 后显式完整路径 1 passed | covered |
| 其余环境/资源清理与 token 投影 | `tests/e2e/test_worktree_stack_lifecycle_e2e.py:113`；`test_daily_acceptance_environment_e2e.py:22`；`critical_paths/test_token_usage_critical_path.py` | 源码保护保留；provider fixture 失败清理测试改为共享 helper；最终默认全量通过 | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 仅 provider HTTP 控制响应，产品/工具真执行 | 是 | `scripts/fixtures/anthropic_sse_events_recording.py:93`、`anthropic_sse_collaboration_recording.py:112`；实际请求与 tool_result/公开事实断言 |
| 真实 Context 请求，非模型背哨兵 | 是 | 普通重启完整历史前缀、fork 截断、read 结果与 summary 配对 |
| 全默认 critical 无 live proxy | 是 | 删除 live fixture 和 gate；`_recording.py` 重写 provider；approval fixture 本地模型配置 |
| 不建 DSL/模拟 Agent Loop、不写 DB/伪造 Work | 是 | 新 provider 脚本仅 SSE/HTTP 响应；测试读真实 Work、通过公开 IM APIs 驱动 |
| 不改产品代码，已知缺陷单独报告且保留断言 | 是 | apps/packages/src 无 diff；autostart 原断言保留，无新 skip/xfail；coverage 已校正未经证实的产品故障归因 |
| 全量 E2E、本地 CI 通过 | 是 | 默认 26 passed / 1 skipped + 显式 macOS 1 passed；后端/Python/typecheck/iOS/docs/ruff 通过，前端失败文件已定向复验 |

本 unit 不改变产品 Context 的选择、注入或恢复，只改验证输入和观察方法，因此不触发完整 Implementation Context Review。已审查测试中模型可见请求与真实工具结果，未以 fixture 的最终固定答案充当唯一证据。

### Prototype / Reference Contract

N/A。

## Evidence

复用 caller 交接的该实现工作区证据，并直接检查日志结尾：

最终 E2E 命令（workdir 为本 unit 工作树；默认 pyproject timeout）：

```bash
PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH PYTHONPATH=src python -m pytest -q --basetemp=/tmp/refactor-668-final-e2e tests/e2e > /tmp/refactor-668-full-e2e-final.log 2>&1
PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH PYTHONPATH=src NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 python -m pytest -q --basetemp=/tmp/refactor-668-autostart-final tests/e2e/critical_paths/test_gateway_autostart_critical_path.py > /tmp/refactor-668-autostart-final.log 2>&1
```

| 命令 / 门禁 | 结果 | 定位及限制 |
|---|---|---|
| `pnpm test --maxWorkers=2` | 142 files / 766 passed | `/tmp/refactor-668-pnpm-test-2.log` |
| Python non-E2E | 70 passed / 27 deselected | `/tmp/refactor-668-python-tests.log` |
| 指定 history、trajectory、cron、heartbeat、single-thread、global-agent | 6 files / 78 passed | `/tmp/refactor-668-low-tests.log`；低层 seam 不冒充 IM 全栈 |
| `pnpm -r --if-present typecheck`；iOS runtime | 通过 | `/tmp/refactor-668-typecheck.log` |
| docs-check | 通过，292 maintained Markdown | `/tmp/refactor-668-docs-check-final.log` |
| ruff check / format | caller 报告全仓通过 | 本 reviewer 未重复运行 |
| 前端全量及失败文件单 worker 复验 | 首轮 106 files 通过、2 files/2 tests 失败；复验 2 files/77 passed | `/tmp/refactor-668-frontend-tests.log`、`/tmp/refactor-668-frontend-retry.log`；不得称首次全绿 |
| audit critical | caller 报告 exit 0，仍有 11 非 critical | 未改依赖 |
| 审批与重连定向 | 6 passed；1 passed | `/tmp/refactor-668-approval-3.log`、`/tmp/refactor-668-resilience-retry.log` |
| macOS 显式 autostart | 1 passed / 38.28s | `/tmp/refactor-668-autostart-final.log`；正确 ready barrier 后真实 crash/stop/bootstrap/disable 全链 |
| 默认完整 `tests/e2e` | 26 passed / 1 skipped / 329.26s | `/tmp/refactor-668-full-e2e-final.log`；c71d9dd05 的 26 项至 83a8f4d74 无代码差异；唯一原有 macOS gate skip 另有最终版本通过证据 |
| 冻结 R1 ready guard 隔离复现 | 未 ready 状态返回 0 / exit 0 | 从 `git show c71d9dd05:scripts/e2e-gateway-autostart.sh` 抽取函数，状态 `{pid:123456,ready:false,connected:false}`，调用 `wait_for_new_gateway 123456`；无产品或模型调用 |

没有启动独立产品服务或真实模型；仅收集测试和执行隔离 shell 函数，无新现场需要清理。

## Issues

### CRITICAL

- 无存活 CRITICAL。R1 C1（M1 完整 E2E 退出证据）已凭默认全量与显式 macOS 的适用证据关闭；见 R2。

### WARNING

- 无存活 WARNING。R1 W1（not-ready 的 `0` 被当作有效替换进程）已在 `83a8f4d74` 修复并独立复验关闭；coverage 已以最终证据更正，见 R2 段。

### SUGGESTION（可以修）

无。

## Corrected Delta Reconciliation

**no spec delta**。`docs/specs/`、产品源码与 production config 无 diff；变更限于测试/fixture/脚本/开发策略文档。新增和更新的开发说明与实际 provider 边界控制一致；没有遗漏需写入产品 delta-spec 的对外行为。

### Uncovered Observable Behavior

None。无产品用户面变化；平台显式 gate 沿用原约定，未新增 skip/xfail。

Outcome: aligned（no spec delta）。

All checks passed. Ready for PR.

## Round R3 — Send Revalidation Delta

> verification_mode: delta; code_review_mode: patch; review_round: R3
>
> executed_base / patch base: `ab88005d93c134442c879dfdd5c27ea2868b441c`
>
> validated_at: `01d238d41c9631e04584b9e1a7d4a4ec0c080471`
>
> branch: `codex/refactor-668-deterministic-e2e`; requires_full_verification: false.

**R3 verdict: pass — 0 CRITICAL、0 WARNING、0 SUGGESTION；code review 无存活问题（`code-review-R3.json` 为 `[]`）。** R1/R2 历史及其有效证据保留。新增一项独立确定性 E2E 后当前为 28 items（23 critical + 5 environment）；没有在本轮重新运行或声称一次完整 28 项全绿。

### Scope and Retained Evidence

用户追加要求：若原 27 项尚未覆盖发送前收到最新消息，就补确定性 E2E，并考虑模型生成时延。完整检查 `ab88005d93c134442c879dfdd5c27ea2868b441c..01d238d41c9631e04584b9e1a7d4a4ec0c080471` 的 5 个文件：独立 provider、独立 test、catalog、coverage 与 fixtures README。没有产品代码、配置或共享 fixture 改动；未扩大到产品修复或真实模型任务。

原 mention 用例保护定向路由，原 Global J2 保护 Inbox 跨聊天与 child/dispatch，二者均没有“多个已开始的模型请求被后来消息作废、读取后再次作废”的交错，因此新建独立用例有不同的失败原因，不是按测试名称增加重复保护。低层 `packages/personal-assistant/tests/global-agent.test.ts:108` 的 held-draft 保护使用产品模块替身，保留它以验证其他目标/背景等分支，不把它当 IM/Node/DSH 全栈接线证明。

原 27 项测试、共享 provider fixture 和产品代码在本 delta 中未改变，因此 R2 的默认 26 passed / 1 skipped + 显式 macOS 1 passed 及既有 CI 结论保持适用。新的受影响全栈 seam 用新增 test、既有 mention 和 Global J2 三项窄验证补齐；不机械重复无变化的全量。

### Completeness / Correctness

| 追加需求或 current 契约 | 实现与直接证据 | 结论 |
|---|---|---|
| 模型生成有真实时延，旧草稿已开始生成后才收到新消息 | `scripts/fixtures/anthropic_sse_send_revalidation_recording.py:87` 在从实际 read tool_result 计算 numbers 后登记 pending 并阻塞 HTTP 响应；`tests/e2e/critical_paths/test_group_send_revalidation_critical_path.py:119` 等 A/B/C/D 四个初次生成都 pending、公开消息为空，并断言各自 read-0 只有实际初始消息 ID，才放行 A | covered；不是通过固定 sleep 猜测生成已开始 |
| 无新消息时正常发送 | current `docs/specs/gateway/global-agent.md:67`；先仅释放 A，实际公开第一条为 1，后续实际 provider 请求中 draft-0 status=sent，A 的实际 tool_use 文本仅 `[1]` | covered |
| 新消息到达后，旧稿不能先公开，需读取再重新发送 | current `docs/specs/gateway/global-agent.md:72`；D/B/C 初次发送参数均为 1，实际 tool_result 为 held_for_revalidation；下一次请求带实际 Inbox read 结果；B/C 随后实际参数分别为 `[1,2]`、`[1,3]`；公开正文为 1/2/3/4 且发言者 A/B/C/D，无旧 1 泄漏 | covered |
| 读取后再次收到消息，发送须再次复核 | current `docs/specs/gateway/global-agent.md:78`；test `:128` 放行 D 的旧 1，等待 D:1，断言旧发送 held 且 read-1 仅 A 的实际消息 ID，此时 D 已从该 read 结果算出 2 并暂停；之后才放行 B/C 并等其公开 2/3，最后释放 D:1；D 实际草稿参数 `[1,2,4]`、前两次 held、最后 sent | covered；第二次作废跨过另一个实际进行中的模型请求 |
| 不能只以 fixture 固定最终答案证明摄取完整性 | test `:144` 检查实际请求中的所有 send_message tool_use 文本、held/sent 工具结果；`:170` 从实际 read tool_result 中按真实消息 ID 查正文，逐项对照先前公开消息；fixture `:88` 仅从 Inbox tool_result 正文取数算下一值 | covered；不存在独立按角色硬编码最终数字后跳过产品的写入 |
| 唯一公开交付与不泄漏 held 草稿 | test `:138` 断言唯一 4 个公开消息 ID、精确正文顺序和发言者，再等待各角色实际 sent 结果，最后再次断言仍为 4 条；固定响应的 Done 为 Global 内部 prose，不作为公开交付证据 | covered |

同时核对实际产品 owner：`packages/personal-assistant/src/global-agent.ts:600` 起以 Inbox blocking 判断适用新消息，真实返回 held_for_revalidation、保留 draft 并阻止 relay；无 blocking 时才请求实际 agent.message 并返回 sent。新 fixture 没有伪造这些结果，没有直接写 DB、Work 或产品状态；release HTTP 只控制本地 provider 何时返回工具调用。

### Coherence / Limits

- 仅 provider HTTP seam 控制响应，复用现有 `_recording.py` 真 IM/Node/DSH 栈。四 Agent 创建、初始消息、Inbox、审批、发送复核与公开消息均走现有产品入口。
- Guardian 请求按实际 guardian_* 工具识别并单独记录，断言读取的生成请求排除 Guardian；不会把审核请求当作 Agent 的生成或读取证据。初次 fixture Guardian 漏识别失败已修，其失败不作为产品 bug。
- 有界等待用于真实 gate 或可观察结果，初次四 gate 及 D 第二 gate 均由本地 provider 的 pending 证明；没有依赖任意固定时长来建立关键先后关系。共享 fixture 拥有原有进程回收，新 test 不启动另一套产品进程。
- 新测试证明 Global Web 群聊、ALWAYS 策略下的机制和双次失效，不声称评估模型理解/规划/自主选工具的概率，也不声称新增覆盖私聊、Feishu、其他群及仅背景消息的全部分支。这些界限不影响本次明确追加场景的完成度。
- 本 delta 不改变产品 Context 的选择、注入、加载或恢复；只补验证输入与实际请求观察，因此无需新增完整 Implementation Context Review。

### R3 Evidence

| Evidence | Result / version applicability |
|---|---|
| caller 的 `PYTHONPATH=src python -m pytest -q tests/e2e/critical_paths/test_group_send_revalidation_critical_path.py tests/e2e/critical_paths/test_group_chat_directed_mention_critical_path.py tests/e2e/critical_paths/test_global_agent_inbox_critical_path.py` | 直接读取 `/tmp/refactor-668-send-final.log`：3 passed / 43.29s；适用于冻结 HEAD 的新增 test 与两个受影响接线相邻场景 |
| 先前新增单项 | caller 交接 1 passed / 13.36s；非唯一通过依据 |
| reviewer 独立 `python -m pytest --collect-only -q tests/e2e`（主仓 venv） | 28 tests collected / 0.14s；仅证明登记和收集，不冒充执行通过 |
| reviewer `git diff --check ab88005d93c134442c879dfdd5c27ea2868b441c..01d238d41c9631e04584b9e1a7d4a4ec0c080471` | 通过 |
| ruff / docs-check | caller 交接通过；未重复已有有效检查 |

本 reviewer 未启动额外服务或调用真实模型，无新增现场需要清理。

### R3 Issues

CRITICAL: none。WARNING: none。SUGGESTION: none。

### R3 Spec Reconciliation

**no spec delta**。新增测试验证 existing current `docs/specs/gateway/global-agent.md:65` 的发送前复核契约；5 文件 delta 没有产品用户面变化，没有遗漏需要新增或归并的产品行为。catalog/coverage/fixtures README 已准确描述新增能力和时延控制。Outcome: aligned。R2 的 no spec delta 结论保留。

R3 delta verification passed. Ready for PR update.

## Round R4 — Eight Test-Value Audit Groups

> verification_mode: delta; code_review_mode: patch; review_round: R4
>
> patch base: `7566971e736f2f07cb18302f8690218a7b13f3f7`
>
> validated_at: `a3ee25dc1d133e0f583306d659441c7613604534`
>
> executed_base / effective_base: `8d428779b5ebe0bb0c5c277f2ca5b56c0a303b82`
>
> branch: `codex/refactor-668-deterministic-e2e`; requires_full_verification: false.

**R4 verdict: pass — 0 CRITICAL、0 WARNING、0 SUGGESTION。Code review findings: `[]`（`code-review-R4.json`）。** 已独立检查全部 12 文件 delta 与 8 组审计问题；没有未闭合项。R1–R3 历史及其有效结论保留。本轮结论针对固定版本的增量，不代替随后 PR 当前 head 的远端 CI，也不表示已合并。

### Scope / Retained Evidence

用户授权在同一 PR 处理审计确认的 8 组问题，增量设计已在 `design-review.md` Round 2 独立 APPROVED。审查读取原审计 `/Users/czj/.codex/reports/test-value-audit-20261028/report.md`、隔离强化证据目录 `/Users/czj/.codex/reports/test-value-audit-fixes-20261028/` 的 `mutations.py`、`mutation-results.json`、正常与各 mutant 日志，并回到当前实际源码核实。

本 delta 仅有 4 个 unit 文档、6 个测试文件、1 个 product-contracts 测试和归档辅助脚本的修改（共 12 文件；测试文件按实际路径计共 7 个）。没有产品 runtime、前端产品组件、生产配置、E2E/provider 或共享 E2E fixture 修改。原 28 项 E2E 与旧后端有效门禁保留；前端和 Python 本轮另有适用全量结果，不把 non-E2E 84 passed 计作重新执行 E2E。

### Completeness / Correctness — Eight Groups

| 组 | 实施、保留保护与直接证据 | 结论 |
|---|---|---|
| 1. legacy SHA manifest 可选链允许 null | `packages/product-contracts/tests/node-update.test.ts:23` 先完整断言 parsed 等于输入，再断言未增 updater_protocol/data_epoch；原非法输入参数化保留。正常 8 passed；相同测试的隔离“40 位 SHA 全返回 null” mutant 在 `mutant-manifest-reject-legacy.log` 精确失败于 `expected null to deeply equal`，1 failed / 7 passed | closed |
| 2. 两个路由接受侧栏/错误页 | `src/IM/frontend/src/app/router.test.tsx:24` 提供 HTTP 数据，真实 appRoutes/页面/API adapter 仍被执行；`:81` 要实际 Agent 行和设备，`:88` 要可用创建表单及 URL 指定 node-2；fixture 的首个默认节点是 node-1，因此不能靠默认选择冒充路由参数。隔离替换为空列表页和固定错误创建页后，两项分别在页面内容断言失败，2 failed / 2 passed；不是 import/构建失败 | closed |
| 3. i18n setter 掩盖默认值 | `src/IM/frontend/src/i18n/i18n.test.ts:4` 清 localStorage/模块缓存后动态 import，不先调用 setter；第二项保持 setter、翻译与存储检查，并重新冷初始化恢复 zh。实际 owner `i18n/index.ts` 使用 createInstance + readPersistedLocale，模块 reset 会重走该入口。默认改 zh 的 mutant 精确失败 `expected 'zh' to be 'en'`，1 failed / 1 passed | closed |
| 4. rail 错称 nodes join | `src/IM/frontend/src/features/settings/agents/agents-rail-desktop.test.tsx:7` 仅 mock 实际 listPublicAgents；两行采用不同 PublicAgent.node_name，按各自行验证设备、active 与点击 agent-two 回调。实际 rail 的 nodes 固定空数组，已删除从未消费的 listNodes mock。丢 node_name 的 mutant 使新接线用例失败，1 failed / 1 passed；既有 AgentRow 的 nodes lookup mutant 6 failed / 8 passed，证明回退/alias 分支由原 owner 保护，未把它误算为 rail 覆盖 | closed |
| 5. emoji 完全重复 | 删除的 bash historical-fallback 用例与保留的 `tool-calls-panel.test.tsx` known-name emoji 用例具有相同输入、expandPanel 与 💻 断言。unknown 通用图标、真实 tool name、显式 emoji 优先级均保留 | closed；无独有分支损失 |
| 6. rail 颜色重复 | 删除上层 CSS 颜色用例，保留 `agent-row.test.tsx` normal/active 的名称、ID、设备颜色保护；真实 rail 仍经 AgentLifecycleRow 使用同一 AgentRow，新增 active 与点击接线断言归属正确 | closed；同因最低层保护保留 |
| 7. 两项整句自然语言政策 | 删除 simplified-flow 和 Ready-PR 三片段匹配，不再将自然语言措辞当机器协议；`test_change_workflow_documentation_contract.py` 的实际门禁矩阵解析仍在，archive 黑盒与稳定 PR 链接检查仍在。删除范围与审计/设计相符，未顺带移除其他有效架构或行为契约 | closed；不需要用新的文本解析框架替代 |
| 8. codex unit 分支绕过归档 | `scripts/check_change_unit_archived.py:13` 同一 regex 提取 unit/codex 两前缀的 ID；`:51` 将已知四类 codex unit 候选送入校验，疑似 unit 的无效编号失败，普通 codex/docs-cleanup 跳过。黑盒参数化两个前缀的 archived/active/retired/missing/duplicate，并覆盖四类 suffix 与 malformed 分支。旧脚本 11 failed / 14 passed，修复后 archive+workflow 27 passed；reviewer 在冻结 HEAD 独立重跑也是 27 passed | closed |

### Archive / CI Wiring

独立读取 `.github/workflows/ci.yml:116` 的实际 backend step：PR 事件条件、head_ref env 和命令真实存在，且没有 continue-on-error。新测试使用 BaseLoader 保留 YAML `on`，查 backend 中具体 step，而非全文件字符串存在；检查 pull_request 触发、step 的 PR 条件、shlex 解析后的完整调用参数、`GITHUB_HEAD_REF=${{ github.head_ref }}` 和非忽略失败。该断言保护当前实际接线，不声称通过 YAML 解析执行了 GitHub Actions。

reviewer 另直接运行：

```bash
/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_change_skill_archive_contract.py tests/contract/test_change_workflow_documentation_contract.py
/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/check_change_unit_archived.py --head-ref codex/refactor-668-deterministic-e2e
```

结果 **27 passed / 0.56s**；当前 codex/refactor-668 分支输出 `Change unit refactor-668 is archived at docs/changes/archive/refactor-668-deterministic-e2e.`。这确认实际 CLI 执行归档判断，并非仅被测试名称或输出 substring 冒充。

### Mutation Evidence / Reliability

隔离脚本逐项保存和恢复产品源码，只在仓库外副本执行 Vitest；正常前端基线 4 files / 75 passed、manifest 8 passed。reviewer 比较了隔离副本中的六份相关/保留测试（router、i18n、rail、AgentRow、tool panel、manifest）与冻结工作树字节，均相同；读取真实失败日志确认是预期行为断言失败，没有把未收集、构建失败或不相关 crash 当作 mutation 成功。

本轮五种 mutation 包括错误默认、两条错误路由、拒 legacy、rail 丢设备字段和已有 AgentRow 丢 nodes lookup。它们证明审计中的特定坏实现被拦截，不声称穷尽全部可能缺陷。隔离脚本不进长期测试套件，不引入通用 mutation 框架；没有扩大到慢测试、超长文件或 E2E CI 接入等未授权工作。

### R4 Validation Evidence

| Evidence / command | Result / applicability |
|---|---|
| 前端相关 5 files | caller 交接 89 passed；测试范围含保留 AgentRow 保护 |
| 前端完整 `vitest run --maxWorkers=2` | 直接读取 `/tmp/refactor-668-audit-frontend-full.log`：108 files / 1029 passed / 55.03s |
| 前端 `tsc -b` | caller 报告通过；`/tmp/refactor-668-audit-frontend-types.log` 为空输出，本 reviewer 不将空日志单独视为退出码证明 |
| product-contracts | `/tmp/refactor-668-audit-contracts.log`：3 files / 16 passed |
| Python non-E2E | `/tmp/refactor-668-audit-python-full.log`：84 passed / 28 deselected / 6.21s |
| archive red/green | `/tmp/refactor-668-audit-archive-red.log`：旧脚本 11 failed / 14 passed；`archive-green.log`：修复后 archive+workflow 27 passed；reviewer 独立复验同样通过 |
| docs-check / ruff check + format | caller 交接通过；未机械重跑有效全量检查 |
| `git diff --check 7566971e..a3ee25dc` | reviewer 独立通过 |

### Coherence / Spec Reconciliation

实现与新增 design 的全部八行及验证计划一致；新增保护留在现有 parser、路由、i18n、rail/row 和 archive 黑盒 owner，删除范围小且可审，没有产品 UI 改动、原型或美术 must-match。没有影响模型可见 Context 的选择、注入、加载、更新或恢复，无需完整 Agent Context Implementation Review。

**no spec delta**。产品组件、runtime、公开 product-contracts parser 实现与 `docs/specs/` 均未变化；归档辅助 CLI 对 codex unit 分支新增强制检查属于本次明确授权的开发门禁修复，已由 unit design/coverage 和当前 CI 黑盒保护说明，不应误写成产品行为 delta。没有遗漏的产品用户面变化需要归并。Outcome: aligned。

### R4 Issues / Completion

CRITICAL: none。WARNING: none。SUGGESTION: none。八组均 closed；未发现需要扩大 full verification 的共享边界变化。仅写本 R4 节与 `code-review-R4.json`，未修改实现、测试、设计或提交；没有启动服务、真实模型或新增需清理的现场。

R4 patch code review and delta verification passed. Ready for PR update and current-head CI.
