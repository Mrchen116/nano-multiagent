# bugfix-693: Validation

- Base: `39a1d78ed25b4c19878dc98b63d96d4810cb2523`。
- 环境：隔离 worktree；Node 24.22.1、pnpm 11.7.0；测试用临时 home、动态本地端口与真实锁定 DSH；测试进程及临时文件均由 finally 清理。
- Red：新增 native 模型请求回归在原实现失败，提醒总数实际 4、期望 2。
- Green：首次窄回归 4 files / 60 tests 全部通过，覆盖 native Inbox、global-agent、runtime-profile、input-evidence。随后加强既有工具执行中消息批次覆盖；最终验证结果见下方补充。
- 验收授权：2026-11-01 用户明确表示“这个小修改，你自己验修，觉得OK就可以合入。” 因此本次由主 Agent 验收；用户未亲自测试，不伪造此类记录。
- 真实模型 / 生产 / Feishu：未执行，本次验证对象为确定性提醒机制。

## 最终验证

- `pnpm -r --if-present build`：通过（全部 workspace packages）。
- `pnpm typecheck`：通过（workspace + evals/memory）。
- 四文件窄回归：60 passed；工具执行三消息批次增强后，整个 `global-inbox-native.test.ts` 复跑：4 passed。
- 独立 reviewer 在固定 `fb7d67ce9` 上复跑模型忙碌/工具忙碌：2 passed；无缺陷，见 [code-review.md](code-review.md)。
- `pytest tests/contract/test_runtime_dependency_contract.py -q`：13 passed。
- 文档完整性检查：通过（277 maintained Markdown sources / 68 required routes）。首次系统 Python 缺少 yaml，改用仓库既有 `.venv` 后通过，未改产品。
- 上轮只执行窄回归；本轮按用户合入授权补齐本地 CI，结果记录在下方；随后用户明确授权无关失败不阻塞直接合入。iOS 原生工程未变，无需运行 Xcode job；iOS TypeScript runtime 检查仍运行。

## 本次合入验收与检查

- 用户授权本次由主 Agent 自验并合入，后续明确“这种跟你没关系吧，可以直接合入”；本次不要求用户亲自测试，不修改通用流程。
- 自验结论：真实 DSH + 受控模型请求捕获覆盖模型忙碌和工具忙碌时三消息合并；每次只新增一条 Inbox 提醒；消息正文完整可读、后续消息可再次提醒、其他通知和发送复核保留。通过，独立审查结论继续有效。
- 完整构建（含 installer candidate）、typecheck、iOS TypeScript runtime：通过；只生成本地候选产物，未发布安装包。
- Python 非 E2E：129 passed / 28 deselected；ruff check 与 format：通过。
- 前端依赖 critical audit：通过（0 critical；已有非 critical 报告未在本次修改）。
- 首轮 backend/frontend 全量同时执行时本机 load average 达 45，出现多项旧测试失败与超时；主动停止两套运行，未将失败写成通过。降低 backend 并发到 2 后，已复验先前失败的 capability catalog、Skill creator、workspace tools 等项通过；未修改其产品代码或测试。
- 按用户后续“可以直接合入”授权，不以无关全量失败阻塞本次交付，不继续扩大排查。全量检查的最终状态与远端 CI 以 PR 为准。
- 原始日志保存在本机 `/Users/czj/.codex/reports/bugfix-693-inbox-notice-coalescing/`；不提交日志或运行数据。
