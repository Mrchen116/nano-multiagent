# bugfix-722：交付记录

## 恢复与最终范围

本 unit 按 `change-fast-close` 对已有实现和用户确认做事后收尾，不重做事前流程。原文、用户接受的限制和复审触发条件保留在 fix.md；设计和独立审查分别见 design.md / code-review.md。

- 分支：`codex/bugfix-722-global-delegation`。
- `executed_base` / `effective_base`：`db1037b96a634e9e3a24435059697fdca4ce98c7`。
- `validated_at` / `effective_through`：`28220464582a2220289b42f1679ca81ed25e2b9f`。其后只补审查记录、文档路径／归档与交付记录；两份模型可见文本逐字未变，门禁 retained，最终文档提交 head 在 PR 展示。
- 原主仓仅迁出本任务两文件 dirty patch 和历史 HTML；先核对与独立提交完全一致，再逆向移除原补丁。`.gitignore`、使用记录、依赖缓存及其他调研文件均保留。原分支上的 `d07b2d0de` 是首次补记的历史文档提交，不是应整体合入的交付分支。
- feat-725 的评测工具另开 PR，两者无合入顺序依赖，不将评测基础设施的工程通过当作本 Prompt 的效果通过。

## 用户确认与独立门禁

用户明确接受当前状态，要求记录后续按实际情况审视。本轮未新增或修改已接受的 Prompt 文本。独立 `gpt-6.1-sol / high` full code review 和 Context Implementation Review 已通过，0 CRITICAL / 0 WARNING。

审查者读取了原生 DSH 发到本地 HTTP fixture 的 Global、PA、一级、嵌套及 cold resume 请求。请求装配和工具边界符合当前源码；没有专门加载持续工作 Skill，也没有运行真实模型，不据此宣称自主派工或附件续派行为已全面验证。

## 工程检查

使用 Node 24.22.1、既有 Python 3.12.9 `.venv`，日志仅保存在本机 `/Users/czj/.codex/reports/coordination-closeout-20261107/`。

| 检查 | 结果与限制 |
| --- | --- |
| `pnpm install --frozen-lockfile` | passed，无依赖清单变化。 |
| `pnpm build` / `pnpm typecheck` / `pnpm check:ios-runtime` | passed。 |
| 原生角色及恢复 fixture | 6 tests passed；临时捕获点已移除，长期测试逐字恢复。 |
| docs-check / ruff check / format / diff-check | passed。补齐被引用的 code-review.md 并纳入跟踪后通过，初始中间态的缺文件结果不冒充通过。 |
| 全量后端 | 首轮 `pnpm test --maxWorkers=4`：215 files，1170 passed / 1 failed。唯一失败为 agent-disable-native 的 `kill EPERM`；同版本该文件单独复跑 7 tests passed。相关测试通过固定 fixture 等待／停止流程，不依赖模型自主选择；本轮未改停止实现。保留全量首轮失败和复跑记录，不宣称全量首次通过，未复现不代表根因已确认。 |
| 产品前端与 Python 非 E2E | 复用同一主干基线的 1078 项 Web 前端、135 项 Python 非 E2E 及 critical 依赖审计通过证据；本 unit 未修改这些实现、测试或依赖。 |

日志：`prompt-build.log`、`prompt-typecheck.log`、`prompt-ios-runtime.log`、`prompt-fixture.log`、`prompt-full-vitest.log`、`prompt-disable-targeted.log`；最终输入：`fixture-inputs-global.json`、`fixture-inputs-pa.json`。捕获使用合成角色和本地 stub，不提交原始轨迹、配置或凭据。

## 合入与后续

当前 canonical 的最窄变化已归并到 `docs/specs/gateway/global-agent.md`，明确这是 Prompt / Skill 指导，不声明宿主自动交接保证。历史 HTML 保留快照警示。无数据迁移、无新增运行时或工具参数，无部署迁移操作。

PR 和远端 CI 继续核对；unit 归档不等于已经合入或部署。开放 PR 期间保留独立 worktree。后续根据 fix.md 中的具体轨迹／能力变化触发复审，不在没有新事实时继续加规则。
