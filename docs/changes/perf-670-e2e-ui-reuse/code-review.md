# perf-670: Code Review

## Scope and result

- Mode: full；范围为 PR #416 的完整最终实现 diff（含原启动修复）。
- validated_at: `e66e79e903b8fbb28a33fab631b9186a809bc492`
- executed_base: `39ce046cc2f228fc2be41f1418452b512df4ff75`
- 独立 reviewer: `/root/review_e2e_ui_reuse`，`gpt-6.1-sol/high`，未参与实现。
- findings: `[]`，无确认的阻塞缺陷。
- 实际覆盖：输入/产物指纹、共享包构建顺序、失败记录失效、启动接线、Vite HTTP/WS 代理及进程出生时间校验。
- reviewer 独立验证：13 个构建行为测试通过，diff-check 通过。未重复启动服务或构建共享产物；真实进程验证由主 Agent 执行。
- Agent Context: 本次 diff 不修改模型可见信息或消费链，无完整 Context Review。

## 主 Agent 验证

- Red：旧无条件构建在后端修改后的第二次准备仍调用两套构建，复用用例失败。
- Green：`tests/integration/test_e2e_ui.py` 13 passed。
- 同步最新 main 后，`pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime` 通过。
- Python 非 E2E：97 passed / 28 deselected；ruff check/format 通过。
- Web：108 files / 1029 tests passed，critical-level audit 通过（既有非 critical advisories 未在本任务升级）。
- docs-check、bash -n、diff-check 通过。docs-check 首次使用系统 Python 缺 PyYAML，改用已配置主仓 `.venv/bin` PATH 后通过；没有修改产品代码或测试断言。
- 两个全新隔离目录真实执行 `e2e-up.sh --vite`：首次 47.122 秒（main 同步引起重建），第二次 12.787 秒（两套 UI 均 reuse）。完整启动时间受当时并发测试负载影响，不能当作稳定性能保证。
- 每轮均验证 IM/Vite 的 `/`、`/trajectory/`、`/trajectory/boot.js` 为 200，浏览器模式登录允许精确 Origin、拒绝继承的 foreign Origin 为 403；每轮 down 后 IM/Gateway/Vite PID 和两个监听端口均已释放。
- 本轮没有新的模型调用；原 PR 同源/Vite 的真实模型与轨迹浏览器证据继续保留，未改回复/轨迹业务链。

证据目录：`/Users/czj/.codex/experiments/pa667-startup/build-reuse-review/`。日志、配置、凭据和运行数据库留本机，不提交。
