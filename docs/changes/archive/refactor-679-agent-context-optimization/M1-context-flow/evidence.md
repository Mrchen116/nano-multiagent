# M1 implementation and validation evidence

This is the caller's actual implementation/validation record, not a reconstructed worker log. Product acceptance and independent static decisions remain in their own reports.

## Source and scope

- Baseline: `4b27d962c1cc09a27a567619bd5cabc3db2ee934`, migrated from current Memory `unit/feat-676` at `c2a7fe3c3727db2c557a28915fda6ccee5e4298e`.
- Inherited implementation saved without loss as `4dda5de90`; owner-workspace Memory and native request fixture fixes in `b610b02b5`.
- `36cef9604` fixes typed `task.context.sync.result` correlation across the real Channels transport.
- `6dc940cf6` fixes transactionally persisted Task deletion notices, PA source synchronization before native Memory assembly, and running Schedule repair at the next native step. Gate 2 Round 6 approves the assembly timing adjustment.
- `6881952b9` gives current members a locatable revocation message while retaining the same-ID minimal projection for the lost source. Gate 2 Round 7 clarifies that historical revocation does not override later verified access; restored access does not resume paused work.
- Final destination remains `unit/feat-676`. No production deployment or production testing is included.

## Actual checks

All Node commands used v24.22.1. Python tools used the main checkout's existing `.venv`. Log locators are ignored local files under `output/refactor-679/`; they are evidence, not committed runtime data.

| Check | Command/scope | Actual result and locator |
|---|---|---|
| Owner workspace | `memory-documents.test.ts`, `memory-workspace-native.test.ts` | 8 pass; `recovery-fix.log` (later wire failures in that mixed log are superseded below) |
| Provider request | `context-revalidation-provider.test.ts` | 2 pass; document/current window reset and explicit legacy/native summary, actual HTTP Anthropic requests; `recovery-wire.log` |
| Preserved provider capture | Temporary exact test copy with only a `finally` JSON write, removed after checking byte equivalence | 2 pass; `provider-capture.log`, `provider-wire-DOCUMENT.json` (3 requests), `provider-wire-LEGACY.json` (4 requests, including summary). Actual HTTP serialization with controlled responses; not a real upstream-model payload claim. |
| Initial runtime regression | `pnpm exec vitest run --maxWorkers=3` | 175 files / 938 tests pass; 6 tests fail under concurrent load; `full-tests.log`. This is not represented as an all-green run. |
| Final runtime regression | `pnpm exec vitest run --maxWorkers=2` | 180 files / 949 tests pass; the new visible-revocation red test was collected while its fix was being developed and was the sole failure; `final-runtime-tests.log`. Its final implementation is validated by the 53-test run below. |
| Failed-file recheck | `history.test.ts`, Node `lifecycle.test.ts`, `agent-context-default.test.ts`, `model-setup.test.ts`, `global-child-tools.test.ts`, `task-execution-limits.test.ts`, `--maxWorkers=1` | 5 files / 12 tests pass; one transient child diagnostic in `global-child-tools` instead of events; `full-timeout-recheck.log`. Both child cases pass in the subsequent focused run below. |
| Channels regression | `packages/channels/tests/web-relay.test.ts` | 16 pass; prior missing reply mapping failed its bounded response deadline; `task-sync-green.log` |
| Source/Task fixes | Exact command below | 8 files / 41 tests pass; `final-fix-focused.log` |
| Deletion notices red | IM `task-execution.test.ts -t 'publishes one original deletion'` | Root/subtree deletion persisted no notice before fix; `task-delete-red.log` |
| Running repair | `task-reminder-batch.test.ts`, `global-child-tools.test.ts`, `--maxWorkers=1` | 2 files / 4 tests pass; `repair-child-focus.log`. Running repair captures actual next native model input containing the stable repair ID, task title, reason and exactly one Task package. |
| Existing repair/stop/child matrix | `task-reminder-batch.test.ts`, `schedule-deletion-native.test.ts`, `task-execution.test.ts` | 18 pass plus the new fixture failed because its allowlist omitted Task; `running-repair-green.log`. Corrected fixture passes above; the file name does not imply the earlier run was all green. |
| Visible revocation | IM `task-context-revocations`, `task-context-live`, `task-context-migration`, `task-execution`, `identity`, `e2e/conversation-tasks`, `--maxWorkers=1` | 6 files / 53 tests pass; `visible-revocation-green.log`. The new test fails before the fix (`visible-revocation-red.log`) and proves current members see the affected Agent/Task, while the same-ID lost-source relay and sync contain only the minimal fact. |
| Revocation wording and ingestion | PA `inbox.test.ts`, `task-context.test.ts`, `--maxWorkers=1` | 2 files / 18 tests pass; `eligibility-tests.log`. Actual restored-access model behavior remains a product acceptance check. |
| TypeScript build/typecheck | `pnpm build`; `pnpm typecheck` | Passed at `6dc940cf6`; `final-build.log`, `final-typecheck.log` |
| Shared iOS runtime | `pnpm check:ios-runtime` | Passed; `ios-runtime.log`. No native iOS source change; full simulator/archive not required. |
| Web regression | `npm --prefix src/IM/frontend run test -- --maxWorkers=2` | 108 files / 1,031 tests pass; `frontend-tests.log` |
| Web dependency audit | `npm --prefix src/IM/frontend audit --audit-level=critical` | Exit 0, no critical finding; 11 existing lower-severity advisories (4 low, 2 moderate, 5 high); `frontend-audit.log` |
| Python architecture/helpers | `pytest -m 'not e2e' -q` | 127 pass, 28 deselected; `python-tests.log` |
| Python formatting | `ruff check .`; `ruff format --check .` | Passed, 97 files formatted; `ruff-check.log`, `ruff-format.log` |
| Documentation | `./scripts/docs-check` | 292 maintained sources / 68 required routes pass before final archive; `docs-check-current.log` |

The eight-file source/Task regression command was:

```sh
pnpm exec vitest run \
  apps/im-server/tests/task-execution.test.ts \
  apps/im-server/tests/task-notifications.test.ts \
  apps/node/tests/global-inbox-native.test.ts \
  packages/dsh-integration/tests/task-context-originals.test.ts \
  packages/dsh-integration/tests/task-context-sync.test.ts \
  packages/dsh-integration/tests/context-order-provider.test.ts \
  packages/dsh-integration/tests/context-revalidation-provider.test.ts \
  packages/dsh-integration/tests/memory-child-runtime.test.ts --maxWorkers=1
```

It covers same-step PA generation/invalidation with no unread messages, claimed-input revocation, outage/stop/restart recovery, environment/catalog ordering, real window/summary request serialization, and same-child source invalidation. It ran before the one-line running-repair adjustment; the latter has the focused evidence above. Tests use controlled model transport unless explicitly identified as real-model product acceptance.

## Real stack and behavior boundary

The fixed daily stack is `/tmp/nano-refactor679-daily/.e2e-daily.json`, `http://127.0.0.1:64012`, node `wt-nano-refactor679-daily-89152`. P/E/Q use `gpt-6.1-sol high`, PA uses `gpt-6-astra medium`, with the normal Codex review path. The managed Node and isolated IM were restarted at `6dc940cf6` and `6881952b9`, preserving identity/data; process and health evidence is in `daily-final-restart.log` and `daily-eligibility-restart.log`. Independent browser actions, real model requests, source exclusion, notices and fixed-chat deliveries are recorded in `../acceptance.md`.

Mechanism tests establish deterministic boundaries; they do not establish model reliability for every branch. The representative actual model scenarios and any unrun/failed branches must remain explicit in acceptance. No service-health result is substituted for product behavior.

## Final documentation and lifecycle closure

Independent code review is `[]`; verification and corrected-delta are PASS/aligned at `6881952b9`, with R1–R6 product PASS and all five observed findings closed. The destination was fetched again and remains `unit/feat-676` at `c2a7fe3c3`; no source sync was needed. The three audited deltas were merged by exact Requirement name, the Gateway index counts were refreshed, and the entire unit was moved to archive with relative links migrated. These documentation-only changes retain the frozen gates. Final `scripts/docs-check` passed (283 maintained Markdown sources / 68 required routes); `scripts/check_change_unit_archived.py --head-ref codex/refactor-679-on-memory` and staged/unstaged `git diff --check` passed. Exact comparison confirms all seven merged Requirement blocks match the audited deltas.

The isolated daily stack was stopped via `scripts/e2e-down.sh --wt /tmp/nano-refactor679-daily`; no listener remains on port 64012 and its IM/Node/runtime PIDs are gone (`daily-shutdown.log`). Ignored local evidence is preserved at `/tmp/nano-refactor679-daily/evidence/` before disposable worktree cleanup. No production process or data was changed.

## 用户验收增量（2026-10-31）

- 实现基线：Memory `5e5d3fcc801c6ad766910b126a10ee25076627a9`；本轮实现：`326dac00ed5d78daaa6464032a94a24daba5d794`。本轮继续 refactor-679，不建立第二个 unit。旧证据保留，以下仅覆盖用户指出的身份、窗口名称、Task 限制相关性、关键记忆包装和 Dreaming 前后台能力。
- 自有插件：`dsh-agent-context@0.3.0-rc.7`，tag/source `00f61960a6a81078cb9102347a277aa9147fe30b`。首窗/换窗删除错误名称行；窗口导航和原生 runtime snapshot 不变。`pnpm test` 9 文件 / 32 测试、`pnpm typecheck` 均通过。固定 release tarball 匿名下载后与本次测试包 `cmp` 相同；SHA256 `e3409381a9cd77546093dcd5cd133021347d6cc650c8bddfdb20a555442848c2`，依赖锁使用 release URL 及 SHA512。最终 `pnpm install --frozen-lockfile` 成功；锁中 SHA512 与下载包一致。重新安装后的真实 HTTP 首轮/恢复/改名测试再次通过（`/tmp/refactor679-release-install-native.log`）。

### 有意义的失败与修复

- 初始上下文回归先复现无对象 Task 同步失败仍追加提醒、缺身份、Memory 来源包装/缺工具噪声；修改后相关原生 provider、child、恢复用例通过。
- 自动 Dreaming 用例复现前台缺少写/维护工具时无法启动。移除启动检查后又定位到配置层 Feature 依赖声明拒绝开启；同步消除该错误前台依赖及历史特殊豁免。测试明确断言配置 `effective:true`、前台无 write/edit/memory_maintenance、后台真实执行与最终保存回执。
- 中间测试 fixture 使用其他 Feature 的隐式默认依赖，曾令自动用例配置仍失败；关闭不相关 Feature 后最终 Dreaming 6 用例通过。前端旧 fixture 将前台工具声明为 Dreaming 必需工具；按新产品契约分开独立工具目录/选择后，原设置页全部28用例通过。没有以修改断言跳过真实保存或授权边界。

### 最终验证

| 命令/范围 | 结果与本地完整日志 |
|---|---|
| `pnpm exec vitest run --maxWorkers=2` | **181 文件 / 953 测试通过**；`/tmp/refactor679-followup-full-tests.log` |
| `pnpm -r build`（最终 release 锁安装后） | **通过**；`/tmp/refactor679-followup-final-build.log` |
| `pnpm -r typecheck` | **通过**；`/tmp/refactor679-followup-typecheck.log` |
| Web `npm test -- --maxWorkers=2` + 受影响 fixture 定向复验 | 全量107文件/1030项通过，1项旧fixture失败；校正后受影响文件28项全部通过；`/tmp/refactor679-followup-frontend.log`、`/tmp/refactor679-followup-frontend-fix.log`。远端 CI 将再次验证最终完整树 |
| `pytest -m 'not e2e' -q` | **127 passed / 28 deselected**；`/tmp/refactor679-followup-python.log` |
| `pnpm check:ios-runtime` | **通过**；`/tmp/refactor679-followup-ios-runtime.log`；本轮无 iOS 原生源变更 |
| `ruff check .` / `ruff format --check .` | **通过**；`/tmp/refactor679-followup-ruff.log` |
| `./scripts/docs-check`（归档前） | **294 maintained sources / 68 required routes 通过**；`/tmp/refactor679-followup-docs.log`；归档后另复核 |

### 真模型完整输入与行为

固定 daily 独立环境 `/tmp/nano-refactor679-context`（IM `http://127.0.0.1:51966`，Node `wt-nano-refactor679-context-32788`），源码与实现提交一致。Global `daily-product` 使用 `codexOAuth:gpt-6.1-sol/high`；PA `pa_3e16eef0a4b1` 使用 `codexOAuth:gpt-6-astra/medium`。真实客户端 API 发起用户请求，模型真实运行并确认公开/主人私聊送达；没有用受控响应替代该行为。

完整首次 `llm/request` header + context + messages 在 `output/refactor-679-followup/{global,pa}-initial-full.json`，可读正文及完整 tools 各有导出；Global session `c1413933-2d32-4574-8388-53c93d346fd3`，PA session `cbb7f3b2-dc1e-4e2a-b0e4-aab22026de9d`。这是 native 请求事件观测，未冒充实际上游 HTTP 抓包；adapter 序列化另有真实 HTTP fixture 回归。

根 Agent 逐段核读 Global 完整系统指导、PA 所有差异段、两者 runtime/Skill/唤醒与工具目录；独立产品 reviewer 核完整输入和交付。PA 首次模板 basis generation0 与首次来源同步 generation1 不同，按保留的来源保护暂不展示待核对正文；后续通过正式 Dreaming 完成保存，`pa-valid-memory-snapshot.txt` 展示绝对文件路径、完整一页关键记忆、详细页导航及当前来源代际。不能将首次失效分支记成有效正文通过；有效分支另由该后续请求证明。详细判据与交付消息见本轮 `acceptance.md`。

旧用户预览 `/tmp/nano-refactor679-daily:64012` 保留；新预览也保留供查看完整轨迹。均为隔离测试环境，没有部署生产或向生产发送消息。当前 worktree 提供两套保留预览的运行文件，结束时如仍保留，应明确报告生命周期原因。

## 消费者接口修正与默认测试能力（2026-10-31，第二轮用户反馈）

- 实现版本：`81bff879b`；真实启动接口修正：`0718cbd3b`，基线 Memory `2724ea8d1`。Round 9 增量设计 Approved。工作 Agent 与审批器使用各自可见接口；前台直接读取当前正式记忆，后台冻结/发布继续校验来源与版本；公开维护状态不暴露内部调度状态。
- Red：`pnpm exec vitest run packages/dsh-integration/tests/memory-documents.test.ts --maxWorkers=1` 得到 3 个当前正文被错误隐藏的失败（首次来源准备、普通文件变更、来源集变化）；`/tmp/refactor679-consumer-red.log`。新增通用测试默认工具同步在尚无实现时两例失败，`/tmp/refactor679-bootstrap-red.log`。
- Green：当前文档、root/child 原生记忆请求、真实 HTTP provider 请求共 4 文件 / 12 测试通过（`/tmp/refactor679-consumer-focused.log` 中另外 6 个旧 status fixture 因再次打开已打开 domain 失败，未归为产品通过）。改从实际持久文件读取后台进度后，Dreaming 终止/失败/不写入、恢复、审批来源、审批提示和 Node 原生 PA 来源准备共 5 文件 / 41 测试通过：`/tmp/refactor679-consumer-regression.log`。保护了失败不推进、成功推进、前台不可直接修改正式记忆与审批私有协议不变。
- `python -m pytest tests/unit/test_e2e_catalog.py tests/unit/test_e2e_daily.py -q`：10 passed。覆盖动态新 default_on、固定工具、已开 Feature 依赖、默认关闭选择、已有额外选择和显式替代配置。
- 真实 daily 首次启动发现 bootstrap PATCH 没有完整配置，真实 API 返回 422，独立 code reviewer 同时复现。`0718cbd3b` 使用已 GET 的完整 current 配置合并工具选择；补保留名称、群策略、提示和模型断言。失败日志 `/tmp/refactor679-consumer-bootstrap-422.log` 保留。按 e2e-down 关闭仅本轮失败栈后重起成功；`/tmp/refactor679-consumer-up.log`、`/tmp/nano-refactor679-consumer/.e2e-daily.json`。
- 新栈 `http://127.0.0.1:58220`，P/E/Q `codexOAuth:gpt-6.1-sol/high`，PA `codexOAuth:gpt-6-astra/medium`，审批 `codexOAuth:gpt-6-luna`；P/E/Q 各 37 个持久工具选择。PA 沿真实产品创建，固定工具由宿主加入；以 allowlist 与 fixed_tools 合集核对产品默认目录，四者缺失均为空，证据 `output/refactor-679-consumer/default-tools.json`。最终实际模型工具由产品验收核对，不能仅以配置声明代替。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime` 通过；`pytest -m "not e2e" -q`：129 passed / 28 deselected；ruff check 与 format：97 文件通过；当前 docs-check：295 Markdown / 68 routes。日志 `/tmp/refactor679-consumer-{full-build,typecheck,ios,python-all,ruff,docs}.log`。前端源码和锁未修改，前轮完整 Web 验证保留，远端最终完整 CI 仍为交付门禁。
- 用户明确接受的例外：DSH jobs 插件已加载而工具被人为白名单隐藏时仍有相关指导，本轮不改 jobs/bash/工具过滤或后台执行行为；保留 `Use read/glob/grep for memory files`。不能把正常默认配置通过概括为任意受限配置都无错配。
- 最终完整 Native：`pnpm exec vitest run --maxWorkers=2`，181 文件 / 954 测试通过，345.86 秒；`/tmp/refactor679-consumer-full-tests.log`。没有用定向通过替代本次全量。
- 新 daily 真实首轮：Global `97e406fe-2a9c-4e35-809f-1a67f81e02e8`，PA `54f70a6a-b492-4cff-a8a8-fad495f1aecb`，实际工具分别 37 / 39，均有 glob/grep/job_output/job_kill。root 全文审读 initial messages、全部 tool schemas 与动态加载内容；首次 MEMORY.md 正文均直接可用，实际 Global 完成 glob/grep/read 并送回原群，PA 只在主人私聊完成整理状态与更正回复。
- PA seq47 完成 Dreaming，seq50 新正文进入下一上下文，seq53 status 只含来源待核对、显式停用、路径级保存/版本回执及 active/backlog/reviews；2 页 saved/versionRecorded。后续更正 seq97 登记停止采用，seq100 约束进入实际上下文，PA 未启动新整理/写正式文件且按新截止时间排序，不谎报持久更正。实际正文、请求、返回、截图均在 `output/refactor-679-consumer/`；来源为原生实际请求记录，不冒充上游 HTTP 抓包。
- Root 在实际加载的 Skill 全文发现残留 memoryRoot/profile、前台 checkpoint 和旧逐 step 说法，产品 reviewer 记 consumer-1 C1 未通过。`5fcb9b18a` 只修 7 行 Skill 文本；managed 重启本轮 Node 后安装内容逐字匹配。实际 seq128 重载全文、seq133 查询 status、seq138 送达新状态说明、seq143 completed，consumer-2 C1 closed / PASS。旧历史中的先前 Skill 原文保留，不伪造历史全无旧词；最终检查的是本次真正重载的当前说明及其后续消费。证据 `pa-reloaded-skill.txt`、`pa-skill-reload-full.json`、`pa-skill-reload.png`。既有行为与完整门禁 retained，不因 7 行文案机械重跑整套测试。
- 本轮无生产操作。先前两个用户预览保持原样；本轮预览保留实际记录，当前 worktree 继续为预览的源码及运行路径 owner。

### PR #436 CI 的停止用例校正

- CI run `41196290600` 的 Native 回归为 953 passed / 1 failed：`task-execution.test.ts` 的 confirmed-stop 场景要求停止通知出现至少两次 `agent/inbox/spliced` 插入事件，实际只有一次，轮询超时。失败摘录保留在 `/tmp/refactor679-consumer-ci-failure.txt`；前端、构建和类型检查通过，后端余下步骤因该失败跳过。
- 未修改用例的本地定向复现通过（4.07 秒，`/tmp/refactor679-ci-stop-repro.log`）。因此没有把未复现当作已确定 CI 的具体调度交错或运行时缺陷已修复。该断言依赖内部入队/重新入队次数，本身不是停止和通知保留的产品契约。
- 仅将该等待改为实际 session 回到 idle，并立即断言无模型请求；保留解除 fence 后仍安静、新外部输入后首个实际模型请求包含停止通知、原 Schedule 与排队人类输入仍可用、旧 doing Task 不复活等原有行为断言。没有修改产品运行时或放宽超时。
- 校正后同文件 13/13 测试通过（17.93 秒，`/tmp/refactor679-ci-stop-regression.log`）。既有 954 项本地全量和真实 Global/PA 证据仍适用于未改的产品代码；远端须在最终提交重新完成整套 CI，不能将首轮失败改记成功。

## 2026-11-01 子执行与自然语言遗忘增量

- 基线 `origin/unit/feat-676@8c9d34780`，分支 `codex/refactor-679-child-context`。实现 `3ddcf506a`；source_history 外显修正 `2b1582620`；SingleThread 普通子与 Task summary 头修正 `fea88c187`；最终 `dfdfbd66b` 仅调整轨迹恢复测试的非持久表示比较。原先预览保留；本轮新建 `/tmp/nano-refactor679-child`，不涉及生产。
- 永久 `fork-prefix-provider.test.ts` 捕获真实 DSH 发往 Anthropic HTTP provider 的完整 body，比较 system、tools 与历史前缀；覆盖 Global、PA、SingleThread 的空历史、有历史和根进程重启后 fork。仅归一 provider 缓存提示与等价单文本表示；模拟 SSE 不充当实际缓存证据。初次 Global/PA 工具差异红测见 `/tmp/refactor679-prefix-red.log`，初修通过 `/tmp/refactor679-prefix-green.log`；扩展三角色在 `/tmp/refactor679-singlethread-green2.log` 通过。既有 `task-child-context` 继续覆盖 fork 自身冷恢复，ordinary child 冷恢复保留内部工具。
- 首轮窄回归 35 passed / 2 failed：两项旧断言仍要求隐藏 fork 历史和由绕过 GlobalAgent 的 stub 拒绝公开发信。修订为保留真实历史并通过真实 GlobalAgent 宿主入口检查权限后 2/2 通过，`/tmp/refactor679-child-focused.log`、`/tmp/refactor679-child-rerun.log`。额外前缀/来源 17 项通过，`/tmp/refactor679-child-final-focused.log`。
- 独立审查找出 source_history 返回范围、SingleThread 根交付继承和 Task summary 头三处消费遗漏，均先由实际 seam 新断言失败、修正后复验。`/tmp/refactor679-history-range-{red,green}.log`（最终 3/3）；`/tmp/refactor679-singlethread-red.log`；`/tmp/refactor679-summary-fields-red.log`；`/tmp/refactor679-final-patch-green.log`（ordinary/fork 三角色及 Dreaming task 10/10）。SingleThread 首次试验将根工具移至 local scope，不满足既有可选工具选择契约，已撤销且未提交；最终保留根 preset 路径，只收窄普通子的本地 send 参数与继承视图。
- 本轮首次全量在补入尚未修复的 source_history 新断言时得到 956 passed / 1 failed，随后最窄验证关闭该红测。冻结 `fea88c187` 后完整回归为 958 passed / 1 failed（182 files），`/tmp/refactor679-final-full-tests.log`；失败仅为自动 Dreaming 的 warm/cold viewer 全对象比较：live assistantStream.revision=20、缺省 delegationDepth 与 cold revision=0、depth=0 不同，records/projections 等持久内容相同。原样单跑通过 `/tmp/refactor679-auto-dreaming-repro.log`，不将其当作具体调度时序已查明。公开 DSH 类型注明 stream revision 为进程局部，JSONL 物化缺省深度；`dfdfbd66b` 仅归一这两项表示，仍比较全部持久内容与 activeAttempt 等其余字段。Dreaming/runtime/trajectory/knowledge-review 共 13/13 通过 `/tmp/refactor679-trajectory-green.log`；独立静态核验认可。远端完整 CI 仍是交付门禁，不能称本地初次全绿。
- `pnpm build`、增量 dsh-integration build、最终 `pnpm typecheck`、`pnpm check:ios-runtime` 通过；Python `pytest -m 'not e2e' -q` 129 passed / 28 deselected；ruff check/format 97 files 通过。日志 `/tmp/refactor679-child-full-build.log`、`/tmp/refactor679-final-patch-build.log`、`/tmp/refactor679-final-typecheck.log`、`/tmp/refactor679-child-{ios,python,ruff}.log`。未改前端，前轮有效 Web 门禁保留，远端 CI 再跑完整前端。
- 本轮透明 HTTP capture 仅修改隔离 Node 的代理入口，原模型服务未改。完整 provider body/SSE 位于本地 `output/refactor-679-child-live/wire/`，不记录认证头、不提交产物。Global root `da629f2f-4479-46fe-a885-35ab29764d5d` 37 tools，普通子 `f9b8520a-ba6f-4e9b-8d19-b823154269b9` 33；PA root `255d6513-5ada-46ac-9eb4-884626f9d41b` 39，普通子 `53e69ef5-7afd-44ad-b9d2-8fcb56eb3ed4` 33。普通子不含父公开 Persona，只有 native 内部 send 参数，去掉无权产品工具；可读当前 MEMORY.md。
- Global fork `35704db3-2384-4c5a-8554-503dbb3692b3`（wire0033）与 PA fork `c2aaedbd-14b3-4bf1-be50-86096107d9f9`（0048）实际 system/tools 完全相等，继承消息前缀分别 10/24 条；返回 `cache_read_input_tokens` 分别 15,744 / 19,968，未缓存输入分别 889 / 1,100。完整对比见 `global-prefix-cache-comparison.json`、`pa-fork-prefix-comparison.json`，是实际 provider 返回，非模拟。Global 首个 fork 没有本轮尚未完成的普通子原文，诚实返回不足；父补齐原文后第二 fork 成功，最终群消息 `3f5f26b6cf274f37b256bb3edc92c095` 三行交付。不能声称第一次就拿到当前未完成轮的全部历史。
- PA 原始聊天驱动遗忘：先用 Dreaming 保存两条虚构偏好；仅本轮例外后的整理保留长期偏好；忘掉请求 `b0c8e10b...` 后 seq161 先真实发送“立即停用、文件尚未改”的答复，seq165 只调用 run，Dreaming `6ef6fd38...` 实际 3/3 保存/版本记录；seq179/180 读回正文与入口已去掉上午偏好、保留结论优先，seq185 公开确认。全程只有 status/run，没有 exclude 或持久名单。完整 `pa-native.jsonl` 与 reviewer `pa-*` 产物可复核。
- source_history 的模型可见工具返回另以现有真实 DSH task-runtime fixture 留存：`source-history-runtime-requests.jsonl`、`source-history-runtime-results.json`；`allowed_range` 只有 session_id、purpose、available_before，原始证据 item 仍可读。`/tmp/refactor679-sourcehistory-proof.log` 1 passed / 6 skipped。它是确定性 LLM/source fixture 的真实工具机制证据，自然模型未自主调用该工具，不能混称自然实跑覆盖。
- canonical Agent Capabilities / Personal Agent 已归并自然语言遗忘与两项新增上下文契约，capabilities requirement 数为 61。重开时损坏的 131 个历史链接已修复；退役 context-visibility.ts 两处历史证据指向原基线永久链接。active docs-check 295 maintained / 68 routes 通过，归档后再验。
- 最终产品定向 closure `child-forget-2` PASS：运行实现 `fea88c187`，新普通子 `6d54c2c5...` 后主 seq220 请求整理，wire0090 提炼、0091 整合；新版 Task summary 头仅 `Source session_id`，没有新注入 root/events/version。Dreaming `02b34...` completed，2/2 保存及版本记录、一份子复盘 integrated；公开 `14a13...` sent，Chrome 1230×816 实际显示完整回报。`pa-closure-delivery.png` 与 acceptance 最终 round。旧 wire0053 的失败保留，不能把历史输入重写成新版。
- 最终独立 code review `[]`、verifier PASS、corrected-delta aligned，V-CHILD-FINAL-1 CLOSED。验收后仅关闭本轮 `/tmp/nano-refactor679-child` 的 Node/IM 和透明捕获代理（端口 63958/64178 已停止监听）；旧 daily/context/consumer 三个预览保留，本工作区仍为其源码/运行路径 owner，合入后不能删除。

### 2026-11-01 PR #437 首轮 CI 的测试时序修正

- 首轮远端 CI（run `41223146002`、head `426cfe2e3`）为 181 files passed / 1 failed，958 tests passed / 1 failed；前端通过，构建/类型/iOS runtime 通过。唯一失败是 `context-revalidation-provider.test.ts` document cell 期望 2 次请求却收到 3 次。保留该失败，不称首次全绿。
- 完整事件显示 `session.ensure` 发起的异步 `TaskExecutionDriver.poke` 先消费夹具提前发布的可执行 Task，自动 turn 1 调用两次模型；人工输入随后进入 turn 2，再调用一次。现有测试在 `session.submit` 前设置 `armed=true`，引入了不属于本场景的启动竞争。原样窄跑 2/2 通过（`/tmp/refactor679-ci-context-before.log`）不能否定该竞争；临时在人工提交前等待首请求后，精确复现相同 3 次请求失败（`/tmp/refactor679-ci-context-race-red.log`），随后移除临时调度。
- 仅修夹具：在人工轮的 `product.task_context.prepare` 读取待消费原文时才启用 Task；保持原有 2 次请求、工具实际消费、来源及压缩后完整上下文断言，另增首请求包含人工输入断言。产品源码不变。窄测 2/2 通过（`/tmp/refactor679-ci-context-green.log`）；连同 Global/PA/SingleThread fork provider 前缀回归共 5/5 通过（`/tmp/refactor679-ci-context-and-fork.log`）。后续远端完整 CI 独立判定。
