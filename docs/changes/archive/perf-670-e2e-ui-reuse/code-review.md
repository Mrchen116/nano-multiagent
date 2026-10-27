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

## Cross-worktree patch review and final validation

- R2 范围：`e66e79e..4aeebb54156776e78d80e5a2f6ba2c36a5e451c3`，同一独立 reviewer 执行 patch review。检查共享缓存有界存储、可移植指纹、共享副本与恢复后完整性校验、文件锁和旧记录失效。Result: `[]`。
- 增加 `_read_stamp` 的联合类型注解后，直接运行系统 Python 3.9 暴露导入期 TypeError；`4aeebb541` 用 future annotations 修复，独立 reviewer 确认系统 Python 导入通过。
- 最终 helper 行为测试 16 passed，完整 Python 非 E2E 100 passed / 28 deselected，ruff check/format 通过。
- 后端完整测试 142 files / 770 tests passed。初次生命周期测试与该套件并发时，3 个用例在 UI 构建阶段达到外层 30/60 秒超时；同代码、同超时设置单独重跑为 4 passed / 103.19 秒。未调整 timeout 或产品逻辑；并发负载为可能因素，不把重跑成功当作唯一根因证明。原失败与独立重跑日志均保留。
- 最终共享缓存版本：UI 首次构建 17.344 秒，同 checkout 无变化 0.242 秒。新建 managed Git worktree，在准备同内容共享包导出与安装锁元数据后，真实 helper 用 0.937 秒恢复两套真实 UI，未调用构建器；主前端 1656 个文件、查看器 154 个文件逐文件 SHA-256 一致。这验证真实产物恢复，不冒充该 worktree 的完整依赖安装或全服务启动。
- `4aeebb541` 上又在两个全新运行目录完成 `e2e-up.sh --vite`：9.101 / 8.209 秒，均两套 reuse；IM/Vite 页面、轨迹资源、精确 Origin 允许/外来 Origin 拒绝与 PID/端口清理再次通过，无新增模型调用。
- effective_base: `39ce046cc2f228fc2be41f1418452b512df4ff75`；实现验证与审查有效到 `4aeebb54156776e78d80e5a2f6ba2c36a5e451c3`。后续只补充本报告和归档，核心构建/typecheck/770 后端/1029 前端/原浏览器证据保留；新增缓存 delta 由上述 Python、真实产物和最终入口检查覆盖。
- 用户明确授权“测好了再更新pr”，验证由 Agent 执行；未声称用户亲自重跑，不合入、不部署。

## Final main sync

- 收尾时 main 合入 #422，effective_base 更新为 `4cea0166d70a604da6a7dcea9246d81e37b1e1bb`；集成树 effective_through 为 `a79a0dc48ac80f2c2ad73226b7355d683bcabdb7`。
- main 增量为 PA/子执行指导、相关测试和文档，未修改本次构建输入集合、前端/轨迹源码、启动脚本或依赖锁；R1/R2 对 PR diff 的审查仍有效。集成后重新 build、typecheck、16 项缓存测试、docs-check 均通过，UI helper 明确两套 reuse，验证后端更新不导致无关 UI 重建。
- 集成树再起全新 `--vite` 隔离栈，9.306 秒，两套 reuse；同源/Vite 页面、轨迹资源、Origin 与清理均通过。首次探针过快命中已有账号每秒一次登录限制（429），按实际 Retry-After 重跑通过；仅修正临时验证脚本，不修改产品限流。
- 后续提交仅补本段事实。开发 worktree 保留供 PR 审查；用于真实产物校验的临时 managed worktree 请求归档时被应用以“当前主 checkout 不可移除”拒绝，未强制删除；该目录无自建服务，验证证据已在外部报告目录保留。
