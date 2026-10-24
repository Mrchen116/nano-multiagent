# M1 execution evidence

- Candidate: `0d3a762fed52`；DSH `0.2.1-alpha.1`，Node `24.22.1`，2026-10-25。
- 范围：隔离本地 Node + DSH + IM + Web，真实工具执行，确定性 fake provider；没有生产写入或生产部署。独立用户旅程结论见 `review.md`。
- Runtime：`/tmp/nano-refactor655-browser`。本机脚本、SQLite、截图和日志不提交；以下记录可从提交测试及明确操作复核。

## 真实执行及重启

通过真实聊天入口触发 Global Agent：`inbox.check/read` → 主执行 `read` 成功 → `subagent` → 子执行 `read` 缺文件失败、第二次 `read` 成功 → `send_message` 交付。Work 中工具参数、结果、失败与主子关系来自这条真实链路，不是直接插入 Work 表。

首次完成：Work revision=35，主执行 context=40/output=18/cache_read=60/cache_total_input=240；子执行 context=40/output=9/cache_read=30/cache_total_input=120。`/tmp/refactor655-restart-probe.py` 经项目 `restart_gateway` 重启隔离 Gateway，恢复到 online/current 后严格比较主 turns、子 turns、latest_main_usage 和 revision：全部相同，revision 仍为 35。证据 `restart-evidence.json`。

第二轮通过同一聊天发送真实消息，临时暂停自有 fake provider 模拟响应等待；Node/IM 保持运行。Work revision=37 时 turn2=running、turn1=completed，latest_main_usage 仍指向 turn1。独立 reviewer 观察新轮次和最近已报告统计后恢复 provider，页面自动完成，revision=68、两个完成主轮次和两个子执行、record_sync_state=current。证据 `running-evidence.json`、`pagination-evidence.json`。

真实 API `GET /im/v1/agents/e2e-global/work?limit=1` 返回 turn2；随后 `before_turn=2&limit=1` 返回 turn1。两页完整 turn 对象与默认列表前两项严格相等，证明已有保存内容直接分页，不重建统计。Web 默认页容量未被改小，浏览器分页交互不以这条 API 证据冒充。

## 首次升级、正文读取与回滚副本

1. `/tmp/refactor655-upgrade-copy.mjs` 用主仓升级前已构建的 NodeStore/InboxStore/IM 数据库入口创建旧库（含累计历史样本、journal id、事件与 ACK），关闭并复制到独立路径。候选版本打开副本：新增处理 checkpoint 初始为空，journal/ACK 不变；补交相同 stable event 时 journal 不重复。随后旧版本三个入口重新打开升级副本，累计样本、journal id/内容/ACK 均保留。结果 `/tmp/refactor655-upgrade-copy/evidence.json`。这是库兼容和成套旧入口回滚演练，不代表执行过生产部署回滚。
2. `/tmp/refactor655-bootstrap-copy.mjs` 复制真实已完成主子原生日志与存储元数据，唯独不复制新 `nano_work_catalog`。用候选真实 DSH RuntimeClient、公开 persistence.open/handle.read 包装计数：首次补建主 43 events、子 29 events 各读取正文一次；使用真实已保存 modelVersion/cursors 再冷重启，Work check settled/rootSettled 均为 true，descendants 正文读取 0 次。结果 `/tmp/refactor655-bootstrap-copy-2/evidence.json`。无 Agent 执行、无源目录写入。
3. 提交中的 `packages/dsh-integration/tests/workflow-native.test.ts` 进一步覆盖四个完成子执行冷重启 0 次、单个变化分支 1 次、增长到八个子执行后冷重启仍 0 次，并保留 Workflow spent=15。正文计数是公开 handle.read 的逻辑读取调用，不冒充物理磁盘 I/O；变化分支仍可能由上游 JSONL 完整解码。

## 本地等价检查

| 检查 | 结果 |
|---|---|
| `pnpm build`、`pnpm typecheck` | 通过；首次完整 build 后的定向修改另有单包 build，最终 typecheck 通过 |
| `pnpm exec vitest run --maxWorkers=2` | 131 files / 703 tests 通过，305.36s |
| 前端 `npm test -- --maxWorkers=2` | 107 files / 1022 tests 通过，102.43s |
| 前端 `npm run build` | 通过 |
| `npm audit --audit-level=critical` | 通过；已有 11 项 low/moderate/high，0 critical，未更改依赖 |
| `pytest -m 'not e2e' -q` | 65 通过 / 31 deselected；final sync 后新 main 测试另见 delivery |
| `ruff check .` / `ruff format --check .` | 通过，85 files |
| `pnpm check:ios-runtime` | 通过 |
| iOS `build.sh test` / `build.sh archive` | 24 tests / 5 suites 通过；Release device archive 成功 |
| token critical path（真实栈 fake provider） | 通过；bubble 与 Work context=31001/output=1/cache_read=1000，累计 API 404 |
| 独立 runtime dependency contract | 13 项通过 |

无约束全量 backend/frontend 同时运行曾因资源竞争超时；没有放宽测试超时或删除断言，改为有界 workers 分开执行后全量通过。对应日志位于 `/tmp/refactor655-{backend-tests-bounded,frontend-tests-bounded,typecheck,build,python-tests,ios-full,ios-archive,token-e2e,native}.log`。

## 页面环境说明

浏览器来自上述冻结 HEAD 的 Vite 开发服务 `http://127.0.0.1:59749`，代理独立 IM `59921`。最初 `/trajectory/` 未配置代理，错误回退到主前端；补充临时 Vite 配置及 IM_TRAJECTORY_DIST_DIR 后以本候选已构建 viewer/dist 提供原生轨迹。未修改产品源码。独立 reviewer 的实际视觉、详情与状态体验以 `review.md` 为准。
