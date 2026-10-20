# M1 实施记录

## 基线与范围

- unit 分支 `unit/feat-623`；文档基线 `e63501054`，以 `2f789f62a` 显式整合未合并 PR #371 的 `bc59dfa72`。没有自行合并依赖 PR，也没有部署生产。
- IM 可信事实与授权修改见 [IM 实施证据](im-identity-evidence.md)。主实施负责 PA 同一 Inbox 的事实投影、时序与迁移恢复，以及运行时固定指导；不改已有 custom_prompt。

## 测试策略

| 风险 | 既有保护与处置 | 实施与证据 |
|---|---|---|
| 主人身份、参与关系、真实授权与外发失效 | IM personal-sources/disclosure/agent tests，rewrite-merge 旧 role 断言，其余 keep | 见 IM 证据；可信事实统一，guard 与完整上下文分离 |
| 完整摄取、分页/附件来源、通知与消费独立 | PA inbox.test.ts keep 并扩展 | 旧实现下新增三个用例失败，恢复新实现 9/9；`/tmp/feat-623-inbox-{red,green}.log` |
| PA 观察批次与原群触发、旧未读恢复/ACK/撤销 | 普通 Global attention/global tests keep；新增 personal-attention.test.ts | PA 特有后台期限属于独立时序风险；旧实现四用例均有行为断言失败，新实现与 Inbox 共16/16；`/tmp/feat-623-attention-{red,green}.log` |
| 非主人请求审核与当前风险提示 | personal-assistant.test.ts rewrite-merge 可信准入 fixture | PA 包127/127通过；新增生命周期用例另在上述16项内 |
| 真实 DSH 下一 step steering 与 onlyIfIdle 空闲接纳 | global-inbox-native.test.ts keep 并扩展 | 真子进程、锁定 DSH、确定性模型 fixture；原及时更正与 PA 忙碌背景合并均通过。与 personal-security tests 合计7/7；`/tmp/feat-623-native.log` |
| 普通工具权限、能力目录与已有 editable prompt | personal-security.test.ts keep | 与真实 DSH fixture 同轮通过，不替代真实模型意图验收 |

新永久测试均归属现有 backend Vitest gate；无一次性验收脚本进入长期测试集。构建 `pnpm build` 已通过；PA typecheck 已通过。完整 CI、独立产品与静态门禁在最终版本继续记录。

## 冻结版本全量验证

受测实现：`f036aedd5e7bc972a413989474f166a8d49db752`（build 产物内容与该提交一致）。

- `pnpm build`、`pnpm typecheck`：通过；`/tmp/feat-623-build.log`、`/tmp/feat-623-typecheck.log`。
- `pnpm test`：106 suites / 469 tests 通过，111.59 秒；`/tmp/feat-623-backend-full.log`。
- Web `npm ci`、`npm run build`、`npm run test`：100 files / 936 tests 通过；`/tmp/feat-623-web-build.log`、`/tmp/feat-623-frontend-tests.log`。
- `npm audit --audit-level=critical`：通过（5 个已有 low）；`/tmp/feat-623-frontend-audit.log`。
- `pytest -m 'not e2e' -q`：62 passed / 31 deselected；ruff check / format：通过；`/tmp/feat-623-pytest.log`、`/tmp/feat-623-ruff.log`。
- docs-check：248 maintained Markdown sources / 67 routes 通过；`/tmp/feat-623-docs-check.log`。
- final-base 只读同步：`origin/main=e63501054`，没有新增 upstream code；PR #371 仍 open，交付保留显式依赖。

隔离真栈已按 runbook 建立，由独立产品 reviewer 记录实际模型/平台结果；上述 fixture 和自动测试不代表真实模型意图验收通过。

## 审查修复与证据保留

- R1 独立审查确认：最后观察来源在到期复核时被撤销，空批退出遗留 `waitingForIdle`，后续新有效批次不再建 timer。修复前扩展已有 ACK/revoke 用例可复现（1 failed / 6 passed），见 `/tmp/feat-623-empty-batch-red.log`。
- 修复 `5b6b2bb63`：无候选的退出路径清除等待标记；没有改变忙碌/未 ACK 时的等待语义。相关 Inbox + attention 16/16、PA build、真实 DSH 两例 2/2 通过，日志 `/tmp/feat-623-empty-batch-green.log`、`/tmp/feat-623-fix-build.log`、`/tmp/feat-623-fix-native.log`。
- 独立 R2 code review：0 存活 finding；verification：0 CRITICAL / 0 WARNING；corrected-delta：aligned。详见 unit [代码审查](../code-review.md) 与 [一致性核对](../verification.md)。
- `f036aedd5` 的完整本地 CI 对未修改部分保留；此修复按影响范围补验。真实十分钟现场保持原运行版本，不能把未重启的进程标成新 head；产品报告分别标明原验证版本与可保留结论。

## 最终门禁与交付范围

- 独立产品验收 [acceptance](../acceptance.md)：pass，16 个 Scenario 覆盖、0 新增问题。真实首批600.045秒、提前读取、普通群/明确群交办、观察语义、冒称、直接更正和飞书实际reply/reminder均有本轮证据。真实长工具跨背景期限不提交，随后模型在当前turn主动读完；idle补发由真实DSH native fixture覆盖，不混称真实模型已走该分支。
- 运行版本 `f036aedd5`；窄修复 `5b6b2bb63` 的受影响边界由独立R2和16项时序/2项native测试闭环，其余真实结论按明确范围保留。
- final sync：origin/main仍`e63501054`，无需追加代码合并；新单元三份delta按Requirement完整归并current规范，gateway个人助手索引6→8。完整unit归档；PR显式包含未合并依赖#371。
- 真实试验数据与临时脚本仅在隔离目录及`/tmp/pa623-review-evidence`，不提交凭据、运行日志、数据库或构建产物。
