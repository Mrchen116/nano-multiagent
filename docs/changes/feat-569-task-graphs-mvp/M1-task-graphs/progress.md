# M1 implementation

- PA 增量：原生 task_graph 使用默认能力目录，保持显式 allowlist；Gateway 复用真实 binder guard 与现有 WS pending/ACK lane；输入来源与 graph home 独立。
- 原生工具缺失先得到 ModuleNotFoundError；实现后，工具/真实 loopback/binder/领域/API 共 29 项通过；WS correlation 与释放 lane 的窄测试另 1 项通过。原有 Gateway listener/IM connection 加工具检查 37 项通过。
- 最近 change_note 保存到受改节点并在 Web 详情展示（无历史表）；这是已批准返工原因的持久化落点。列表 total 属同一权限过滤，delta 已按实现补齐这两项可观察细节。
- 最新前端 build + task graph 6 项窄测试通过；上一前端增量全量 776 项通过，最终 CI 还将核对集成树。

- Baseline: `499774a56`; branch `codex/feat-569-task-graphs`, managed worktree `/Users/czj/.codex/worktrees/unit-feat-569/nano-multiagent`.
- Gate 2: Round 3 Approved; only status metadata changed afterward.
- Work split: primary owns IM persistence/authorization/protocol and PA tool integration; bounded frontend implementation delegated independently under the same fixed API. Primary integrates and owns final validation/PR.
- Existing tests searched: IM Work API/repository tests (keep: separate Work semantics), Gateway internal listener/IM connection tests (extend where transport changes), frontend current chat/navigation tests (frontend owner).
- New permanent coverage: task-graph domain invariants and atomic persistence/ACL through HTTP/WS. This new business resource has no prior regression owner. Tests stay at the lowest seam exposing each risk; model/browser evidence is separate.
- Consumer clarification: list results include `total` under the same member/query/conversation filter, so Chat can display its count without loading every page. No change to the approved user behavior or write interface.
# IM 持久化增量

- 真实 HTTP/WS 测试先取得缺失端点 404，再实现 IM 单一存储、原子批量、revision 冲突、请求去重、当前成员授权与只读浏览 API。
- `PYTHONPATH=src .venv/bin/python -m pytest tests/im_service/unit/test_task_graph_rules.py tests/im_service/integration/test_task_graph_api.py -q`（使用主仓 .venv）：20 passed。覆盖 global/single_thread 同权、并发只成功一次、重启后数据保持、撤权后不能重放历史成功回执。
- 对本增量全部 Python 文件执行 Ruff check：通过。

## P5 修复：从 Agent 正文和 Work 返回时保留草稿

- 独立真实浏览器验收复现：聊天/Work 的任务 Markdown 链接触发完整页面导航，清空内存中的聊天 composer；顶部 Tasks 的 SPA 跳转正常。根因在跳转边界。
- 同源任务链接统一走现有 Router，在聊天正文、Work 和任务详情的 Markdown 中复用；原有外链分类与普通链接行为保持。
- 先补真实 MessagePane 链接路径和 Work 路由断言得到红测，再修复：140 项相关测试通过，TypeScript/Vite build 通过。任务往返断言包含正文、mentions、待发附件及不自动发送。
- 产品 Round 1 的其余场景和原型对照保留；I1 交给独立 reviewer 做针对性复验。
