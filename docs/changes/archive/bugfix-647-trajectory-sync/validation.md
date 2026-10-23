# bugfix-647 — 交付验证

## 验证版本与范围

- `executed_base`: `236a4698c7a8a2d03efa00c35049914d2422771d`
- `validated_at`: `a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7`
- Node 24.22.1 / pnpm 11.7.0；专属 checkout `codex/bugfix-647-trajectory-sync`。
- 编译、测试、性能实验与独立门禁针对同一源码；最终同步、归档与报告提交的有效性见下文。没有操作生产 checkout、合并 PR 或部署生产。

## 本地检查

| 检查 | 结果 | 本机证据 |
|---|---|---|
| `pnpm build` / `pnpm typecheck` | PASS | `/tmp/nano-647-final-build.log`、`/tmp/nano-647-typecheck.log` |
| PA global-agent + 真 runtime presenter | 2 files / 48 passed | `/tmp/nano-647-green.log` |
| descendants、model-fallback、trajectory-runs、task-graph-permission | 4 files / 22 passed | `/tmp/nano-647-focused.log` |
| 完整后端 `pnpm exec vitest run --maxWorkers=2` | 123 files / 601 passed，309.63s | `/tmp/nano-647-vitest-stable.log` |
| `pytest -m "not e2e" -q` | 65 passed / 31 deselected | `/tmp/nano-647-python.log` |
| `ruff check .` / `ruff format --check .` | PASS，85 files formatted | `/tmp/nano-647-ruff.log` |
| `pnpm check:ios-runtime` | PASS | `/tmp/nano-647-ios-runtime.log` |
| Web `npm run test` | 103 files / 963 passed | `/tmp/nano-647-frontend-tests.log` |
| Web `npm run build` | PASS；现有 chunk-size 提示 | `/tmp/nano-647-frontend-build.log` |
| Web `npm audit --audit-level=critical` | exit 0；8 条低于 critical 的现存依赖提示 | `/tmp/nano-647-audit.log` |
| `./scripts/docs-check` | PASS；归档后复验 | `/tmp/nano-647-docs.log` |

首轮完整后端与前端回归同时运行时，600 项通过，workspace-tools 长旅程一项 90s timeout。该测试原样隔离重跑 1 passed / 49.27s；随后完整后端仅降低并发，全部 601 项通过。没有修改测试、timeout 或产品源码；并发负载是合理推断，未精确证明为唯一原因。日志 `/tmp/nano-647-vitest.log`、`/tmp/nano-647-workspace-retry.log` 保留失败与复验原貌。

## 独立门禁与性能

- Gate 2：`design-review.md` Round 3 Approved；此前模型版本确认与快照时点两项发现均已修正。
- Code review：`code-review.md`，full review，findings `[]`。
- Verifier：`verification.md`，0 CRITICAL / 0 WARNING，no spec delta aligned；当前契约已要求无关历史不得阻塞当前查询，并要求轨迹完整可恢复。
- 产品旅程：`regression.md`，使用隔离真实服务的客户端 API；不冒充视觉验收。
- `M1-fix/evidence/performance.md`：400 个冷子会话、151.97 MiB 压缩历史；旧路径重复读取 800 次，18.095/20.626/31.559s；新路径重复零 body read，103.70/101.05/97.95ms。首次读取仍 9.628s；reader 重建仍需恢复目录。新增、续写、孙会话、重启、失败不确认和重试都有直接证据。
- 性能数字只代表 native 后代同步核心，不包括 stdio、PA、模型、审批、IM 或网络，不据此宣称生产 RTT 或部署后的收益。

隔离产品验收发现默认审批模型不支持当前 `low` 请求。仅在本 worktree 临时配置中选择支持该参数的 `codexOAuth:gpt-6-luna` 后重启，保留独立审批及原数据；没有改变审批规则或生产配置。默认 maxDepth=1 保持不变，孙会话覆盖来自持久 native 实验与测试。

## 最终同步与归档

- `effective_base`: `c5ee4d1bdca912391097fe1769ce56ec2015c297`
- `effective_through`: `415025ef701b5f8384b8ee6f3cc9f92fb2baf179`（final sync merge）；最终归档 head 见 PR 的同名字段。
- final sync 从 executed_base 到该 main 仅引入其他 unit 的 21 个文档/原型/图片文件，没有产品源码、测试、依赖、current spec 或 CI 变化，没有冲突。`git diff --exit-code a33d21099 -- packages apps src pnpm-lock.yaml package.json` 通过。
- retained：Gate 2、full code review、verification、独立产品 pass、性能和本地测试继续支持同一源码/契约/旅程结论。后续只固化报告、归档本 unit 和修正实验命令路径，不扩大验收判据、不改变受审行为。归档后 docs-check PASS（`/tmp/nano-647-docs-final.log`）；archive checker 以 `--head-ref unit/bugfix-647-trajectory-sync` 显式核对唯一归档目录并 PASS（当前 codex/ 分支不会自动触发脚本的 unit/ 分支匹配）。
- no spec delta 已由独立 verifier 确认，无 canonical spec 需要归并。
- caller 已用本 worktree 的 e2e-down 停止 Gateway/DSH/IM；原 Gateway PID 76123 与 IM PID 71043 消失，49160 无 listener，专属 tmux nano647-e2e 已关闭。产品 reviewer 已删除临时令牌；摘要与可复现实验随 unit 归档，本机原始证据留在 `/tmp/nano647-review/` 与 `/tmp/nano-647-*`。
- 适用远端 CI 由最终 PR checks 记录；没有执行 merge 或生产部署。
