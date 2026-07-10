# M1-fix progress

## R1+R2+R3+R4+R5 — 一次性原子提交（lite 单 milestone 范围足够小）

**Context**: fix.md 根因已锁定 `auto_mode_gate.SAFE_TOOL_ALLOWLIST` 不含 `memory`，且 RCA 上挖一层"新增 tool 漏接 gate 是个未成文的跨模块约束"。本 milestone 同时落地修复（allowlist 加 memory）+ 防回归（builtin gate coverage 契约测试）。

**Decision**: 方案 A（加 allowlist）而非 B（给 MemoryTool 实现 check_permissions）。理由见 fix.md "修复"段：本仓既定模式 + 上游 CC 一致，B 写出来只是无逻辑的 `return allow`。

**Rationale**:
- allowlist 是单点登记表，新增 tool 一处可读、PR diff 显眼。
- 强契约测试 `EXPECTED_GATE_POSITION` 钉死每个 builtin tool 的 gate 归属（allowlist / check / classifier 三选一）。新增 tool 必须**两处同步**改才能过 CI——把 issue #31 的根因模式（漏接 gate）从"靠人记"提升为"CI 强约束"。
- 顺手把 skill_manage 显式登记为 classifier（写用户 skill 文件，per-call 判更稳）；如果以后有人误把它加到 allowlist，契约测试会立刻炸。

**Evidence**:
- `pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_memory_tool.py tests/contract/test_tool_gate_coverage.py` → **99 passed in 0.20s**
- 试删 `"memory"` 后 `test_memory_safe` + `test_each_builtin_tool_matches_its_declared_gate_position` 红，证明回归测试有效。
- 试加虚构 `FooTool` 到 `builtins/__init__.py` 后 `test_every_builtin_tool_has_an_expected_gate_position` 红，证明强契约会拦"漏接 gate"。

**Rollback**: 单 commit，`git revert <hash>` 即可。allowlist 减一个条目不会破坏既有调用路径——只是把 memory 重新打回 classifier deny 状态（与 #31 前现状一致）。

**Commits**:
- `c0ba189a` docs(bugfix-368): spec lite — ...（spec-author 阶段，已合）
- `<待补>` fix(bugfix-368/M1): memory → SAFE_TOOL_ALLOWLIST + builtin gate coverage 契约测试

## Next

无。lite 单 milestone 已完成，由 orchestrator 直接走 §7 提 PR。
