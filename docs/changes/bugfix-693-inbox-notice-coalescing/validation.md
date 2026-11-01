# bugfix-693: Validation

- Base: `39a1d78ed25b4c19878dc98b63d96d4810cb2523`。
- 环境：隔离 worktree；Node 24.22.1、pnpm 11.7.0；测试用临时 home、动态本地端口与真实锁定 DSH；测试进程及临时文件均由 finally 清理。
- Red：新增 native 模型请求回归在原实现失败，提醒总数实际 4、期望 2。
- Green：首次窄回归 4 files / 60 tests 全部通过，覆盖 native Inbox、global-agent、runtime-profile、input-evidence。随后加强既有工具执行中消息批次覆盖；最终验证结果见下方补充。
- 用户亲自验收：待用户确认，不能以自动化验证替代。
- 真实模型 / 生产 / Feishu：未执行，本次验证对象为确定性提醒机制。

## 最终验证

- `pnpm -r --if-present build`：通过（全部 workspace packages）。
- `pnpm typecheck`：通过（workspace + evals/memory）。
- 四文件窄回归：60 passed；工具执行三消息批次增强后，整个 `global-inbox-native.test.ts` 复跑：4 passed。
- 独立 reviewer 在固定 `fb7d67ce9` 上复跑模型忙碌/工具忙碌：2 passed；无缺陷，见 [code-review.md](code-review.md)。
- `pytest tests/contract/test_runtime_dependency_contract.py -q`：13 passed。
- 文档完整性检查：通过（277 maintained Markdown sources / 68 required routes）。首次系统 Python 缺少 yaml，改用仓库既有 `.venv` 后通过，未改产品。
- 未执行全量 pnpm/pytest、前端/iOS 门禁或远端 CI；此次范围为 runtime Inbox 提醒。完整快修归档/交付仍待用户验收及对应本地 CI，不将当前窄回归写作全量 CI 通过。
