# Drift Review Queue

> 临时审阅文件，不是 current spec、backlog 或开发指令。
>
> 本次文档迁移发现仓库原有资料与代码、测试或现行流程不一致时，先在这里保留证据，不自动把文档改成
> 代码现状，也不自动把代码判成 bug。由用户审核后决定：接受当前实现并修文档、恢复原意图、建立 issue，
> 或确认无需处理。完成裁决后删除本文件，并把结论写入对应权威位置。

## 待审核

### D-001：关键路径 E2E 清单的计数与“已有门禁”不一致

- 现状：`docs/development/e2e-critical-paths.md` 写“v1 必保活当前为 12 条”，表中实际有 13 行
  （1–6、8–14）。
- 现状：同页声称清单与测试 drift 时“门禁不过”，但现有 `tests/unit/test_e2e_catalog.py` 只检查隔离
  Gateway model catalog 注入，没有解析这份 Markdown 或核对表中的测试符号。
- 影响：读者会高估当前关键路径数量的准确性和机械保护程度。
- 待决定：
  1. 如果这份清单应是强约束，修正计数并在 `scripts/docs-check` 中加入表项/测试符号检查；
  2. 如果它只是人工 catalog，修正计数并收回“门禁不过”的承诺；
  3. 如果其中某行不应属于 v1，先调整清单内容，再决定检查方式。
- 状态：Awaiting user review；原文未修改。

### D-002：测试 conftest 引用不可定位的 `regression.md`

- 现状：`tests/unit/personal_assistant/conftest.py` 写 `See regression.md §4.1`，没有路径。
- 来源：该说明由 commit `5ae0ffaf9` 引入；对应内容位于
  `docs/changes/archive/refactor-372-test-suite-health/regression.md` §4.1。
- 影响：Agent 无法从代码注释稳定找到设计理由，也可能误读其他 unit 的同名报告。
- 待决定：改成完整 archive 路径；或把仍长期有效的环境约束写在测试注释中，不再依赖历史报告。
- 状态：Awaiting user review；代码未修改。

### D-003：Testing 指南高估了 contract tests 的保护范围

- 现状：`docs/development/testing.md` 声称命名、落层、marker、依赖和行数都由 `tests/contract/`
  机械兜底。
- 实际：contract tests 当前只锁定新测试命名和 400 行上限；E2E marker 由
  `tests/e2e/conftest.py` 自动添加，落层和 optional dependency 没有对应 contract。
- 影响：读者可能把人工规范误认为已有 CI 保护。
- 待决定：收回文档承诺到真实覆盖范围；或补齐希望机械保护的检查，并明确自动 marker 的实际机制。
- 状态：Awaiting user review；原文未修改。

### D-004：Claude Code tools 比较材料仍把已经实现的能力写成缺口

- 现状：原 `docs/tools-diff-cc/`（现
  `docs/research/comparisons/claude-code-tools/`）中 Read-Before-Write、SessionFileState 等材料记录的是
  旧 nano 基线；当前代码已经包含相关能力。
- 影响：旧研究如果继续靠近 current 入口，Agent 可能把历史差距当成当前缺陷。
- 待决定：迁入 research 并冻结为带基线的 snapshot；其中仍未解决的缺口是否建立 issue，需逐项审核。
- 状态：Awaiting user review；正文不重写。

### D-005：Autocompact 设计仍把已前进的工作写成待实施

- 现状：原 `docs/kernel-diff-cc/autocompact-spec.md`（现
  `docs/research/comparisons/claude-code-kernel/autocompact-spec.md`）仍写 Phase 2 待实现，current code、
  tests 和 `docs/specs/kernel/context-persistence.md` 已经前进。
- 影响：Agent 可能从历史设计启动重复实施。
- 待决定：标记为 superseded research design；若原设计中仍有未实现且期望保留的部分，再建立 issue。
- 状态：Awaiting user review；正文不重写。

### D-006：Change review 脑暴结论没有被现行三类门禁采用

- 现状：原 `docs/brainstorms/change-review-gates.md`（现
  `docs/research/brainstorms/change-review-gates.md`）的暂定结论主张一个通用 reviewer；当前流程使用
  `change-verifier + change-reviewer + change-code-review`。
- 影响：Agent 可能把脑暴方案误读为仍待落地的目标流程。
- 待决定：确认该方案已经放弃并标记 superseded；或建立 issue 继续评估，不能在本次文档整理中改流程。
- 状态：Awaiting user review；流程和脑暴正文均未修改。

### D-007：生产代码注释仍指向 retired Gateway SPEC

- 现状：`src/personal_assistant/gateway/composition.py` 引用 `NodeGateway-SPEC §4.2`。
- current 替代入口：`docs/specs/gateway/routing-delivery.md` 的“重启后同一通道会话续接原内核会话”。
- 影响：从生产代码追踪约束时会进入 retired 文档。
- 待决定：改为 current spec 路径；或把足够的“为什么”直接保留在代码注释中。
- 状态：Awaiting user review；代码未修改。

### D-010：本地主工作树的架构审查快照是否进入仓库历史

- 现状：主工作树有 5 份未跟踪 HTML 和 1 份组合 Markdown；HTML 都明确标记为 dirty snapshot，不能只靠
  commit 复现。
- 现状：`395a54b5` 与 `d33025cf` 两份报告被 completed change 引用；其余报告没有 live 引用。
- 现状：2026-07-25 组合稿有较高综合价值，但引用了主工作树尚未纳入本迁移分支的 476–483 units。
- 待决定：
  1. 只选择性提交被历史 change 引用的两份报告；
  2. 同时提交组合稿并先处理其 unit 引用；
  3. 全部保留为 local evidence，不进入 Git。
- 状态：Awaiting user review；本次只建立未来报告的 research 入口，没有复制任何既有未跟踪报告。

### D-011：全量测试偶发回收未 await 的 Feishu SDK cache 协程

- 现状：`pytest -m "not e2e" -n 4` 全部通过（3733 passed、1 skipped），但一次全量运行在
  `test_gateway_boundary_outbox.py::test_applied_runtime_and_boundary_survive_gateway_restart` 结束附近报告
  `RuntimeWarning: coroutine 'ExpiringCache._start_clear_cron' was never awaited`。
- 来源：协程定义在当前环境的第三方 `lark_oapi/core/cache/expiring_cache.py`。`ExpiringCache.__init__`
  取得当前 event loop 并立即 `create_task()` 启动永久清理循环；warning 显示在
  `session_keys.py:934` 只是该对象被回收时的当前位置，不能据此判定 session binding 是根因。
- 复现：目标测试单跑，以及与 Feishu worker 测试用 xdist 并跑，均通过且没有再次出现该 RuntimeWarning；
  当前证据只支持“测试顺序或 worker teardown 相关”，尚未得到稳定复现和完整根因。
- 影响：当前 CI 不失败，但可能掩盖 SDK import-time event-loop 任务的资源生命周期问题，并给测试日志带来
  非确定性噪声。
- 待决定：是否建立 issue，专门稳定复现并判断应由 SDK 升级、隔离 import/lifecycle，还是测试 teardown
  处理；在根因确认前不应根据偶发 warning 修改业务代码或屏蔽全部 RuntimeWarning。
- 状态：Awaiting user review；本次没有修改代码、依赖版本或 warning 策略。

### D-012：前端 clean install 报告 9 个依赖漏洞

- 现状：在 `src/IM/frontend` 按 CI 顺序执行 `npm ci` 后，npm audit 报告 9 个漏洞：
  1 critical、6 high、2 low。
- 直接依赖：`vitest <3.2.6` 为 critical；`react-router-dom 7.0.0-pre.0–7.14.1` 与
  `vite 7.0.0–7.3.3` 为 high。
- 传递依赖：`picomatch`、`postcss`、`react-router`、`ws` 为 high，`@babel/core`、`esbuild` 为 low。
  当前 audit 对各项都报告存在可用修复，但尚未核对升级后的兼容性、生产可达性和 advisory 适用条件。
- 影响：当前 CI 只执行 `npm ci` 和 Vitest，不会因 audit 结果失败；其中部分是开发工具依赖，但不能仅凭
  “测试通过”判断风险可忽略。
- 待决定：是否建立 dependency/security issue，逐项确认 advisory、生产/开发作用域和最小兼容升级；
  不应在本次文档迁移中直接运行 `npm audit fix` 改 lockfile。
- 状态：Awaiting user review；`package.json` 与 `package-lock.json` 未修改。

### D-013：前端测试全绿但 stderr 噪声规模很大

- 现状：本机 Node `v25.8.2`、clean `npm ci` 后，Vitest 68 files / 653 tests 全部通过；第二次运行按固定
  模式统计到 408 条 React “not wrapped in act” warning、40 条 `user stream runtime error` 和 68 条
  `--localstorage-file` warning。
- 边界：`user stream runtime error` 中一部分来自测试主动制造 404、无效游标或未 mock 的 `/im/v1/sync`；
  `--localstorage-file` 可能与本机 Node 25 有关，而 CI 使用 Node 20。当前只确认输出噪声，不把每条都判成
  产品 bug。
- 影响：大量预期/未隔离 stderr 会降低真实回归的可见度；全绿摘要无法区分测试刻意验证的错误与意外后台
  runtime error。
- 待决定：是否建立 test-hygiene issue，先在 CI Node 20 复现并分类，再逐步修 `act()` 生命周期、关闭
  未参与测试的 user-stream runtime，并决定哪些 stderr 应成为失败。
- 状态：Awaiting user review；本次没有修改前端测试、Vitest 配置或 warning 策略。

## 本规则建立前已经直接校正、需要复核

### D-008：Feishu channel 的操作入口

- 已改内容：operations 从“在 Gateway YAML 写 App Secret”改成由 Web IM Agent Channels 页面托管。
- 依据：当前代码与 current specs。
- Commit：`c9122e85e`。
- 待复核：确认当前实现就是期望产品行为；否则恢复原规范并为实现偏差建立 issue。

### D-009：CLI current spec 的旧命令和 product profile

- 已改内容：移除已不存在的 `llm-config set`、已解散 product profile 叙事，并按当前代码拆分 CLI area。
- 依据：当前 CLI 代码、测试和包边界。
- Commit：`7434a7711`。
- 待复核：确认这些能力确实已经退役；否则应恢复规范并为缺失实现建立 issue。
