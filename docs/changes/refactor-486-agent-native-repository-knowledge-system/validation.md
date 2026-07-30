# Repository Harness Validation

> 日期：2026-07-30
>
> 范围：验证重构后的知识入口、current/history 边界、恢复能力和隔离运行入口。本文是
> `refactor-486` 的验收记录，不是新的 current owner。

## 结论

机械可达性、真实隔离 runtime 和七类独立冷启动 Agent 任务均通过。Agent 能从根入口找到正确知识，
区分 current、proposed、history 与 runtime evidence，并在文档快照与实时状态不一致时继续核对代码、
测试、Git、进程和日志。

冷测也发现了仓库原有的文档、skill 和 active unit 漂移。它们集中记录在
[`drift-review.md`](drift-review.md)，没有借验收过程直接修改产品流程或代码。

## 冷启动测试设计

- 每项任务使用没有本次聊天历史的独立 Agent，只提供仓库路径、任务场景、只读/清理边界和回报格式；
  不提供预期文档路径或标准答案。
- 第一批架构、IM 和 runtime 任务在当前迁移分支执行。IM Agent 在结论形成后的一次宽泛搜索中看见了
  本文件摘要，因此该结果没有作为严格盲测证据。
- 后续任务与 IM 重跑使用 detached snapshot `4e95552a4`。该提交已包含阶段 0–7 的目标文档体系，但
  尚不存在 `validation.md`，消除了仓库内参考答案污染。
- 每个 Agent 必须报告真实读取顺序、命令、authority 判断、误入路径和阻塞；评价以行为轨迹为准，
  不只看最终答案。
- 所有调查 worktree 最终保持 clean；真实 runtime Agent 只创建临时隔离目录，并在验收后清理。

## 代表性任务

| 任务 | 实际入口链 | 观察结果 | 结论 |
|---|---|---|---|
| 判断四个顶层包的依赖边界 | [`AGENTS.md`](../../../AGENTS.md) → [`docs/README.md`](../../README.md) → [`SPEC.md`](../../../SPEC.md) → code / `tests/contract/` | 正确还原四包职责和允许/禁止依赖，未使用 history；主动定位并运行 21 个聚焦 contract tests | Pass（冷启动） |
| 修改 IM 用户可观察行为 | `AGENTS.md` → docs map → [`IM spec`](../../specs/im/spec.md) → [`web-chat-ux.md`](../../specs/im/web-chat-ux.md) → [`change-workflow.md`](../../development/change-workflow.md) → active unit | 严格重跑仍能区分 current area 与 `feat-484` proposed delta，并核对 unit branch/acceptance；未把更详细或更新的 delta 当 current | Pass（无答案快照重跑） |
| 在 worktree 启动真实 IM/Gateway | `AGENTS.md` → docs map → [`worktree-runtime.md`](../../development/worktree-runtime.md) → [`e2e-up.sh`](../../../scripts/e2e-up.sh) / [`e2e-down.sh`](../../../scripts/e2e-down.sh) | 自行选择随机端口和临时 config；验证 HTTP ready、node online、bind、heartbeat；两次过强自检失败均由 trap 清理，随后通过源码和更强 evidence 修正假设 | Pass（冷启动真实 runtime） |
| 定位一次模型调用记录 | `AGENTS.md` → operations → [`llm-integration.md`](../../development/llm-integration.md) → [`evidence.md`](../../development/evidence.md) → LLM_PROXY owner/logs | 任务未提供真实 session ID，Agent 明确拒绝猜测；用既有 session 做脱敏结构验证，只输出 keys/计数/状态，不读取正文或发起模型调用 | Pass（正确保留输入边界） |
| 恢复一个中断的 active unit | `AGENTS.md` → docs map → [`changes/README.md`](../README.md) → [`feat-484 status`](../feat-484-chat-message-interactions/status.md) → live Git/PR/worktree/process/log | 没有把 status 快照当实时真相；发现未跟踪 credential/runtime、存活服务、未完成 Round 3、旧 validated range 和 `diff --check` 失败后停止，不重复派发或清理 | Pass（冷启动安全恢复） |
| 查询历史架构选择 | docs map → [`refactor-387 motivation`](../archive/refactor-387-kernel-sdk-no-http-api/motivation.md) / [`design`](../archive/refactor-387-kernel-sdk-no-http-api/design.md) → current architecture/code/tests | 找到移除 loopback Kernel HTTP 的原始理由和提交链，再用 current spec、源码和 16 个 contract tests确认今天仍采用进程内 SDK | Pass（history 未覆盖 current） |
| 完成一次 change 收尾 | workflow / changes / spec contribution / evidence → repo-local `change-*` skills → CI | 正确还原 Full/lite 门禁、delta 校正、promotion、archive、PR/CI 和恢复顺序；同时识别并行 report push、归档后门禁和最终 CI head 等流程缺口 | Pass（主链可用，漂移待裁决） |

## Agent 行为评估

| 能力 | 预期行为 | 实际观察 | 评价 |
|---|---|---|---|
| 上下文发现 | 从固定入口进入任务相关 owner | 七类任务都从根指令或其显式路由进入 docs map / canonical owner；没有靠全仓目录猜测作为唯一入口 | 符合 |
| 权威判断 | current、proposed、history、research、evidence 分工清楚 | IM 与历史任务都主动回到 current spec/代码核验；日志只被当作单次证据 | 符合 |
| 环境与安全 | 隔离运行，不污染主配置和其他实例 | runtime 使用随机端口和临时目录；主 config SHA/mtime 不变；所有自建 PID、端口和目录最终清理 | 符合 |
| 反馈与自纠错 | 失败后用证据修正，不编造成功 | runtime Agent 撤销对 state 文件和固定日志字符串的错误假设；LLM Agent 在缺 session ID 时停止具体归因 | 符合 |
| 恢复能力 | 快照只作入口，实时状态覆盖快照 | active unit Agent继续检查 branch、PR、worktree、进程、日志和 validated range，并拒绝贸然恢复 | 符合 |
| 门禁与交付 | 能还原完整收尾链，同时识别门禁是否真的闭环 | change 收尾 Agent重建正确矩阵，也发现 skills 中会让最终 head 或报告丢失的流程竞态 | 符合，暴露治理缺口 |
| 搜索纪律 | 宽搜结果不应覆盖权威路由 | 两个 Agent 的早期宽搜产生 archive 噪声；它们随后收窄范围。第一轮 IM 搜索命中验收摘要后已在无答案快照重跑 | 可接受，需保留污染记录 |

## Runtime Evidence

| Claim | Baseline | Method | Result | Locator | Limit |
|---|---|---|---|---|---|
| worktree runbook 能建立并清理真实隔离栈 | branch `codex/docs-knowledge-system-rebuild` at `4e95552a4` | 以主 Gateway config 为只读源，执行 `e2e-up.sh --wt <temp>`；检查 IM HTTP、Gateway PID/auto-bind；执行 `e2e-down.sh` 后检查 PID 与敏感临时文件 | IM `63150` ready；IM PID `11958`、Gateway PID `11974` 启动后存活，Gateway auto-bound；down 后两 PID 均不存在，PID/JWT/config/ports/credential 临时文件均移除 | 本机 `/tmp/nano-docs-validation.8UinoR` 保留 `.im.log`、`.gateway.log` 与运行数据库 | 单次本机运行；未执行真实用户消息或 LLM 调用；诊断目录不提交 Git |
| 冷启动 Agent 能独立执行同一 runbook 并清理 | branch `codex/docs-knowledge-system-rebuild` at `816d4d1dc` | Agent 自行定位 runbook；在带 EXIT trap 的受控 shell 中启动；验证 HTTP、listener、state、node/heartbeat 和主配置；配对 down 后做 PID/port/pgrep/lsof 终检 | 临时 IM `53677` / PID `25962`、Gateway PID `25976` 正常；清理后六个尝试 PID、三个端口和 `/tmp/nano-docs-cold.*` 均无残留，原有实例未受影响 | 临时目录 `/tmp/nano-docs-cold.NPhRAE` 验收后主动删除；关键结果固化在本文 | 仍未执行浏览器用户旅程或付费 LLM 调用 |

## Mechanical Evidence

- `./scripts/docs-check`：197 份受维护 Markdown、85 个必须入口，全部通过。
- `ruff check .`：passed；`ruff format --check .`：894 files already formatted。
- `pytest -m "not e2e" -n 4 --dist worksteal`：3733 passed、1 skipped；第三方 Feishu SDK 的一次非确定性
  RuntimeWarning 记录为 [`D-011`](drift-review.md#d-011全量测试偶发回收未-await-的飞书-sdk-cache-协程)。
- clean `npm ci` 后执行 `npm run test`：68 test files / 653 tests passed；依赖 audit 与 stderr 噪声分别记录为
  [`D-012`](drift-review.md#d-012前端-clean-install-报告-9-个依赖漏洞) 和
  [`D-013`](drift-review.md#d-013前端测试全绿但-stderr-噪声规模很大)，没有在本 unit 自动修复。
- `git diff --check origin/main...HEAD`：passed。
- 冷启动 architecture Agent 运行 21 个聚焦架构 contract tests；history Agent 运行 16 个 Kernel HTTP
  removal contract tests；LLM Agent 运行 2 个 mock provider/header tests，均通过。
- active unit `status.md` 的实时核对使用 `git worktree list`、本地/远端 branch HEAD 和 worktree
  `git status`，没有依据文档快照覆盖实时状态。
- 当前已知、但不应在本次迁移中自动裁决的 drift 仍只记录在
  [`drift-review.md`](drift-review.md)。

## 尚未覆盖

1. 模型日志任务没有收到真实 session ID，因此只验证了定位路径、日志结构、隐私边界和 mock header 契约；
   没有判断某次真实异常，也没有额外产生付费模型调用。
2. active unit 恢复是 2026-07-30 的只读现场快照；没有停止 `feat-484` 服务、清理 credential/runtime 文件
   或继续验收。
3. change 收尾任务只验证知识发现和流程自洽性，没有实际归档 unit、创建 PR 或 push；其发现的流程缺口
   需要用户裁决后另行修复。
4. 真栈验证覆盖进程 ready、bind/heartbeat 和清理，没有覆盖浏览器用户旅程；本次迁移没有改变产品行为。
