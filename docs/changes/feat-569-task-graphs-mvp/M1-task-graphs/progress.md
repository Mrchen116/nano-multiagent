# M1 implementation

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
