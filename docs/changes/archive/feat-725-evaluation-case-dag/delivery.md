# feat-725：交付恢复与最终同步

## 交付范围

2026-11-07，用户要求将此前分散的评测与 Prompt 修改分别按流程收尾。本 unit 只交付共享 DAG、GC-01/02、回放原语和四 suite 的统一查看器，不包含 bugfix-722 的最新模型可见文本。两者是独立 PR，无合入顺序依赖。

- 当前交付分支：`codex/feat-725-evaluation-case-dag`（原名 `codex/eval-agent-coordination`）。
- 原冻结提交：`0196d1ec2`，包含既有设计、独立 code review / verification / acceptance 和两项消费边界修复。
- 同步后的实现提交：`6ce39edae`；格式收尾提交：`afe85807e70e9df4b2fe24cdea89e4372e67d716`。
- `effective_base`：`db1037b96a634e9e3a24435059697fdca4ce98c7`。
- `effective_through`：`afe85807e70e9df4b2fe24cdea89e4372e67d716`；本记录提交后只有交付元数据变化，最终 head 另在 PR 中展示。

## 原门禁有效性

保留原报告的实际执行位置，不将事后冻结提交倒填成当时的 `validated_at`：原设计及静态报告记录 `6db4c258a + 当时未提交实现`，最终成果由 `0196d1ec2` 保存；原网页证据与限制仍见 acceptance.md。

| 门禁 | 本轮判断与证据 |
| --- | --- |
| Design review | retained。主干增量未改本 unit 的需求、设计、evals、参考入口或开发规则；未重新设计。 |
| Code review / verification | retained。同步后所有评测实现与 `0196d1ec2` 逐字相同。后续 11 个 Python 文件仅按仓库 ruff 规范格式化，并删除 run.py / score.py 各一个未使用导入；逐文件 AST 核对排除这两个导入后完全相同。无执行逻辑 delta，不制造新一轮 full review。 |
| Product acceptance | retained。查看器、case JSON、渲染与样式字节未变；原 Web／390px、完整材料、筛选、跨任务前置和模拟阻断证据仍适用。用户要求保留的静态预览继续运行。 |
| Canonical delta | no product spec delta。评测协议与入口已写回 evals/README、evals/ui/README 和 agent_coordination/README；不改运行时产品契约。 |

## 本轮工程验证

Node 使用 24.22.1，Python 使用主仓既有 `.venv` 的 3.12.9。下列均为工程／fixture 检查，未运行真实模型评测。

| 检查 | 结果 |
| --- | --- |
| Python DAG / adapter / score unittest | 9 passed；格式化后再次通过。 |
| `pnpm exec vitest run evals` | 8 files / 17 tests passed。 |
| `pnpm exec tsc -p evals/tsconfig.json` | passed。 |
| `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime` | passed。 |
| 全量后端 `pnpm test` | 首轮 216 files：1173 passed / 1 failed；失败是 providers.test.ts 的 `Capability inspection deadline exceeded`。相关产品实现与测试相对 main 没有改动；同一版本该文件单独复跑 3 tests passed。保留首轮失败，不改称全量一次通过，也不将未复现认定为已证明根因。 |
| Python 非 E2E | 135 passed / 28 deselected。 |
| Web 产品前端 | 113 files / 1078 tests passed；本 PR 未修改产品前端。 |
| 前端依赖审计 | `--audit-level=critical` passed，未修改依赖。 |
| docs-check、ruff check / format、diff-check | passed；最初误用系统 Python 缺 yaml，改用既有 `.venv` 后通过；新 Python 文件的两处 unused import 与格式问题已修正。 |

完整工程日志留在本机 `/Users/czj/.codex/reports/coordination-closeout-20261107/`，包含 `eval-build.log`、`eval-typecheck.log`、`eval-ios-runtime.log`、`eval-vitest.log`、`providers-targeted.log`、`eval-pytest.log`、`frontend-vitest.log` 与 `frontend-audit.log`。不提交日志、运行数据、截图或凭据。

## 未测与合入边界

- 用户已明确不再要求本轮运行真实模型评测。完整 GC-01/02 的模型效果、私有历史附件和私有 archive 的原生轨迹 E2E 不在本轮通过结论内。
- GC-01/02 的 DAG 和脚本检查不是 bugfix-722 的模型效果验收；不能因为评测工具可运行就宣称最新 Prompt 全部有效。
- unit 已完成工程交付归档；PR 与远端 CI 由本次交付继续核对，归档不代表 main 已合入。开放 PR 期间保留开发 worktree 和用户要求的静态预览；实际合入后再按仓库规则清理。
