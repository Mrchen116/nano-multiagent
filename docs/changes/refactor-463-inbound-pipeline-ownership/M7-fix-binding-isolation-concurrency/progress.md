# refactor-463-M7 — Progress

## 根因取证

- `PersistentSessionBindingStore.drop_agent()` / `bindings_for_agent()` / `find_direct_by_agent()` 将外部 Agent/channel 标识直接拼入参数化 `LIKE` pattern；参数化只防 SQL 注入，不会取消 `_` / `%` 的 pattern 语义，因此相似 id 会被错误查询或删除。
- `GatewaySessionBinder.resolve()` 在单一 `threading.Lock` 内调用同步 `Kernel.get_session()`；该 SDK 路径经 `SessionDirectory.get()` → `JsonlTranscript.load_config()` 遍历 JSONL。锁覆盖磁盘扫描，且同步调用发生在 async resolve 的 event-loop 线程，既串行化所有 binder 操作，也阻塞无关协程。
- D2/D3 约束：旧 snapshot 已开始的操作可以完整使用旧 revision；但 publish / invalidate 之后，任何旧 reuse/create 结果都不得重新写入 repository。修复需把慢校验拆成 capture → validate → recheck/commit 两阶段，而不是移除 workspace guard。

## R1 — SQLite binding 字面值隔离

- 状态：TODO
- Next：提交真实 repository/binder 红测。

## R2 — Binder workspace 校验两阶段并发协议

- 状态：TODO
- Next：R1 完成后提交可控慢校验并发红测。
