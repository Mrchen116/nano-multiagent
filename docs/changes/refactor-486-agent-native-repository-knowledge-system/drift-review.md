# Drift Review Queue

> 临时审阅文件，不是 current spec、backlog 或开发指令。
>
> 本次文档迁移发现仓库原有资料与代码、测试或现行流程不一致时，先在这里保留证据，不自动把文档改成代码现状，也不自动把代码判成 bug。由用户审核后决定：接受当前实现并修文档、恢复原意图、建立 issue，或确认无需处理。完成裁决后删除本文件，并把结论写入对应权威位置。

## 待审核

### D-001：关键路径 E2E 清单的计数与“已有门禁”不一致

- 用户裁决：13 条用户旅程当前都对应真实测试；保留机械门禁，但只保护可以客观判断的结构关系，不把语义覆盖或真实 E2E 运行纳入常态 CI。
- 处理：计数修正为 13；`scripts/docs-check` 校验 v1 表格结构、唯一编号、非空字段、声明计数，以及每个守护测试 node id 能被 `pytest --collect-only` 收集。
- 边界：CI 不运行真实 E2E，不要求测试目录中的每个测试都登记为关键路径，也不声称机器能够判断测试是否真正覆盖旅程语义。
- 状态：Resolved；窄门禁已写入 current catalog 和文档完整性检查。

### D-002：测试 conftest 引用不可定位的 `regression.md`

- 用户裁决：archive 只保留历史来由，live 测试不依赖历史报告解释当前行为。
- 处理：删除不可定位且不提供当前增量信息的 `See regression.md §4.1`；保留 docstring 中对代理变量、`httpx` 和 `socksio` 故障机制的完整说明。
- 复核：原 `KernelApiClient` 测试虽已删除，但当前 listener HTTP 测试和 DDGS 集成检查仍会继承宿主机代理，因此该 fixture 仍有实际作用。
- 状态：Resolved；当前理由已在代码中自包含，历史报告保持冻结。

### D-003：Testing 指南高估了 contract tests 的保护范围

- 用户裁决：收回超出真实实现的机械保护承诺，不为了匹配文档增加依赖语义猜测的启发式检查。
- 处理：删除“命名、落层、marker、依赖和行数均由 contract tests 兜底”的总括声明。Worker 指南只保留作业规则，并在对应位置说明 `tests/e2e/conftest.py` 自动添加 marker；真实机械范围仍是新增测试文件的 milestone 命名禁令、新增文件 400 行上限和 E2E 路径 marker。
- 状态：Resolved。

### D-004：Claude Code tools 比较材料仍把已经实现的能力写成缺口

- 现状：原 `docs/tools-diff-cc/`（现 `docs/research/comparisons/claude-code-tools-2026-04-20/`）中 Read-Before-Write、SessionFileState 等材料记录的是旧 nano 基线；当前代码已经包含相关能力。
- 用户裁决：比较研究天然只对记录时点负责，过时不构成文档漂移。comparison 子目录统一采用 `<比较对象>-<YYYY-MM-DD>`，日期表示该组快照的截止日期；后续复查建立新的日期目录，不覆盖旧快照。
- 处理：目录已带上 2026-04-20 截止日期，子目录索引继续保留每篇页面的精确日期和 nano commit，旧正文不重写。某项今天是否仍是缺口，必须重新核对 current code/spec 后再决定是否建立 issue。
- 状态：Resolved；按用户裁决归类为冻结研究快照。

### D-005：Autocompact 设计仍把已前进的工作写成待实施

- 现状：原 `docs/kernel-diff-cc/autocompact-spec.md`（现 `docs/research/comparisons/claude-code-kernel-2026-04-20/autocompact-spec.md`）仍写 Phase 2 待实现，current code、tests 和 `docs/specs/kernel/context-persistence.md` 已经前进。
- 用户裁决：同 D-004，带时间的 comparison 是历史快照，不因 current 实现前进而改写正文。
- 处理：目录已带上 2026-04-20 截止日期并冻结。原设计中某项今天是否仍需实施，重新核对 current code/spec 后再决定是否建立 issue。
- 状态：Resolved；按用户裁决归类为冻结研究快照。

### D-006：Change review 脑暴结论没有被现行三类门禁采用

- 现状：原 `docs/brainstorms/change-review-gates.md`（现 `docs/research/brainstorms/change-review-gates.md`）的暂定结论主张一个通用 reviewer；当前流程使用 `change-verifier + change-reviewer + change-code-review`。
- 影响：Agent 可能把脑暴方案误读为仍待落地的目标流程。
- 用户决定：不处理；保留为 research 中的历史脑暴，不修改现行三类门禁，也不建立 issue。
- 状态：Resolved；流程和脑暴正文均未修改。

### D-007：生产代码注释仍指向 retired Gateway SPEC

- 现状：`src/personal_assistant/gateway/composition.py` 引用 `NodeGateway-SPEC §4.2`。
- current 替代入口：`docs/specs/gateway/routing-delivery.md` 的“重启后同一通道会话续接原内核会话”。
- 影响：从生产代码追踪约束时会进入 retired 文档。
- 处理决定：保留原注释说明的持久化原因，将文档引用改为 current spec 路径。
- 状态：Resolved。

### D-010：本地主工作树的架构审查快照是否进入仓库历史

- 用户裁决：5 份 HTML 架构审查快照全部进入 Git；它们的 dirty warning 必须保留。
- 处理：快照迁入 `docs/research/architecture-reviews/`；completed change 中对旧目录的引用同步改到新路径。
- 组织规则：目录入口只说明这类快照的用途和读取限制，不手工维护文件清单；文件名和报告正文承载时间、基线及 working-tree 状态。
- 用户决定：2026-07-25 组合 Markdown 不处理、不复制进 Git。
- 状态：Resolved；HTML 已纳入，组合 Markdown 保持本地文件。

### D-011：全量测试偶发回收未 await 的 Feishu SDK cache 协程

- 现状：`pytest -m "not e2e" -n 4` 全部通过（3733 passed、1 skipped），但一次全量运行在 `test_gateway_boundary_outbox.py::test_applied_runtime_and_boundary_survive_gateway_restart` 结束附近报告 `RuntimeWarning: coroutine 'ExpiringCache._start_clear_cron' was never awaited`。
- 来源：协程定义在当前环境的第三方 `lark_oapi/core/cache/expiring_cache.py`。`ExpiringCache.__init__`取得当前 event loop 并立即 `create_task()` 启动永久清理循环；warning 显示在 `session_keys.py:934` 只是该对象被回收时的当前位置，不能据此判定 session binding 是根因。
- 复现：目标测试单跑，以及与 Feishu worker 测试用 xdist 并跑，均通过且没有再次出现该 RuntimeWarning；当前证据只支持“测试顺序或 worker teardown 相关”，尚未得到稳定复现和完整根因。
- 影响：当前 CI 不失败，但可能掩盖 SDK import-time event-loop 任务的资源生命周期问题，并给测试日志带来非确定性噪声。
- 用户决定：本次不修改代码、依赖版本或 warning 策略，后续通过 [Issue #218](https://github.com/Mrchen116/nano-multiagent/issues/218) 稳定复现并处理。
- 状态：Deferred to Issue #218。

### D-012：前端 clean install 报告 9 个依赖漏洞

- 现状：在 `src/IM/frontend` 按 CI 顺序执行 `npm ci` 后，npm audit 报告 9 个漏洞：1 critical、6 high、2 low。
- 直接依赖：`vitest <3.2.6` 为 critical；`react-router-dom 7.0.0-pre.0–7.14.1` 与 `vite 7.0.0–7.3.3` 为 high。
- 传递依赖：`picomatch`、`postcss`、`react-router`、`ws` 为 high，`@babel/core`、`esbuild` 为 low。当前 audit 对各项都报告存在可用修复，但尚未核对升级后的兼容性、生产可达性和 advisory 适用条件。
- 影响：当前 CI 只执行 `npm ci` 和 Vitest，不会因 audit 结果失败；其中部分是开发工具依赖，但不能仅凭 “测试通过”判断风险可忽略。
- 用户决定：本次不修改 `package.json` 或 `package-lock.json`，后续通过 [Issue #219](https://github.com/Mrchen116/nano-multiagent/issues/219) 逐项审计并升级。
- 状态：Deferred to Issue #219。

### D-013：前端测试全绿但 stderr 噪声规模很大

- 现状：本机 Node `v25.8.2`、clean `npm ci` 后，Vitest 68 files / 653 tests 全部通过；第二次运行按固定模式统计到 408 条 React “not wrapped in act” warning、40 条 `user stream runtime error` 和 68 条 `--localstorage-file` warning。
- 边界：`user stream runtime error` 中一部分来自测试主动制造 404、无效游标或未 mock 的 `/im/v1/sync`；`--localstorage-file` 可能与本机 Node 25 有关，而 CI 使用 Node 20。当前只确认输出噪声，不把每条都判成产品 bug。
- 影响：大量预期/未隔离 stderr 会降低真实回归的可见度；全绿摘要无法区分测试刻意验证的错误与意外后台 runtime error。
- 用户决定：本次不修改前端测试、Vitest 配置或 warning 策略，后续通过 [Issue #217](https://github.com/Mrchen116/nano-multiagent/issues/217) 在 Node 20 下分类、治理并建立门禁。
- 状态：Deferred to Issue #217。

### D-014：架构 contract test 的名称和说明仍携带旧架构术语

- 现状：`tests/contract/test_cli_http_only_contract.py` 实际守护的是 SDK-only 架构，文件名仍是 `http_only`；`tests/contract/test_agent_sdk_boundary_contract.py` 的模块说明仍把已退役的 `agent.products` 写在 `agent.sdk` 的当前依赖层中。
- 边界：测试断言本身仍会拦截产品越界 import，并未发现由这些旧术语造成的实际边界失守。
- 影响：Agent 按文件名或模块说明寻找 current 架构门禁时，可能误以为仓库仍保留旧 HTTP/products 结构。
- 用户决定：在本 PR 内完成行为不变的术语清理。
- 已修复：测试文件重命名为 `tests/contract/test_cli_sdk_only_contract.py`，SDK 边界模块说明改为当前 `sdk → core + platform` 依赖关系，并同步 live 文档、测试、脚本中的旧测试路径。
- 状态：Resolved。

### D-015：SDK 表面契约与实际豁免、允许 import 形态没有完全对齐

- 现状：`docs/specs/kernel/sdk-boundary.md` 声称显式豁免名单逐字钉死，并列出五个 re-export；当前 `agent.sdk.__all__` 和 `test_agent_sdk_surface_guard.py` 还包含 `USER_INTERRUPT_RECOVERY_CONTENT` 这一 core-owned string re-export，current spec 未列出。
- 现状：同一 spec 写“消费者只能 import `agent.sdk`”；Gateway 两个文件在 `TYPE_CHECKING` 下使用 `from agent.sdk.kernel import Kernel`。现有 contract 只禁止 `agent.core`、`agent.platform` 和 `agent.products`，没有裁决“只能从 `agent.sdk` 根导入”还是“可以从任意 `agent.sdk.*` 子模块导入”。
- 影响：公开表面名单已经发生可验证漂移；对 SDK 子模块是否属于 public surface 也缺少一致、可机械保护的解释。
- 用户决定：`agent.sdk` 根包是产品唯一公开入口，`coding_cli` / `personal_assistant` 不得直接 import `agent.sdk.*` 子模块。
- 处理：current spec 补入 `USER_INTERRUPT_RECOVERY_CONTENT` 豁免；两处 Gateway type import 改走根包；contract test 现在机械阻止产品绕过 `agent.sdk` 根入口。
- 状态：Resolved。

### D-016：Paused `feat-444` 的 reviewer runbook 使用不存在的 Gateway 健康检查

- 用户决定：现在修正失效 runbook，不等待该 unit 恢复。
- 处理：改用 current `worktree-runtime.md` 的隔离 `e2e-up.sh` / `e2e-down.sh` 入口，以进程、IM OpenAPI、新鲜 Gateway 日志和真实消息往返组合判断可用性；明确 Gateway 没有供 reviewer 调用的 HTTP health endpoint。
- 边界：本次只修正运行入口，不重新批准暂停前的技术方案；`feat-444` 恢复实施前仍须重新 grounding 并重过 design review。
- 状态：Resolved。

### D-017：`feat-484` 的 unit 文档没有覆盖当前验收现场

- 现状：2026-07-30 冷启动恢复检查发现 unit worktree 同时存在：
  - 未跟踪的 Round 3 runner、runtime 数据、channel credential/manifest 和 Gateway state；
  - 仍存活的隔离 IM/Gateway（检查时 PID `81982` / `82006`）；
  - 空的 Round 3 evidence 目录和已经停止的 runner；
  - 嵌套 verifier worktree，HEAD 为当前 unit HEAD，但没有新的 verification 结论；
  - `git diff --check main...unit/feat-484` 报告多处历史 evidence/报告 trailing whitespace。
- 文档缺口：M2 tasks/progress 没有记录最后有效 verification 的 validated head/range、Round 3 中断现场，也未签收最后两个 fix commits。
- 其他待裁决记录：M2 退出标准表写 `F1–F4`，正文存在 `F5`；design-review 的冻结表述与后来追加 M2 的做法没有留下裁决；progress 记录 orchestrator 在 worker 403 后亲自实现，与当前 orchestrator “不写代码”边界不一致。
- 影响：新 Agent 若没有核对运行现场和实时 Git 状态，可能重复派验收、误清理现场、遗漏当前 HEAD 复验，或用宽泛 `git add -A` 暂存本机 credential。
- 待决定：由 `feat-484` owner 审核现场后，决定继续复验还是安全清理；将真实 validated range 和运行 locator 写回对应 milestone progress/evidence；另行判断 credential ignore、trailing whitespace 和历史流程偏差是否建 issue。
- 状态：Awaiting user review；本次未停止进程、清理文件、恢复 agent 或修改该 unit。

### D-018：并行 reviewer/verifier 的报告 push 存在竞态

- 原因：reviewer 与 verifier 并行从同一个 unit HEAD 产生报告 commit，并竞争推进同一个远端 unit 分支；原 orchestrator 又只读取 unit worktree 的本地 HEAD，可能看不到 verifier 已 push 的报告。
- 决定：保留并行验收和各自提交。每个验收 Agent 在普通 push 被拒绝时自行 `fetch → rebase → push`，直到自己的报告进入远端 unit 分支；Orchestrator 等两者返回后同步远端，确认本轮两份 `report_commit` 都已纳入再路由。
- 状态：Resolved；不增加报告分支、锁或固定重试状态机，Orchestrator 不替验收 Agent 提交报告。

### D-019：归档步骤曾与手工活动索引冲突

- 原因：本次重构一度要求 `docs/changes/README.md` 手工列出 active unit，并由 `docs-check` 检查索引与 `status.md`。
- 决定：用户确认活动表和 `status.md` 都没有增量信息，已经撤销这套重复维护；归档继续以 `git mv` 后的目录位置和 unit 唯一性为准。
- 状态：Resolved；无需建立 issue。

### D-020：远端 CI 全绿后再提交最终状态曾使绿色结论过期

- 原因：本次重构一度要求远端 CI 绿后再提交 archive 内的 `status.md`。
- 决定：`status.md` 制度已经撤销，CI 绿后不再产生这次纯状态提交；最终结论继续绑定 PR head。
- 状态：Resolved；无需建立 issue。

### D-021：Verifier WARNING 是否阻塞收尾的口径不一致

- 用户决定：CRITICAL 是严重阻塞，WARNING 是普通阻塞，SUGGESTION 非阻塞；只有 CRITICAL / WARNING 都为 0 时 verifier 才能 pass。
- 处理：orchestrator 统一按 verifier `verdict=fail` 进入现有 fix 流程，不增加 WARNING 豁免、接受者或额外记录字段。
- 状态：Resolved。

### D-022：`pass-with-issues` 的 acceptance bar 没有稳定输入

- 现状：`change-reviewer` 允许第三轮起由 caller 放宽 major issue 为 `pass-with-issues`；`change-orchestrator` 也允许“acceptance bar 允许”时收尾，但 reviewer 派发包没有 acceptance bar 字段，也没有规定谁、何时、依据什么授权放宽。
- 影响：同一验收结果可能因 orchestrator 临场判断得到不同路由，恢复后也无法知道当时使用了哪条 bar。
- 待决定：保持 major 默认 fail；或为人工/流程授权定义显式字段，并持久化到 report/PR。
- 状态：Awaiting user review；skills 未修改。

### D-023：验收完成后的 main rebase 没有完整的门禁失效判断

- 原因：原流程在 selected gates 和 corrected-delta 对账完成后才 rebase `origin/main`，随后直接进入 CI；§6.2.1 虽然把高风险 rebase delta 列为 full 条件，§7 的 sync gate 却没有调用 Revalidation Selection。
- 用户决定：最终 sync 前移到 corrected-delta 与 canonical spec 归并之前。rebase 后逐道判断 main 增量是否使 reviewer、verifier、code review 失效；无影响时记录 retained，局部影响时重跑对应门禁，高风险或无法说明 retained 依据时重跑所有适用门禁。
- 处理：orchestrator 在派 gate 前记录 `executed_base` 和 `validated_at`；最终 sync 后结合 main 增量、门禁后 unit 增量和最终 unit diff 逐道选择 retained 或重跑，并记录 `effective_base`、`effective_through` 与理由。归档前对收尾提交和 main 推进再做一次同样判断。
- 状态：Resolved；current spec 只在门禁对最终集成树仍然有效后校正和归并。

### D-024：部分收尾状态只存在于 orchestrator 内存

- 现状：同 issue 的 5 轮上限依赖“orchestrator 内存中的 issue 指纹表”；Full/lite 的 code-review findings 没有稳定报告文件，也没有固定保存 finding origin head、open/closed 状态、retained 理由和轮次指纹。
- 影响：跨 session 恢复后无法可靠继续轮次计数、closure diff 或 retained 判定，可能重复修复或错误放行。
- 用户决定：后续通过 [Issue #216](https://github.com/Mrchen116/nano-multiagent/issues/216) 为 `change-code-review` 建立可恢复的持久报告，并取消对 orchestrator 内存指纹表的依赖。
- 状态：Deferred to Issue #216。

### D-025：校正后 delta 的软对账缺少可恢复的执行契约

- 原因：feat-392 为防止长青 spec 与代码漂移，借鉴 OpenSpec verify 引入了 reviewer/verifier 软对账；后来流程改为 design 阶段生成 delta-spec、orchestrator 在门禁后校正时，这条旧机制被迁移到“校正后 delta”，但没有同步调整执行顺序和角色契约。
- 用户决定：保留一次校正后对账，仅由 verifier 负责，reviewer 不参与。orchestrator 提交校正结果后，verifier 从最新 unit 分支逐条核对 delta-spec 与实现、测试，在 `verification.md` 留下报告；通过后 orchestrator 再归并 canonical spec。
- 状态：Resolved；已新增 verifier `corrected-delta` 模式和三种 outcome 路由。派发只声明模式，verifier 自行发现 unit delta；报告只保留最新对账结果，不建立专属 SHA/diff-range、尝试次数或重复状态协议。历史 feat-392 决策记录保持原样。

### D-026：Codex 执行映射与当前 collaboration tool schema 漂移

- 现状：`.claude/skills/change-orchestrator/references/codex-execution-notes.md` 要求 `spawn_agent(agent_type=...)`，当前工具没有 `agent_type` 参数；模型表使用带空格的 `gpt-5.6 sol` / `gpt-5.6 Terra`，当前可用标识为连字符形式，并列出当前未暴露的 `gpt-5.3-codex-spark`。
- 影响：orchestrator 若逐字执行映射，会在派发阶段参数校验失败，或无法按文档指定模型启动 agent。
- 待决定：按当前工具 schema 更新映射，并明确模型不可用时的兼容策略；这属于运行时适配更新，不应改变 Full/lite、spec review 或三类门禁的产品流程语义。
- 状态：Awaiting user review；Codex 映射未修改。

### D-027：简化实施与零用户面 Full 的 reviewer 政策冲突

- 用户决定：简化实施不能比原流程增加门禁；它只减少实施编排成本，沿用原有门禁适用性。
- 处理：两种 Full 实施方式共用同一 selected-gates 矩阵。存在用户可观察旅程时执行 reviewer、verifier、code review；零用户面时只执行 verifier 与 code review。
- 状态：Resolved。

## 本规则建立前已经直接校正、需要复核

### D-008：Feishu channel 的操作入口

- 已改内容：operations 从“在 Gateway YAML 写 App Secret”改成由 Web IM Agent Channels 页面托管。
- 依据：当前代码与 current specs。
- Commit：`c9122e85e`。
- 用户复核：当前由 Web IM Agent Channels 页面托管 Feishu channel 配置就是期望产品行为。
- 状态：Resolved。

### D-009：CLI current spec 的旧命令和 product profile

- 已改内容：移除已不存在的 `llm-config set`、已解散 product profile 叙事，并按当前代码拆分 CLI area。
- 依据：当前 CLI 代码、测试和包边界。
- Commit：`7434a7711`。
- 用户复核：`llm-config set` 已退役；内核中的 `local_coding` product profile 叙事已由 CLI 自有装配取代。
- 状态：Resolved。
