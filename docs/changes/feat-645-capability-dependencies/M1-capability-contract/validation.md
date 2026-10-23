# M1 实施与验证记录

状态：实施中，尚未取得产品验收、静态审查和最终集成结论。

## 已完成的有限验证

执行环境：本 unit worktree，Node 24.22.1。公共契约提交 `d6f49184d`，IM 责任保护提交 `c34813147`；以下是早期分段验证记录，完整集成状态见下文。

| 范围 | 实际结果 |
|---|---|
| `packages/product-contracts/tests/capabilities.test.ts` | 新增模块前失败；实现后 6 tests 通过。Task→Cron、关闭保留 Cron、共享依赖、tool-only、Skill 选择模式、固定工具、资源缺失和图结构分别验证。 |
| `apps/im-server/tests/control.test.ts` / `task-execution.test.ts` 新场景 | 原实现 4 tests 失败：关闭前未检查 doing、pending 期间新增 doing 成功、缺依赖未拒绝、tool-only 被 Feature 拦截。实现后 4 tests 通过。 |
| IM control / task-execution / approval-configuration / personal-agent | 构建通过，4 files / 47 tests 通过，包含结构化拒绝、授权 usage 计数、未知状态失败和配置回执恢复。 |
| IM 扩大测试 | 30 files / 185 tests 首轮有 3 项失败：1 份旧 socket fixture 缺依赖，2 项 15 秒超时。夹具明确改成合法的 Heartbeat + tool-only 配置；两个超时场景串行复测通过。配置 socket 场景单跑 9.68 秒通过，没有修改其永久超时或隐藏断言。完整集成检查仍需执行。 |
| docs-check | 296 maintained Markdown sources / 67 required routes 通过。 |

公共 JSON fixtures 为 TS/Swift 共用的 17 个输入/输出样例；客户端测试直接消费同一文件，未复制 Feature 依赖表。

## 部署提示词的隔离演练

只使用 `40deea7f1:config/e2e/gateway.yaml` 的无密钥旧夹具副本。按本 unit 部署提示词保留旧有效 Feature，补齐依赖；三个测试 Agent 都保留默认开启项，将 Cron 从 false 补为 true，并补入 task_graph、memory、skill_manage 和六个 schedule 工具。模型、审批、身份、提示词与其余原字段逐项断言不变，最终静态依赖校验通过。

演练备份、准备结果与后续真实栈均在本次专属临时目录 `nano-feat645-e2e-6nVL2z`；它不是生产配置，不提交其中运行数据。实际重启后保留用户后续选择的验证已执行，见下文与 evidence/restart-choices.json。

## 首轮实施收口与集成（2026-10-24）

运行时实现提交 `ce77ecb55`，客户端实现提交 `c12f87570`；合并最新主线至 `5d03e0567`，冲突处保留主线 `reconcileRoot` 与本 unit 的 tool allowlist 检查。集成后补充前端测试所需的显式 Node 类型依赖，提交 `1ce3925a3`；此前集成构建确实因缺失 `node:fs`/`node:path` 类型失败，补齐后 production build 通过。

- Node、PA 三包构建与 47 项相关测试通过；配置恢复追加 5 项通过，覆盖 prepare 重放、pending 恢复与 release。
- Native runtime 核心与扩大回归通过对应验证；扩大 12 files / 51 tests 首轮 50 通过，唯一 model-fallback 首次 submit poll 超时，原超时单独复测 9.01 秒通过。Cron 测试保留原 admission 已落盘证据，未对 DSH 的崩溃回执窗口宣称 exactly-once。
- Web 8 files / 95 tests 通过，含公共 17 fixtures、阻止关闭、usage 延迟、拒绝保存后保留无关草稿、重复 Toast 与 focus。首次实施日志 `/tmp/feat645-web-all-final.log`；集成构建日志 `/tmp/feat645-web-integrated-build.log`。
- iOS 21 tests / 5 suites 通过（公共 17 fixtures 包含在内），最终增量 build 通过，日志 `/tmp/feat645-ios-tests-retry.log` 与 `/tmp/feat645-ios-final-build.log`。中途 testmanager 日志出现异常但实际测试最终成功，不将日志猜测当根因。
- 主线合并后 workspace build 通过；PA global-agent/input-reconciliation/usage 的 3 files / 56 tests 通过（`/tmp/feat645-merge-pa-tests.log`）。

原生可见验收仍未完成：客户端实施者和主 Agent 的 CUA Simulator 均返回 `-10005 timeoutReached`。只有测试/build 证据，尚无保护 Toggle、焦点或安全区的原生交互证据。独立产品验收不得将其视作已通过。

隔离环境采用本任务临时目录的同源静态 Web；IM `127.0.0.1:54795`、Node identity `wt-nano-feat645-e2e-6nVL2z-26600`。最初 e2e-up readiness 因主机高负载超时，但只读核验 Node 在线；随后保留原数据库/config 正常重启 Node 与 IM至合并构建，未再次执行会清空测试数据的 e2e-up。该阶段完整产品验证仍在进行，不能据服务在线认定验收完成。

## 真实 Web 自检与首轮审查修复

在 `1ce3925a3` 构建上真实登录隔离账户。Task 开启时取消 Cron 出现轻提示且保持选中；无占用关闭 Task 后，Cron 仍开启、task_graph 工具关闭；随后关 Cron，再单开 schedule_create，不会恢复 Cron。依次关闭 Intelligent UI/Memory/Skills 时，共享 skill/read 保留至最后使用者关闭。所有 Feature 关闭后单开 memory、skill_manage、task_graph、send_message 与 schedule_create 保存成功；正常 Node restart 后逐项比对 features/tools/skills/mode 完全相同，见 `evidence/restart-choices.json`。

Web 三个宽度的首次工具区测量：1440/768/390 下 before/during/after 坐标及高度均一致；浮层 13px/400/fixed。768px 首次浮层右边缘缺少 16px 留白，因此初次截图仅作失败复现，修复 width=max-content 后需重新截图验收。后续复验已用最新构建覆盖 `evidence/web-toast-*.png` 与 geometry。1440/768/390 三宽度的 before/during/after 坐标和高度完全一致；右边缘分别为 1381.29/752/374，均至少保留 16px。

独立 code review `5d03e0567^2..1ce3925a3` 返回 2 项 CONFIRMED，原报告保留于 `code-review.json`。

- 配置 prepare 提前污染分区恢复快照：新增回归先失败，修复为 prepare 仅建立可信路由，只有 effective apply 更新恢复配置；新 PA 成功 apply 后报告 availability。Node 分区 7 tests 通过。
- 两端忽略命名 Skill 的关闭预检：Web 新回归先失败；Web/Swift 都按有效 Skill 选择计算差集并检查 usage；Web 2 files / 26 tests 通过，Swift 窄复验进行中。

另外，真实自检发现 Intelligent UI 的旧说明仍声称关后只能文字回复，已改成关闭额外卡片指导、消息工具仍可发卡片，避免与本次已确认原则冲突。

## 修复后冻结构建与本地 CI

产品代码冻结于 `9802c9347`；`850e6cd82` 只补测试夹具类型。Web 完整 TypeScript + Vite build 通过（`/tmp/feat645-web-review-build.log`），Node 三包构建通过（`/tmp/feat645-node-review-build.log`）。独立 code-review closure 对两项历史发现返回空数组，报告保留于 `code-review-closure.json`；Swift 新增回归编译成功但测试运行结果仍待返回。

同源 IM 运行该 worktree 构建；正常重启 Node 到该构建后，专属 state 显示 ready/connected，PID 51963 / runtime PID 52014。独立产品验收的 validated_at 为 `850e6cd82`。

- Python `pytest -m "not e2e" -q`：65 passed / 31 deselected（`/tmp/feat645-pytest.log`）。
- Ruff check 通过；format check 发现本 unit 新增导入边界集合未分行，按 formatter 修正后 85 files 已格式化。
- npm audit critical 门禁通过；仍报告 5 low / 2 moderate / 1 high，未擅自升级无关依赖。
- 用户于 2026-10-24 00:52 明确允许本机负担大时改为 PR 远端 CI。已停止本任务 full native/frontend、release build 与等待中的 Swift test，将完整门禁交给远端；分包编译已结束但 release 构建被取消，不能记全量 build 通过。先前 broad native 尝试有多项超时；高负载是观测事实，且最后一轮命令实际使用了 shell Node 25.8.2，不能视为要求的 Node 24 CI。远端 workflow 固定 Node 24.22.1。

独立产品 reviewer 后续已通过 CUA 访问专属 Simulator，原生可见入口恢复可用，继续实际交互验收；此前 timeout 仅为当时的观测，不再认定持续阻塞。
